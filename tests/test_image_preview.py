import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from pic_record_manager.image_preview import load_preview_pixmap


class ImagePreviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_loads_jpeg_as_bounded_qt_pixmap(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "sample.jpg"
            Image.new("RGB", (320, 180), "#336699").save(image_path, format="JPEG")

            pixmap = load_preview_pixmap(image_path, max_width=80, max_height=60)

            self.assertLessEqual(pixmap.width(), 80)
            self.assertLessEqual(pixmap.height(), 60)
            self.assertGreater(pixmap.width(), 0)
            self.assertGreater(pixmap.height(), 0)


if __name__ == "__main__":
    unittest.main()
