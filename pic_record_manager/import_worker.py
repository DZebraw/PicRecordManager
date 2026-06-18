from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .archive_store import ArchiveStore


class ImageImportWorker(QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, database_path: Path | str, media_dir: Path | str, photo_id: int, source_paths: list[Path | str]):
        super().__init__()
        self.database_path = Path(database_path)
        self.media_dir = Path(media_dir)
        self.photo_id = photo_id
        self.source_paths = [Path(path) for path in source_paths]

    def run(self) -> None:
        try:
            store = ArchiveStore(self.database_path, self.media_dir)
            images = store.add_photo_images(self.photo_id, self.source_paths)
        except Exception as exc:
            self.failed.emit(self.photo_id, str(exc))
            return
        self.finished.emit(self.photo_id, images)
