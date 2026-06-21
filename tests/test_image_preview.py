import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from pic_record_manager import image_preview
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

    def test_loads_mp4_preview_from_video_first_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "sample.mp4"
            video_path.write_bytes(b"fake mp4 bytes")
            frame = QPixmap(320, 180)
            frame.fill(QColor("#cc2020"))

            with patch.object(image_preview, "load_video_first_frame_pixmap", return_value=frame) as load_frame:
                pixmap = image_preview.load_media_preview_pixmap(video_path, max_width=80, max_height=60)

            load_frame.assert_called_once_with(video_path, 80, 60)
            self.assertEqual("#cc2020", pixmap.toImage().pixelColor(10, 10).name())


if __name__ == "__main__":
    unittest.main()
