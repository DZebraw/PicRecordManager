import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from pic_record_manager.archive_store import Photo
from pic_record_manager.gui import PHOTO_CARD_HEIGHT, StackedImagePreview, TiltImagePreview, PhotoCard


class PhotoCardLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_preview_card_gives_more_height_to_image_without_changing_scaling(self):
        with tempfile.TemporaryDirectory() as tmp:
            photo = Photo(
                id=1,
                album_id=1,
                album_name="Album",
                title="A compact preview title",
                description="",
                original_name="missing.jpg",
                stored_path=Path(tmp) / "missing.jpg",
                created_at="2026-06-18",
                display_date="2026-06-18",
                image_count=1,
            )

            card = PhotoCard(photo, lambda _: None)

            self.assertEqual(PHOTO_CARD_HEIGHT, card.height())
            self.assertGreaterEqual(card.preview.minimumHeight(), 150)
            self.assertEqual(card.preview.minimumHeight(), card.preview.maximumHeight())
            self.assertLessEqual(card.title_label.maximumHeight(), 30)
            self.assertLessEqual(card.meta_label.maximumHeight(), 16)
            self.assertLessEqual(card.layout().spacing(), 3)
            self.assertEqual(Qt.AspectRatioMode.KeepAspectRatio, card.preview.scale_mode)

            card.deleteLater()

    def test_stacked_preview_does_not_clip_portrait_stack_at_top_edge(self):
        preview = StackedImagePreview()
        preview.resize(260, 180)
        pixmap = QPixmap(90, 120)
        pixmap.fill(QColor("#d8cbb1"))
        preview.set_preview_pixmaps([pixmap, pixmap, pixmap])

        rendered = QImage(preview.size(), QImage.Format.Format_ARGB32)
        rendered.fill(QColor("#010203"))
        painter = QPainter(rendered)
        preview.render(painter, QPoint(0, 0))
        painter.end()

        top_edge_image_pixels = 0
        for y in range(2):
            for x in range(rendered.width()):
                color = rendered.pixelColor(x, y)
                if (
                    abs(color.red() - 216) <= 3
                    and abs(color.green() - 203) <= 3
                    and abs(color.blue() - 177) <= 3
                ):
                    top_edge_image_pixels += 1

        self.assertEqual(0, top_edge_image_pixels)

    def test_detail_preview_renders_image_near_widget_center(self):
        preview = TiltImagePreview()
        preview.resize(520, 420)
        pixmap = QPixmap(180, 220)
        pixmap.fill(QColor("#4488aa"))
        preview.set_preview_stack([pixmap])

        rendered = QImage(preview.size(), QImage.Format.Format_ARGB32)
        rendered.fill(QColor("#010203"))
        painter = QPainter(rendered)
        preview.render(painter, QPoint(0, 0))
        painter.end()

        blue_pixels = []
        for y in range(rendered.height()):
            for x in range(rendered.width()):
                color = rendered.pixelColor(x, y)
                if (
                    abs(color.red() - 68) <= 3
                    and abs(color.green() - 136) <= 3
                    and abs(color.blue() - 170) <= 3
                ):
                    blue_pixels.append((x, y))

        self.assertGreater(len(blue_pixels), 0)
        min_x = min(x for x, _ in blue_pixels)
        max_x = max(x for x, _ in blue_pixels)
        min_y = min(y for _, y in blue_pixels)
        max_y = max(y for _, y in blue_pixels)
        image_center_x = (min_x + max_x) / 2
        image_center_y = (min_y + max_y) / 2

        self.assertLess(abs(image_center_x - preview.width() / 2), 30)
        self.assertLess(abs(image_center_y - preview.height() / 2), 30)


if __name__ == "__main__":
    unittest.main()
