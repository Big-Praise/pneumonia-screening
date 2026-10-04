"""Tiny key -> bytes store for images and LIME results, on disk or in the database.

Decision: one interface, two backends (config.BLOB_BACKEND). The Streamlit app
keeps using disk; the hosted API uses the database because the host's disk is
wiped on every restart. Names are relative paths like "ab12.png" or "lime/ab12.npz".
"""
from pathlib import Path

import config


class BlobError(ValueError):
    pass


def _disk_path(name: str) -> Path:
    root = config.UPLOAD_DIR.resolve()
    path = (root / name).resolve()
    if root not in path.parents:  # never read/write outside UPLOAD_DIR
        raise BlobError("Invalid file name.")
    return path


def put(name: str, data: bytes) -> None:
    if config.BLOB_BACKEND == "db":
        from db import Blob, get_session
        with get_session() as s:
            s.merge(Blob(name=name, data=data))
        return
    path = _disk_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def get(name: str) -> bytes | None:
    if config.BLOB_BACKEND == "db":
        from db import Blob, get_session
        with get_session() as s:
            blob = s.get(Blob, name)
            return blob.data if blob else None
    path = _disk_path(name)
    return path.read_bytes() if path.exists() else None


def exists(name: str) -> bool:
    if config.BLOB_BACKEND == "db":
        from sqlalchemy import select

        from db import Blob, get_session
        with get_session() as s:
            return s.scalar(select(Blob.name).where(Blob.name == name)) is not None
    return _disk_path(name).exists()


def delete(name: str) -> None:
    if config.BLOB_BACKEND == "db":
        from db import Blob, get_session
        with get_session() as s:
            blob = s.get(Blob, name)
            if blob:
                s.delete(blob)
        return
    _disk_path(name).unlink(missing_ok=True)
