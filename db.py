"""Database layer: SQLAlchemy models (User, Patient, Scan) + session helper.

Schema follows docs/DATA_MODEL.md, plus one approved addition:
`Scan.pneumonia_prob` (the raw model output p). Label and confidence alone
can't be re-thresholded later; storing p keeps every saved scan reproducible.

Decision: the engine is created lazily via init_db(url) so tests can point at a
throwaway database without touching app.db.
"""
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, create_engine, event, func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

import config


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)  # bcrypt only
    full_name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    patients: Mapped[list["Patient"]] = relationship(back_populates="creator")
    scans: Mapped[list["Scan"]] = relationship(back_populates="user")

    def __repr__(self) -> str:  # never include the hash in reprs/logs
        return f"<User id={self.id} username={self.username!r}>"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    creator: Mapped[User] = relationship(back_populates="patients")
    scans: Mapped[list["Scan"]] = relationship(
        back_populates="patient", order_by="Scan.created_at.desc()"
    )

    def __repr__(self) -> str:  # id only — patient details stay out of logs
        return f"<Patient id={self.id}>"


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)  # relative to UPLOAD_DIR
    predicted_label: Mapped[str] = mapped_column(String(16), nullable=False)  # NORMAL | PNEUMONIA
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0..1, for the label shown
    pneumonia_prob: Mapped[float] = mapped_column(Float, nullable=False)  # raw model output p
    threshold_used: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="scans")
    user: Mapped[User] = relationship(back_populates="scans")

    def __repr__(self) -> str:
        return f"<Scan id={self.id} patient_id={self.patient_id}>"


class Blob(Base):
    """Binary files (X-ray PNGs, LIME results) when BLOB_BACKEND=db. Keyed by the
    same relative name used on disk, so Scan.image_path works with either backend."""
    __tablename__ = "blobs"

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


_engine = None
_SessionLocal = None


def init_db(url: str | None = None) -> None:
    """Create the engine and any missing tables. Safe to call repeatedly."""
    global _engine, _SessionLocal
    url = url or config.DATABASE_URL
    if _engine is not None and str(_engine.url) == url:
        return
    is_sqlite = url.startswith("sqlite")
    # Streamlit reruns scripts on different threads; SQLite must allow that.
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    # pool_pre_ping: hosted Postgres (Neon) closes idle connections; re-check before use.
    _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=not is_sqlite)
    if is_sqlite:
        # SQLite ignores foreign keys unless asked per connection.
        @event.listens_for(_engine, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    # expire_on_commit=False lets callers read attributes after the session closes.
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)


@contextmanager
def get_session():
    """Commit on success, roll back on error, always close."""
    if _SessionLocal is None:
        init_db()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ------------------------------------------------------------------ queries
# Every query takes the user id and filters on it: a clinician only ever sees
# their own patients and scans (approved scoping decision).

class NotFound(LookupError):
    """Record missing or not owned by this user (deliberately indistinguishable)."""


def as_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo on read; values are always stored as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def create_patient(user_id: int, name: str, age: int | None = None,
                   sex: str | None = None, note: str | None = None) -> Patient:
    name = (name or "").strip()
    if not name:
        raise ValueError("Patient name is required.")
    if age is not None and not 0 <= age <= 130:
        raise ValueError("Age must be between 0 and 130.")
    with get_session() as s:
        p = Patient(name=name, age=age, sex=sex or None,
                    note=(note or "").strip() or None, created_by=user_id)
        s.add(p)
        s.flush()
        return p


def list_patients(user_id: int) -> list[Patient]:
    with get_session() as s:
        return list(s.scalars(
            select(Patient).where(Patient.created_by == user_id).order_by(Patient.name)
        ))


def get_patient(user_id: int, patient_id: int) -> Patient:
    with get_session() as s:
        p = s.get(Patient, patient_id)
        if p is None or p.created_by != user_id:
            raise NotFound("Patient not found.")
        return p


def create_scan(user_id: int, patient_id: int, image_path: str, predicted_label: str,
                confidence: float, pneumonia_prob: float, threshold_used: float) -> Scan:
    get_patient(user_id, patient_id)  # ownership check before writing
    with get_session() as s:
        scan = Scan(patient_id=patient_id, user_id=user_id, image_path=image_path,
                    predicted_label=predicted_label, confidence=confidence,
                    pneumonia_prob=pneumonia_prob, threshold_used=threshold_used)
        s.add(scan)
        s.flush()
        return scan


def update_scan_threshold(user_id: int, scan_id: int, threshold: float) -> Scan:
    """Re-save a scan at a new threshold. Label and confidence are recomputed from
    the stored pneumonia_prob so the row can never disagree with itself."""
    from predict import classify  # pure function; local import keeps db free of ML deps at load

    if not 0.0 <= threshold <= 1.0:
        raise ValueError("Threshold must be between 0 and 1.")
    with get_session() as s:
        scan = s.get(Scan, scan_id)
        if scan is None or scan.user_id != user_id:
            raise NotFound("Scan not found.")
        scan.predicted_label, scan.confidence = classify(scan.pneumonia_prob, threshold)
        scan.threshold_used = threshold
        s.flush()
        return scan


def get_scan(user_id: int, scan_id: int) -> tuple[Scan, Patient]:
    with get_session() as s:
        row = s.execute(
            select(Scan, Patient).join(Patient, Scan.patient_id == Patient.id)
            .where(Scan.id == scan_id, Scan.user_id == user_id)
        ).first()
        if row is None:
            raise NotFound("Scan not found.")
        return row[0], row[1]


def patient_summaries(user_id: int) -> list[tuple[Patient, int, datetime | None]]:
    """Each of the user's patients with their scan count and latest scan time."""
    with get_session() as s:
        rows = s.execute(
            select(Patient, func.count(Scan.id), func.max(Scan.created_at))
            .outerjoin(Scan, (Scan.patient_id == Patient.id) & (Scan.user_id == user_id))
            .where(Patient.created_by == user_id)
            .group_by(Patient.id).order_by(Patient.name)
        ).all()
        return [(r[0], r[1], r[2]) for r in rows]


def scans_for_patient(user_id: int, patient_id: int) -> list[Scan]:
    """A patient's scan history, newest first (ownership-checked)."""
    get_patient(user_id, patient_id)
    with get_session() as s:
        return list(s.scalars(
            select(Scan).where(Scan.patient_id == patient_id, Scan.user_id == user_id)
            .order_by(Scan.created_at.desc(), Scan.id.desc())
        ))


def recent_scans(user_id: int, limit: int = 10) -> list[tuple[Scan, Patient]]:
    with get_session() as s:
        rows = s.execute(
            select(Scan, Patient).join(Patient, Scan.patient_id == Patient.id)
            .where(Scan.user_id == user_id)
            .order_by(Scan.created_at.desc(), Scan.id.desc()).limit(limit)
        ).all()
        return [(r[0], r[1]) for r in rows]


def count_for_user(user_id: int) -> tuple[int, int]:
    with get_session() as s:
        n_p = s.scalar(select(func.count(Patient.id)).where(Patient.created_by == user_id))
        n_s = s.scalar(select(func.count(Scan.id)).where(Scan.user_id == user_id))
        return n_p, n_s
