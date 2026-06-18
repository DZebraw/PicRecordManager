import tempfile
import unittest
from pathlib import Path

from pic_record_manager.archive_store import ArchiveStore
from pic_record_manager.import_worker import ImageImportWorker


class ImageImportWorkerTest(unittest.TestCase):
    def test_run_emits_finished_with_imported_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ArchiveStore(root / "archive.db", root / "media")
            photo = store.create_empty_photo(store.list_albums()[0].id, title="worker import")
            first = root / "first.jpg"
            second = root / "second.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            worker = ImageImportWorker(store.database_path, store.media_dir, photo.id, [first, second])
            received = []

            worker.finished.connect(lambda photo_id, images: received.append((photo_id, images)))

            worker.run()

            self.assertEqual(1, len(received))
            self.assertEqual(photo.id, received[0][0])
            self.assertEqual([first.name, second.name], [image.original_name for image in received[0][1]])
            self.assertEqual(2, len(store.list_photo_images(photo.id)))

    def test_run_emits_failed_for_missing_source_without_importing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ArchiveStore(root / "archive.db", root / "media")
            photo = store.create_empty_photo(store.list_albums()[0].id, title="worker import")
            worker = ImageImportWorker(store.database_path, store.media_dir, photo.id, [root / "missing.jpg"])
            failures = []

            worker.failed.connect(lambda photo_id, message: failures.append((photo_id, message)))

            worker.run()

            self.assertEqual(1, len(failures))
            self.assertEqual(photo.id, failures[0][0])
            self.assertIn("missing.jpg", failures[0][1])
            self.assertEqual([], store.list_photo_images(photo.id))


if __name__ == "__main__":
    unittest.main()
