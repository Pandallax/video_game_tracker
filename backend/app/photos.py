"""Normalize uploaded copy photos to compact WebP files."""
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

WEBP_QUALITY = 85
# Phone photos are often 4000px+; this is plenty for viewing a case and keeps files ~100-300 KB.
MAX_DIMENSION = 1600
MAX_UPLOAD_BYTES = 25_000_000


class PhotoError(ValueError):
    pass


def to_webp(content: bytes) -> bytes:
    try:
        image = Image.open(BytesIO(content))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise PhotoError("Couldn't read that file as an image (JPEG, PNG, WebP or GIF)") from exc

    # Phones store rotation in EXIF instead of rotating the pixels.
    image = ImageOps.exif_transpose(image)
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")

    out = BytesIO()
    # No exif= argument, so camera metadata (including GPS location) is dropped.
    image.save(out, format="WEBP", quality=WEBP_QUALITY, method=6)
    return out.getvalue()
