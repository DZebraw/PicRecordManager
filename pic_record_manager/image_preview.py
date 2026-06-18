from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


def load_preview_pixmap(path: Path | str, max_width: int, max_height: int) -> QPixmap:
    """Load an image into a QPixmap scaled to fit the preview bounds."""

    pixmap = QPixmap(str(Path(path)))
    if pixmap.isNull():
        raise OSError(f"Unable to load image: {path}")
    return pixmap.scaled(
        max_width,
        max_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
