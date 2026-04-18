from __future__ import annotations

import base64
import io
import mimetypes
from pathlib import Path
from typing import BinaryIO

from dox.models.elements import Figure


_PATH_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}


def figure_display_src(element: Figure) -> str:
    """Return a displayable source for HTML/Markdown converters."""
    if element.source:
        return element.source
    if element.image_data:
        return f"data:{_guess_mime_type(element)};base64,{element.image_data}"
    return ""


def figure_binary_source(element: Figure) -> tuple[str | BinaryIO | None, str]:
    """Return a path or in-memory stream for binary converters."""
    source = element.source or ""
    img_path = Path(source)
    if img_path.exists() and img_path.suffix.lower() in _PATH_IMAGE_SUFFIXES:
        return str(img_path), source

    if element.image_data:
        try:
            raw = base64.b64decode(element.image_data, validate=True)
        except Exception:
            return None, source or "[embedded image]"
        buf = io.BytesIO(raw)
        ext = mimetypes.guess_extension(_guess_mime_type(element)) or ".png"
        buf.name = f"embedded{ext}"
        return buf, source or "[embedded image]"

    return None, source


def _guess_mime_type(element: Figure) -> str:
    """Best-effort MIME type guess for embedded figure data."""
    if element.source:
        guessed, _ = mimetypes.guess_type(element.source)
        if guessed and guessed.startswith("image/"):
            return guessed
    return "image/png"
