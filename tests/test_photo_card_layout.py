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
from pic_record_manager.theme_assets import ThemeAssets


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

    def test_stacked_preview_reserves_right_and_bottom_room_for_rear_images(self):
        preview = StackedImagePreview()
        preview.resize(260, 180)
        preview.setStyleSheet("background: #010203; border: none;")
        pixmaps = []
        for color in ("#4488aa", "#aa8844", "#66aa44"):
            pixmap = QPixmap(200, 140)
            pixmap.fill(QColor(color))
            pixmaps.append(pixmap)
        preview.set_preview_pixmaps(pixmaps)

        content_rect = preview.content_rect()
        self.assertLess(content_rect.right(), preview.width() - 2)
        self.assertLess(content_rect.bottom(), preview.height() - 2)

        background = QColor("#010203")
        rendered = QImage(preview.size(), QImage.Format.Format_ARGB32)
        rendered.fill(background)
        painter = QPainter(rendered)
        preview.render(painter, QPoint(0, 0))
        painter.end()

        edge_pixels = 0
        for x in range(rendered.width()):
            for y in range(rendered.height() - 2, rendered.height()):
                if rendered.pixelColor(x, y) != background:
                    edge_pixels += 1
        for y in range(rendered.height()):
            for x in range(rendered.width() - 2, rendered.width()):
                if rendered.pixelColor(x, y) != background:
                    edge_pixels += 1

        self.assertEqual(0, edge_pixels)

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

    def test_detail_preview_feathers_photo_edges_into_pic_ground(self):
        with tempfile.TemporaryDirectory() as tmp:
            ground_dir = Path(tmp) / "Themes" / "Default"
            ground_dir.mkdir(parents=True)
            ground = QPixmap(64, 64)
            ground.fill(QColor("#20c060"))
            self.assertTrue(ground.save(str(ground_dir / "PicGround.png")))

            preview = TiltImagePreview(theme=ThemeAssets(Path(tmp)))
            preview.resize(360, 360)
            preview.setStyleSheet("background: #010203; border: none;")
            pixmap = QPixmap(200, 200)
            pixmap.fill(QColor("#cc2020"))
            preview.set_preview_stack([pixmap])

            rendered = QImage(preview.size(), QImage.Format.Format_ARGB32)
            rendered.fill(QColor("#010203"))
            painter = QPainter(rendered)
            preview.render(painter, QPoint(0, 0))
            painter.end()

            center = rendered.pixelColor(180, 180)
            edge = rendered.pixelColor(60, 180)

            self.assertGreater(center.red(), 180)
            self.assertLess(center.green(), 80)
            self.assertGreater(edge.green(), center.green() + 20)
            self.assertLess(edge.red(), center.red())

    def test_empty_stacked_preview_uses_pic_ground_as_default_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            ground_dir = Path(tmp) / "Themes" / "Default"
            ground_dir.mkdir(parents=True)
            ground = QPixmap(80, 60)
            ground.fill(QColor("#20c060"))
            self.assertTrue(ground.save(str(ground_dir / "PicGround.png")))

            preview = StackedImagePreview(theme=ThemeAssets(Path(tmp)))
            preview.resize(260, 160)
            preview.setStyleSheet("background: #010203; border: none;")
            preview.set_preview_pixmaps([], empty_text="空档案")

            rendered = QImage(preview.size(), QImage.Format.Format_ARGB32)
            rendered.fill(QColor("#010203"))
            painter = QPainter(rendered)
            preview.render(painter, QPoint(0, 0))
            painter.end()

            center = rendered.pixelColor(preview.width() // 2, preview.height() // 2)

            self.assertGreater(center.green(), 120)
            self.assertLess(center.red(), 80)
            self.assertEqual("", preview.text())

    def test_detail_preview_does_not_draw_shadow_behind_photo_card(self):
        preview = TiltImagePreview()
        preview.resize(520, 420)
        preview.show()
        self.app.processEvents()
        preview.setStyleSheet("background: #010203; border: none;")
        pixmap = QPixmap(200, 200)
        pixmap.fill(QColor("#cc2020"))
        preview.set_preview_stack([pixmap])

        rendered = QImage(preview.size(), QImage.Format.Format_ARGB32)
        rendered.fill(QColor("#010203"))
        painter = QPainter(rendered)
        preview.render(painter, QPoint(0, 0))
        painter.end()

        background = QColor("#010203")
        for sample in (QPoint(preview.width() // 2, 395), QPoint(preview.width() // 2, 400), QPoint(preview.width() // 2, 408)):
            self.assertEqual(background.name(), rendered.pixelColor(sample).name())

    def test_detail_preview_stack_keeps_rear_images_inside_widget_bounds(self):
        preview = TiltImagePreview()
        preview.resize(520, 700)
        preview.setStyleSheet("background: #010203; border: none;")
        pixmaps = []
        for color in ("#4488aa", "#aa8844", "#66aa44"):
            pixmap = QPixmap(260, 340)
            pixmap.fill(QColor(color))
            pixmaps.append(pixmap)
        preview.set_preview_stack(pixmaps)

        background = QColor("#010203")
        rendered = QImage(preview.size(), QImage.Format.Format_ARGB32)
        rendered.fill(background)
        painter = QPainter(rendered)
        preview.render(painter, QPoint(0, 0))
        painter.end()

        right_edge_painted_pixels = 0
        for y in range(rendered.height()):
            for x in range(rendered.width() - 2, rendered.width()):
                if rendered.pixelColor(x, y) != background:
                    right_edge_painted_pixels += 1

        self.assertEqual(0, right_edge_painted_pixels)


if __name__ == "__main__":
    unittest.main()
