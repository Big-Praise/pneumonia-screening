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
    DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event,
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
    _engine = create_engine(url, connect_args=connect_args)
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
