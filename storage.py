"""Validate, save and load uploaded X-ray images (local disk only).

Decisions:
- Files are re-encoded as PNG under a random UUID name. That (a) proves the
  upload really is a decodable image, (b) strips EXIF/metadata that could carry
  identifying information, and (c) means user-supplied filenames never touch
  the filesystem (no path tricks, no patient names in filenames).
- The DB stores the path relative to UPLOAD_DIR, so the folder can be moved.
"""
import io
import uuid

from PIL import Image, UnidentifiedImageError

import blobstore
import config

MIN_SIDE = 64
# Refuse absurdly large images (decompression-bomb protection); real CXRs are < 10 MP.
Image.MAX_IMAGE_PIXELS = 50_000_000


class ImageError(ValueError):
    """Displayable problem with an uploaded image."""


def load_upload(data: bytes) -> Image.Image:
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ImageError(f"File is larger than {config.MAX_UPLOAD_MB} MB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()  # catches truncated/corrupt files
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ImageError("This file isn't a readable JPG or PNG image.") from e
    if img.format not in ("JPEG", "PNG"):
        raise ImageError("Only JPG and PNG images are supported.")
    if min(img.size) < MIN_SIDE:
        raise ImageError(f"Image is too small (minimum {MIN_SIDE}×{MIN_SIDE} pixels).")
    # Normalise odd modes (CMYK, 16-bit, palette) to something every step handles.
    if img.mode not in ("L", "RGB"):
        img = img.convert("RGB")
    return img


def save_image(img: Image.Image) -> str:
    rel = f"{uuid.uuid4().hex}.png"
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    blobstore.put(rel, buf.getvalue())
    return rel


def delete_image(rel: str) -> None:
    blobstore.delete(rel)


def open_image(rel: str) -> Image.Image:
    try:
        data = blobstore.get(rel)  # disk or DB, per config.BLOB_BACKEND
    except blobstore.BlobError as e:
        raise ImageError("Invalid image path.") from e
    if data is None:
        raise ImageError("The stored image file is missing.")
    with Image.open(io.BytesIO(data)) as img:
        return img.copy()
