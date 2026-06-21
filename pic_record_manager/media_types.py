from __future__ import annotations

from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".gif", ".jpg", ".jpeg", ".bmp"}
VIDEO_EXTENSIONS = {".mp4"}

MEDIA_FILE_FILTER = (
    "媒体文件 (*.png *.gif *.jpg *.jpeg *.bmp *.mp4);;"
    "图片文件 (*.png *.gif *.jpg *.jpeg *.bmp);;"
    "视频文件 (*.mp4);;"
    "所有文件 (*.*)"
)


def is_image_file(path: Path | str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def is_video_file(path: Path | str) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS
