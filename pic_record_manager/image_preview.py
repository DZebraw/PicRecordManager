from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, QUrl, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink

from .media_types import is_video_file


def load_media_preview_pixmap(path: Path | str, max_width: int, max_height: int) -> QPixmap:
    media_path = Path(path)
    if is_video_file(media_path):
        return load_video_first_frame_pixmap(media_path, max_width, max_height)
    return load_preview_pixmap(media_path, max_width, max_height)


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


def load_video_first_frame_pixmap(path: Path | str, max_width: int, max_height: int, timeout_ms: int = 3000) -> QPixmap:
    """Load the first decodable video frame into a QPixmap scaled to fit the preview bounds."""

    video_path = Path(path)
    if QCoreApplication.instance() is None:
        raise OSError("A Qt application instance is required to load video previews")

    player = QMediaPlayer()
    sink = QVideoSink()
    player.setVideoSink(sink)
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    result = {"pixmap": QPixmap(), "error": ""}

    def finish() -> None:
        if loop.isRunning():
            loop.quit()

    def handle_frame(frame) -> None:
        if not frame.isValid():
            return
        image = frame.toImage()
        if image.isNull():
            return
        result["pixmap"] = QPixmap.fromImage(image.copy())
        player.stop()
        finish()

    def handle_error(*args) -> None:
        if args:
            result["error"] = str(args[-1])
        player.stop()
        finish()

    sink.videoFrameChanged.connect(handle_frame)
    player.errorOccurred.connect(handle_error)
    timer.timeout.connect(finish)
    player.setSource(QUrl.fromLocalFile(str(video_path.resolve())))
    timer.start(timeout_ms)
    player.play()
    loop.exec()
    timer.stop()
    player.stop()

    pixmap = result["pixmap"]
    if pixmap.isNull():
        message = result["error"] or f"Unable to load video frame: {video_path}"
        raise OSError(message)
    return pixmap.scaled(
        max_width,
        max_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
