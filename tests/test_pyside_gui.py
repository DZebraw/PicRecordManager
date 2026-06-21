import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QPoint, QPointF, QEvent, QUrl, Qt
from PySide6.QtGui import QColor, QEnterEvent, QImage, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QWidget,
)

from pic_record_manager.gui import (
    BASE_FONT_POINT_SIZE,
    DETAIL_IMAGE_SLIDE_OFFSET,
    FONT_FAMILY,
    TRANSITION_ANIMATION_MS,
    ArchiveWindow,
    PhotoCard,
)


class PySideGuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_uses_warm_window_and_renders_without_theme_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            self.assertEqual("#f5e3b6", window.palette().window().color().name())
            self.assertEqual(4, len(window.albums))

            window.close()

    def test_window_uses_end_field_icon_from_theme_for_taskbar(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            icon = workspace / "Themes" / "Default" / "EndField.ico"
            icon.parent.mkdir(parents=True)
            icon.write_bytes((Path.cwd() / "Themes" / "Default" / "EndField.ico").read_bytes())

            with patch("pic_record_manager.gui.set_windows_app_user_model_id") as set_app_id:
                window = ArchiveWindow(workspace)

            self.assertEqual(icon, window.app_icon_path)
            self.assertFalse(window.windowIcon().isNull())
            self.assertFalse(self.app.windowIcon().isNull())
            set_app_id.assert_called_once()

            window.close()

    def test_window_loads_theme_background_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            theme_dir = workspace / "Themes" / "Default"
            theme_dir.mkdir(parents=True)
            Image.new("RGB", (32, 32), "#f0d090").save(theme_dir / "BackGround.jpg", format="JPEG")
            window = ArchiveWindow(workspace)
            self.assertFalse(window.background_pixmap.isNull())
            window.resize(360, 260)
            window.show()
            self.app.processEvents()

            rendered = QImage(window.size(), QImage.Format.Format_ARGB32)
            rendered.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rendered)
            window.render(painter, QPoint(0, 0))
            painter.end()
            background_pixel = rendered.pixelColor(300, 230)

            self.assertGreater(background_pixel.red(), 180)
            self.assertLess(background_pixel.red(), 220)
            self.assertGreater(background_pixel.green(), 150)
            self.assertLess(background_pixel.green(), 190)
            self.assertLess(background_pixel.blue(), 150)

            window.close()

    def test_window_darkens_theme_background_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            theme_dir = workspace / "Themes" / "Default"
            theme_dir.mkdir(parents=True)
            Image.new("RGB", (32, 32), "#f0d090").save(theme_dir / "BackGround.jpg", format="JPEG")
            window = ArchiveWindow(workspace)
            window.resize(360, 260)
            window.show()
            self.app.processEvents()

            rendered = QImage(window.size(), QImage.Format.Format_ARGB32)
            rendered.fill(QColor("#000000"))
            painter = QPainter(rendered)
            window.render(painter, QPoint(0, 0))
            painter.end()
            background_pixel = rendered.pixelColor(300, 230)

            self.assertLess(background_pixel.red(), 220)
            self.assertLess(background_pixel.green(), 190)
            self.assertLess(background_pixel.blue(), 150)

            window.close()

    def test_applies_polished_ui_font_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            self.assertEqual(FONT_FAMILY, window.font().family())
            self.assertEqual(BASE_FONT_POINT_SIZE, window.font().pointSize())
            self.assertIn("font-size: 15px", window.styleSheet())
            self.assertIn("font-weight: 700", window.styleSheet())

            window.close()

    def test_non_button_text_labels_use_blurred_text_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            labels = [
                label
                for label in window.findChildren(QLabel)
                if label.text().strip() and label.objectName() != "ImagePreview"
            ]
            self.assertGreater(len(labels), 0)
            for label in labels:
                effect = label.graphicsEffect()
                self.assertIsInstance(effect, QGraphicsDropShadowEffect)
                self.assertGreaterEqual(effect.blurRadius(), 8)
                self.assertEqual(2, effect.yOffset())
                self.assertEqual("#000000", label.property("textOutlineColor"))
                self.assertGreaterEqual(label.property("textOutlineWidth"), 1)

            window.close()

    def test_theme_surfaces_are_opaque_warm_white_with_black_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))
            style = window.styleSheet()

            self.assertNotIn("rgba(", style)
            self.assertNotIn("backdrop-filter", style)
            self.assertIn("background: #fff7df;", style)
            self.assertIn("color: #111111;", style)
            self.assertIn("border: 1px solid #9a7a28;", style)

            window.close()

    def test_settings_preferences_apply_text_and_theme_colors_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            window = ArchiveWindow(workspace)

            window.apply_theme_preferences("#223344", "#f8e8bb", 62)

            self.assertEqual("#223344", window.text_color)
            self.assertEqual("#f8e8bb", window.theme_color)
            self.assertEqual(62, window.background_brightness)
            self.assertIn("color: #223344;", window.styleSheet())
            self.assertIn("background: #f8e8bb;", window.styleSheet())
            preferences = json.loads((workspace / "data" / "preferences.json").read_text(encoding="utf-8"))
            self.assertEqual("#223344", preferences["text_color"])
            self.assertEqual("#f8e8bb", preferences["theme_color"])
            self.assertEqual(62, preferences["background_brightness"])

            window.close()

            reopened = ArchiveWindow(workspace)
            self.assertEqual("#223344", reopened.text_color)
            self.assertEqual("#f8e8bb", reopened.theme_color)
            self.assertEqual(62, reopened.background_brightness)
            self.assertIn("color: #223344;", reopened.styleSheet())
            self.assertIn("background: #f8e8bb;", reopened.styleSheet())

            reopened.close()

    def test_settings_dialog_exposes_font_and_theme_color_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            dialog = window._create_settings_dialog()
            text_input = dialog.findChild(QLineEdit, "SettingsTextColorInput")
            theme_input = dialog.findChild(QLineEdit, "SettingsThemeColorInput")
            brightness_slider = dialog.findChild(QSlider, "SettingsBackgroundBrightnessSlider")
            brightness_spin = dialog.findChild(QSpinBox, "SettingsBackgroundBrightnessSpinBox")

            self.assertIsNotNone(text_input)
            self.assertIsNotNone(theme_input)
            self.assertIsNotNone(brightness_slider)
            self.assertIsNotNone(brightness_spin)
            self.assertEqual("#111111", text_input.text())
            self.assertEqual("#fff1c7", theme_input.text())
            self.assertEqual(80, brightness_slider.value())
            self.assertEqual(80, brightness_spin.value())
            self.assertNotIn("恢复默认", [button.text() for button in dialog.findChildren(QPushButton)])

            dialog.close()
            window.close()

    def test_content_scroll_background_matches_page_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            self.assertEqual("ContentViewport", window.scroll.viewport().objectName())
            self.assertEqual("ContentWidget", window.content_widget.objectName())
            self.assertIn("QWidget#ContentViewport, QWidget#ContentWidget", window.styleSheet())
            self.assertIn("QFrame#Sidebar", window.styleSheet())
            self.assertIn("QFrame#MainPanel", window.styleSheet())
            self.assertIn("QWidget#ContentViewport, QWidget#ContentWidget {\n    background: transparent;", window.styleSheet())
            self.assertIn("QFrame#Sidebar {\n    background: transparent;", window.styleSheet())
            self.assertIn("QFrame#MainPanel {\n    background: transparent;", window.styleSheet())

            window.close()

    def test_main_background_is_not_split_into_two_large_shadowed_panels(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            self.assertIsNone(window.sidebar.graphicsEffect())
            self.assertIsNone(window.main_panel.graphicsEffect())

            window.close()

    def test_window_uses_frameless_chrome_with_drag_area(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            self.assertTrue(window.windowFlags() & window.FRAMELESS_WINDOW_FLAG)
            self.assertEqual(96, window.DRAG_REGION_HEIGHT)

            window.close()

    def test_custom_window_controls_exist_in_top_right(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            controls = [window.minimize_button, window.maximize_button, window.close_button]
            self.assertEqual(["WindowMinimizeButton", "WindowMaximizeButton", "WindowCloseButton"], [button.objectName() for button in controls])
            self.assertEqual(["最小化", "最大化", "关闭"], [button.accessibleName() for button in controls])
            self.assertFalse(any(button.property("interactiveMotion") for button in controls))
            self.assertFalse(any(hasattr(button, "hover_animation") for button in controls))

            window.close()

    def test_photo_cards_do_not_draw_outer_background_frame_or_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "card.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(window.selected_album_id, source, title="动画卡片")
            card = PhotoCard(photo, window.show_detail)

            self.assertFalse(card.property("previewGlow"))
            self.assertFalse(card.property("interactiveMotion"))
            self.assertIsNone(card.graphicsEffect())
            self.assertIsInstance(card.delete_button.graphicsEffect(), QGraphicsDropShadowEffect)
            self.assertIn("QFrame#PhotoCard {\n    background: transparent;", window.styleSheet())
            self.assertIn("QFrame#PhotoCardContainer {\n    background: #fff7df;", window.styleSheet())
            self.assertFalse(hasattr(card, "hover_animation"))

            card.deleteLater()
            window.close()

    def test_photo_card_title_and_date_text_have_black_outline(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "outlined-text.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(window.selected_album_id, source, title="描边标题")
            card = PhotoCard(photo, window.show_detail)

            self.assertEqual("#000000", card.title_label.property("textOutlineColor"))
            self.assertEqual("#000000", card.meta_label.property("textOutlineColor"))
            self.assertGreaterEqual(card.title_label.property("textOutlineWidth"), 1)
            self.assertGreaterEqual(card.meta_label.property("textOutlineWidth"), 1)

            card.deleteLater()
            window.close()

    def test_empty_photo_card_uses_theme_pic_ground_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            theme_dir = workspace / "Themes" / "Default"
            theme_dir.mkdir(parents=True)
            Image.new("RGB", (80, 60), "#20c060").save(theme_dir / "PicGround.png", format="PNG")
            window = ArchiveWindow(workspace)
            window.store.create_empty_photo(window.selected_album_id, title="无图档案")
            window.refresh()
            window.resize(1180, 740)
            window.show()
            self.app.processEvents()

            card = window.content_grid.itemAt(0).widget()
            preview = card.preview
            self.assertEqual("", preview.text())
            rendered = QImage(preview.size(), QImage.Format.Format_ARGB32)
            rendered.fill(QColor("#010203"))
            painter = QPainter(rendered)
            preview.render(painter, QPoint(0, 0))
            painter.end()
            center = rendered.pixelColor(preview.width() // 2, preview.height() // 2)

            self.assertGreater(center.green(), 120)
            self.assertLess(center.red(), 80)

            window.close()

    def test_detail_page_uses_left_to_right_slide_transition_for_enter_and_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "transition.jpg"
            Image.new("RGB", (640, 420), "#446688").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(window.selected_album_id, source, title="转场测试")

            window.show_detail(photo)

            self.assertEqual("enter", window.last_transition_direction)
            self.assertGreaterEqual(TRANSITION_ANIMATION_MS, 420)
            self.assertIsNone(window.detail_zoom_animation)
            self.assertEqual(TRANSITION_ANIMATION_MS, window.detail_slide_animation.duration())
            self.assertEqual(
                window.detail_slide_animation.endValue() - QPoint(DETAIL_IMAGE_SLIDE_OFFSET, 0),
                window.detail_slide_animation.startValue(),
            )
            self.assertEqual(2, window.detail_transition_animation.animationCount())
            self.assertTrue(
                all(
                    window.detail_transition_animation.animationAt(index).duration() == TRANSITION_ANIMATION_MS
                    for index in range(window.detail_transition_animation.animationCount())
                )
            )

            window.back_to_list()

            self.assertEqual("return", window.last_transition_direction)
            self.assertEqual(TRANSITION_ANIMATION_MS, window.detail_slide_animation.duration())
            self.assertEqual(
                window.detail_slide_animation.startValue() - QPoint(DETAIL_IMAGE_SLIDE_OFFSET, 0),
                window.detail_slide_animation.endValue(),
            )

            window.close()

    def test_closing_window_stops_pending_detail_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "transition-close.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(window.selected_album_id, source, title="关闭转场")

            window.show_detail(photo)
            window.back_to_list()
            self.assertIsNotNone(window.detail_transition_animation)

            window.close()

            self.assertIsNone(window.detail_transition_animation)

    def test_detail_image_follows_mouse_with_inertial_card_tilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "tilt.jpg"
            Image.new("RGB", (640, 420), "#446688").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(window.selected_album_id, source, title="卡牌动态")

            window.show_detail(photo)
            window.show()
            QTest.qWait(TRANSITION_ANIMATION_MS + 40)
            window.detail_image.resize(520, 420)
            self.app.processEvents()

            QTest.mouseMove(window.detail_image, QPoint(window.detail_image.width() - 20, 24))
            self.app.processEvents()

            self.assertTrue(window.detail_image.tilt_motion_enabled)
            self.assertGreater(window.detail_image.target_offset.x(), 0)
            self.assertLess(window.detail_image.target_offset.y(), 0)
            self.assertGreater(window.detail_image.target_tilt.y(), 0)
            self.assertGreater(window.detail_image.target_tilt.x(), 0)
            self.assertLess(window.detail_image.current_offset.x(), window.detail_image.target_offset.x())

            before = window.detail_image.current_offset.x()
            window.detail_image.advance_tilt_frame()
            self.assertGreater(window.detail_image.current_offset.x(), before)

            window.detail_image.leaveEvent(QEvent(QEvent.Type.Leave))
            self.assertEqual(QPointF(0, 0), window.detail_image.target_offset)
            self.assertEqual(QPointF(0, 0), window.detail_image.target_tilt)

            window.close()

    def test_imported_jpeg_is_rendered_as_preview_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "source.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            window.store.import_photo(window.selected_album_id, source, title="预览测试")

            window.refresh()

            self.assertGreater(window.content_grid.count(), 0)

            window.close()

    def test_primary_action_creates_empty_archive_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            button_texts = [button.text() for button in window.findChildren(QPushButton)]
            self.assertIn("新建档案", button_texts)
            self.assertNotIn("导入照片", button_texts)

            window.create_empty_archive()

            self.assertEqual(1, window.current_page.total)
            card = window.content_grid.itemAt(0).widget()
            self.assertEqual("未命名档案", card.photo.title)
            self.assertEqual("空档案", card.preview.text())

            window.close()

    def test_detail_page_imports_multiple_images_and_switches_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            first = workspace / "first.jpg"
            second = workspace / "second.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(first, format="JPEG")
            Image.new("RGB", (320, 180), "#aa8844").save(second, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.create_empty_photo(window.selected_album_id, title="空档案")

            window.show_detail(photo)

            self.assertEqual("0 / 0", window.detail_image_counter.text())
            self.assertEqual("导入图片", window.detail_import_images_button.text())
            self.assertFalse(window.detail_prev_image_button.isEnabled())
            self.assertFalse(window.detail_next_image_button.isEnabled())
            labels = [label.text() for label in window.detail_page.findChildren(QLabel)]
            self.assertNotIn("档案文字", labels)
            self.assertNotIn("书签", labels)
            self.assertNotIn("备注", labels)
            self.assertIn("记录", labels)
            self.assertEqual(Qt.AlignmentFlag.AlignCenter, window.detail_record_label.alignment())
            self.assertEqual("DetailRecordLevelInput", window.detail_record_level.objectName())
            self.assertEqual("DetailResourceNoteInput", window.detail_resource_note.objectName())
            self.assertFalse(hasattr(window, "detail_album"))

            window.detail_images = window.store.add_photo_images(photo.id, [first, second])
            window._refresh_detail_image()

            self.assertEqual(2, len(window.detail_images))
            self.assertEqual(2, window.detail_image.stack_depth)
            self.assertEqual("1 / 2", window.detail_image_counter.text())
            self.assertTrue(window.detail_prev_image_button.isEnabled())
            self.assertTrue(window.detail_next_image_button.isEnabled())

            window.detail_record.setPlainText("shared archive record")
            window.detail_resource_note.setPlainText("first resource note")
            window.next_detail_image()

            self.assertEqual(1, window.detail_image_index)
            self.assertEqual("2 / 2", window.detail_image_counter.text())
            self.assertEqual("shared archive record", window.detail_record.toPlainText())
            self.assertEqual("", window.detail_resource_note.toPlainText())
            self.assertTrue(window.detail_image.page_transition_active)
            self.assertEqual("next", window.detail_image.page_transition_direction)
            self.assertTrue(window.detail_prev_image_button.isEnabled())
            self.assertTrue(window.detail_next_image_button.isEnabled())

            window.detail_resource_note.setPlainText("second resource note")
            window.next_detail_image()
            self.assertEqual(0, window.detail_image_index)
            self.assertEqual("1 / 2", window.detail_image_counter.text())
            self.assertEqual("shared archive record", window.detail_record.toPlainText())
            self.assertEqual("first resource note", window.detail_resource_note.toPlainText())
            self.assertEqual("next", window.detail_image.page_transition_direction)

            window.previous_detail_image()
            self.assertEqual(1, window.detail_image_index)
            self.assertEqual("2 / 2", window.detail_image_counter.text())
            self.assertEqual("shared archive record", window.detail_record.toPlainText())
            self.assertEqual("second resource note", window.detail_resource_note.toPlainText())
            self.assertEqual("previous", window.detail_image.page_transition_direction)

            window.close()

    def test_detail_text_fields_use_solid_warm_white_shadowed_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "source.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(window.selected_album_id, source, title="白色输入框")

            window.show_detail(photo)

            field_expectations = (
                (window.detail_title, "DetailTitleInput", 36, 10),
                (window.detail_display_date, "DetailDateInput", 36, 10),
                (window.detail_record_level, "DetailRecordLevelInput", 36, 10),
                (window.detail_record, "DetailRecordInput", 46, 14),
                (window.detail_resource_note, "DetailResourceNoteInput", 46, 14),
            )
            for field, object_name, blur_radius, y_offset in field_expectations:
                self.assertEqual(object_name, field.objectName())
                effect = field.graphicsEffect()
                self.assertIsInstance(effect, QGraphicsDropShadowEffect)
                self.assertGreaterEqual(effect.blurRadius(), blur_radius)
                self.assertEqual(y_offset, effect.yOffset())

            self.assertIn("QLineEdit#DetailTitleInput", window.styleSheet())
            self.assertIn("QLineEdit#DetailDateInput", window.styleSheet())
            self.assertIn("QLineEdit#DetailRecordLevelInput", window.styleSheet())
            self.assertIn("QTextEdit#DetailRecordInput", window.styleSheet())
            self.assertIn("QTextEdit#DetailResourceNoteInput", window.styleSheet())
            self.assertIn("background: #fff7df;", window.styleSheet())

            window.close()

    def test_detail_editor_panel_has_no_background_frame_or_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "source.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(window.selected_album_id, source, title="透明详情面板")

            window.show_detail(photo)

            self.assertEqual("DetailEditorPanel", window.detail_editor.objectName())
            self.assertIsNone(window.detail_editor.graphicsEffect())
            self.assertIn("QFrame#DetailEditorPanel", window.styleSheet())
            self.assertIn("QFrame#DetailEditorPanel {\n    background: transparent;", window.styleSheet())
            self.assertIn("QFrame#PhotoCard {\n    background: transparent;", window.styleSheet())

            window.close()

    def test_framed_controls_have_drop_shadows(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            widgets = [
                window.search_entry,
                window.findChildren(QPushButton)[0],
            ]
            for widget in widgets:
                self.assertIsInstance(widget.graphicsEffect(), QGraphicsDropShadowEffect)

            window.close()

    def test_multi_image_archive_cards_show_stacked_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            first = workspace / "stack-first.jpg"
            second = workspace / "stack-second.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(first, format="JPEG")
            Image.new("RGB", (320, 180), "#aa8844").save(second, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.create_empty_photo(window.selected_album_id, title="多图档案")
            window.store.add_photo_images(photo.id, [first, second])

            window.refresh()

            card = window.content_grid.itemAt(0).widget()
            self.assertEqual(2, card.preview.stack_depth)
            self.assertEqual("", card.preview.text())

            window.close()

    def test_main_preview_uses_complete_image_fit_without_cropping(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "wide.jpg"
            Image.new("RGB", (1200, 260), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            window.store.import_photo(window.selected_album_id, source, title="完整预览")

            window.refresh()

            card = window.content_grid.itemAt(0).widget()
            self.assertEqual(Qt.AspectRatioMode.KeepAspectRatio, card.preview.scale_mode)

            window.close()

    def test_preview_grid_is_fixed_two_by_three_without_scroll_and_resizes_with_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            window = ArchiveWindow(workspace)
            for index in range(9):
                source = workspace / f"grid-{index}.jpg"
                Image.new("RGB", (320, 180), f"#{40 + index:02x}88aa").save(source, format="JPEG")
                window.store.import_photo(window.selected_album_id, source, title=f"Fixed card {index + 1}")
            window.refresh()
            window.resize(1180, 740)
            window.show()
            self.app.processEvents()

            positions = [(row, column) for row in range(2) for column in range(3)]
            titles = [window.content_grid.itemAtPosition(row, column).widget().photo.title for row, column in positions]
            self.assertEqual([f"Fixed card {index + 1}" for index in range(6)], titles)
            self.assertIsNone(window.content_grid.itemAtPosition(2, 0))
            self.assertEqual(6, window.per_page)
            initial_sizes = []
            for row, column in positions:
                card = window.content_grid.itemAtPosition(row, column).widget()
                initial_sizes.append(card.size())
                self.assertEqual(Qt.AlignmentFlag.AlignCenter, card.title_label.alignment())
                self.assertIn("QLabel#CardTitle", window.styleSheet())
                self.assertIn("font-size: 18px", window.styleSheet())
            self.assertEqual(1, len({(size.width(), size.height()) for size in initial_sizes}))
            self.assertEqual(0, window.scroll.verticalScrollBar().maximum())
            self.assertEqual(0, window.scroll.horizontalScrollBar().maximum())

            window.resize(1380, 860)
            self.app.processEvents()

            grown_card = window.content_grid.itemAtPosition(0, 0).widget()
            self.assertGreater(grown_card.width(), initial_sizes[0].width())
            self.assertGreater(grown_card.height(), initial_sizes[0].height())
            self.assertEqual(0, window.scroll.verticalScrollBar().maximum())
            self.assertEqual(0, window.scroll.horizontalScrollBar().maximum())

            window.close()

    def test_toolbar_does_not_offer_adaptive_view_switching(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            button_texts = [button.text() for button in window.findChildren(QPushButton)]
            self.assertNotIn("切换视图", button_texts)

            window.close()

    def test_double_clicking_album_button_renames_bookmark_inline(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))
            window.show()
            self.app.processEvents()
            album_item = window.album_item_widgets[0]

            QTest.mouseDClick(album_item.select_button, Qt.MouseButton.LeftButton)
            self.app.processEvents()

            self.assertTrue(album_item.rename_editor.isVisible())
            self.assertEqual("书签 1", album_item.rename_editor.text())

            album_item.rename_editor.setText("资料相册")
            QTest.keyClick(album_item.rename_editor, Qt.Key.Key_Return)
            self.app.processEvents()

            self.assertEqual("资料相册", window.store.list_albums()[0].name)
            self.assertEqual("1. 资料相册", window.album_item_widgets[0].select_button.text())

            window.close()

    def test_album_rename_editor_saves_when_focus_leaves(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))
            window.show()
            self.app.processEvents()
            album_item = window.album_item_widgets[0]

            album_item.begin_rename()
            album_item.rename_editor.setText("失焦保存")
            window.search_entry.setFocus()
            self.app.processEvents()

            self.assertEqual("失焦保存", window.store.list_albums()[0].name)

            window.close()

    def test_preview_card_delete_button_removes_photo_and_refreshes_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "delete-photo.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(window.selected_album_id, source, title="删除照片")
            window.refresh()
            card = window.content_grid.itemAt(0).widget()

            self.assertEqual("PhotoDeleteButton", card.delete_button.objectName())
            with patch(
                "pic_record_manager.gui.QMessageBox.question",
                return_value=QMessageBox.StandardButton.No,
            ) as question:
                card.delete_button.click()

            question.assert_called_once()
            self.assertEqual(photo.id, window.store.get_photo(photo.id).id)
            self.assertEqual(1, window.current_page.total)

            with patch(
                "pic_record_manager.gui.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ) as question:
                card.delete_button.click()

            with self.assertRaises(KeyError):
                window.store.get_photo(photo.id)
            question.assert_called_once()
            self.assertEqual(0, window.current_page.total)

            window.close()

    def test_delete_buttons_overlay_without_occupying_layout_space(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "overlay-delete.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            window.store.import_photo(window.selected_album_id, source, title="Overlay delete")
            window.refresh()
            window.resize(1180, 740)
            window.show()
            self.app.processEvents()

            card = window.content_grid.itemAt(0).widget()
            self.assertEqual(card, card.delete_button.parent())
            self.assertIs(card.preview, card.layout().itemAt(0).widget())
            preview_rect = card.preview_content_rect()
            expected_x = card.preview.x() + int(preview_rect.right()) - card.delete_button.width()
            expected_y = card.preview.y() + int(preview_rect.top()) - 6
            self.assertEqual(expected_x, card.delete_button.x())
            self.assertEqual(expected_y, card.delete_button.y())
            self.assertLess(card.delete_button.x(), card.width() - card.delete_button.width() - 12)

            album_item = window.album_item_widgets[0]
            self.assertEqual(album_item, album_item.delete_button.parent())
            self.assertEqual(album_item.width(), album_item.select_button.width())
            self.assertGreaterEqual(
                album_item.delete_button.x(),
                album_item.width() - album_item.delete_button.width() - 6,
            )
            self.assertLessEqual(album_item.delete_button.y(), 6)

            window.close()

    def test_album_delete_button_removes_bookmark_and_selects_remaining_album(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "delete-album.jpg"
            Image.new("RGB", (320, 180), "#aa8844").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            album = window.store.create_album("删除书签")
            photo = window.store.import_photo(album.id, source, title="跟随书签删除")
            window.selected_album_id = album.id
            window.refresh()
            album_item = next(item for item in window.album_item_widgets if item.album.id == album.id)

            self.assertEqual("AlbumDeleteButton", album_item.delete_button.objectName())
            with patch(
                "pic_record_manager.gui.QMessageBox.question",
                return_value=QMessageBox.StandardButton.No,
            ) as question:
                album_item.delete_button.click()

            question.assert_called_once()
            self.assertIn(album.id, [item.id for item in window.store.list_albums()])
            self.assertEqual(photo.id, window.store.get_photo(photo.id).id)

            with patch(
                "pic_record_manager.gui.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ) as question:
                album_item.delete_button.click()

            self.assertNotIn(album.id, [item.id for item in window.store.list_albums()])
            with self.assertRaises(KeyError):
                window.store.get_photo(photo.id)
            question.assert_called_once()
            self.assertNotEqual(album.id, window.selected_album_id)

            window.close()

    def test_detail_import_starts_worker_and_enters_busy_state(self):
        class FakeSignal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

        class FakeThread:
            def __init__(self):
                self.started = FakeSignal()
                self.finished = FakeSignal()
                self.started_called = False

            def start(self):
                self.started_called = True

            def quit(self):
                pass

            def deleteLater(self):
                pass

        class FakeWorker:
            instances = []

            def __init__(self, database_path, media_dir, photo_id, source_paths):
                self.database_path = database_path
                self.media_dir = media_dir
                self.photo_id = photo_id
                self.source_paths = source_paths
                self.finished = FakeSignal()
                self.failed = FakeSignal()
                FakeWorker.instances.append(self)

            def moveToThread(self, thread):
                self.thread = thread

            def run(self):
                pass

            def deleteLater(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "async.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.create_empty_photo(window.selected_album_id, title="Async")
            window.show_detail(photo)

            with patch(
                "pic_record_manager.gui.QFileDialog.getOpenFileNames",
                return_value=([str(source)], ""),
            ) as file_dialog, patch("pic_record_manager.gui.QThread", FakeThread), patch(
                "pic_record_manager.gui.ImageImportWorker",
                FakeWorker,
            ):
                window.import_images_to_detail()

            self.assertIn("*.mp4", file_dialog.call_args.args[3])
            self.assertEqual(1, len(FakeWorker.instances))
            worker = FakeWorker.instances[0]
            self.assertEqual(photo.id, worker.photo_id)
            self.assertEqual([source], worker.source_paths)
            self.assertFalse(window.detail_import_images_button.isEnabled())
            self.assertIn("导入", window.status_label.text())
            self.assertTrue(window.image_import_thread.started_called)

            window.close()

    def test_detail_page_uses_video_first_frame_preview_for_imported_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            video = workspace / "clip.mp4"
            video.write_bytes(b"fake mp4 bytes")
            first_frame = QPixmap(320, 180)
            first_frame.fill(QColor("#cc2020"))
            window = ArchiveWindow(workspace)
            photo = window.store.create_empty_photo(window.selected_album_id, title="视频档案")
            window.store.add_photo_images(photo.id, [video])

            with patch("pic_record_manager.gui.load_media_preview_pixmap", return_value=first_frame) as load_preview:
                window.show_detail(window.store.get_photo(photo.id))
            window.detail_image.resize(520, 420)
            window.show()
            self.app.processEvents()

            rendered = QImage(window.detail_image.size(), QImage.Format.Format_ARGB32)
            rendered.fill(QColor("#010203"))
            painter = QPainter(rendered)
            window.detail_image.render(painter, QPoint(0, 0))
            painter.end()
            center = rendered.pixelColor(window.detail_image.width() // 2, window.detail_image.height() // 2 - 90)

            self.assertEqual("1 / 1", window.detail_image_counter.text())
            load_preview.assert_called()
            self.assertGreater(center.red(), 160)
            self.assertGreater(center.red(), center.green())

            window.close()

    def test_detail_video_play_button_overlays_current_video_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            video = workspace / "clip.mp4"
            video.write_bytes(b"fake mp4 bytes")
            image = workspace / "still.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(image, format="JPEG")
            first_frame = QPixmap(320, 180)
            first_frame.fill(QColor("#cc2020"))
            window = ArchiveWindow(workspace)
            photo = window.store.create_empty_photo(window.selected_album_id, title="Video overlay")
            window.store.add_photo_images(photo.id, [video, image])

            with patch("pic_record_manager.gui.load_media_preview_pixmap", return_value=first_frame):
                window.show_detail(window.store.get_photo(photo.id))
            window.detail_image.resize(520, 420)
            window.show()
            self.app.processEvents()
            window._position_detail_video_play_button()

            button = window.detail_video_play_button
            self.assertEqual("VideoPlayButton", button.objectName())
            self.assertTrue(button.isVisible())
            self.assertIs(window.detail_image, button.parent())
            self.assertLessEqual(abs(button.geometry().center().x() - window.detail_image.rect().center().x()), 1)
            self.assertLessEqual(abs(button.geometry().center().y() - window.detail_image.rect().center().y()), 1)

            with patch("pic_record_manager.gui.load_media_preview_pixmap", return_value=first_frame):
                window.next_detail_image()
            self.assertFalse(button.isVisible())

            window.close()

    def test_detail_video_play_button_hides_when_archive_has_no_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            window = ArchiveWindow(workspace)
            photo = window.store.create_empty_photo(window.selected_album_id, title="Empty")

            window.show_detail(photo)

            self.assertFalse(window.detail_video_play_button.isVisible())

            window.close()

    def test_video_play_button_plays_inside_detail_preview_area(self):
        class FakeSignal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

            def emit(self, *args):
                for callback in self.callbacks:
                    callback(*args)

        class FakeMediaPlayer:
            instances = []

            def __init__(self, parent=None):
                self.parent = parent
                self.video_output = None
                self.audio_output = None
                self.source = QUrl()
                self.play_called = False
                self.pause_called = False
                self.stop_called = False
                self.positions = []
                self.positionChanged = FakeSignal()
                self.durationChanged = FakeSignal()
                self.playbackStateChanged = FakeSignal()
                self.__class__.instances.append(self)

            def setVideoOutput(self, output):
                self.video_output = output

            def setAudioOutput(self, output):
                self.audio_output = output

            def setSource(self, source):
                self.source = source

            def play(self):
                self.play_called = True

            def pause(self):
                self.pause_called = True

            def stop(self):
                self.stop_called = True

            def setPosition(self, position):
                self.positions.append(position)

        class FakeAudioOutput:
            def __init__(self, parent=None):
                self.parent = parent

        class FakeVideoWidget(QWidget):
            instances = []

            def __init__(self, parent=None):
                super().__init__(parent)
                self.__class__.instances.append(self)

        class FakeTimer:
            callbacks = []

            @staticmethod
            def singleShot(interval, callback):
                FakeTimer.callbacks.append((interval, callback))

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            video = workspace / "clip.mp4"
            video.write_bytes(b"fake mp4 bytes")
            image = workspace / "still.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(image, format="JPEG")
            first_frame = QPixmap(320, 180)
            first_frame.fill(QColor("#cc2020"))
            window = ArchiveWindow(workspace)
            photo = window.store.create_empty_photo(window.selected_album_id, title="Inline video")
            window.store.add_photo_images(photo.id, [video, image])

            with patch("pic_record_manager.gui.QMediaPlayer", FakeMediaPlayer), patch(
                "pic_record_manager.gui.QAudioOutput",
                FakeAudioOutput,
            ), patch("pic_record_manager.gui.QVideoWidget", FakeVideoWidget), patch(
                "pic_record_manager.gui.QTimer",
                FakeTimer,
                create=True,
            ), patch(
                "pic_record_manager.gui.load_media_preview_pixmap",
                return_value=first_frame,
            ):
                window.show_detail(window.store.get_photo(photo.id))
                window.detail_image.resize(520, 420)
                window.show()
                self.app.processEvents()
                window.detail_video_play_button.click()

                player = FakeMediaPlayer.instances[0]
                video_widget = FakeVideoWidget.instances[0]
                self.assertEqual(1, len(FakeTimer.callbacks))
                self.assertEqual(0, FakeTimer.callbacks[0][0])
                self.assertFalse(player.play_called)
                self.assertFalse(video_widget.isVisible())

                FakeTimer.callbacks[0][1]()

                self.assertEqual(window.detail_images[0].stored_path.resolve(), Path(player.source.toLocalFile()).resolve())
                self.assertIs(video_widget, player.video_output)
                self.assertTrue(player.play_called)
                self.assertTrue(video_widget.isVisible())
                self.assertFalse(window.detail_video_play_button.isVisible())
                self.assertTrue(window.detail_video_controls.isVisible())
                self.assertEqual("DetailVideoControls", window.detail_video_controls.objectName())
                self.assertEqual("DetailVideoPauseButton", window.detail_video_pause_button.objectName())
                self.assertEqual("DetailVideoProgressSlider", window.detail_video_progress.objectName())
                self.assertEqual(
                    window.detail_image.height() - window.detail_video_controls.height() - 14,
                    window.detail_video_controls.y(),
                )
                self.assertEqual(0, video_widget.geometry().x())
                self.assertEqual(0, video_widget.geometry().y())
                self.assertEqual(window.detail_image.width(), video_widget.geometry().width())
                self.assertLess(video_widget.geometry().bottom(), window.detail_video_controls.y())

                player.durationChanged.emit(90000)
                player.positionChanged.emit(30000)

                self.assertEqual(0, window.detail_video_progress.minimum())
                self.assertEqual(90000, window.detail_video_progress.maximum())
                self.assertEqual(30000, window.detail_video_progress.value())

                window.detail_video_pause_button.click()

                self.assertTrue(player.pause_called)
                self.assertEqual(">", window.detail_video_pause_button.text())

                window.detail_video_pause_button.click()

                self.assertTrue(player.play_called)
                self.assertEqual("||", window.detail_video_pause_button.text())

                window.detail_video_progress.setValue(45000)
                window.detail_video_progress.sliderReleased.emit()

                self.assertEqual([45000], player.positions)

                window.next_detail_image()

                self.assertTrue(player.stop_called)
                self.assertFalse(video_widget.isVisible())
                self.assertFalse(window.detail_video_controls.isVisible())

            window.close()

    def test_preview_opens_detail_page_and_saves_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "detail.jpg"
            Image.new("RGB", (420, 260), "#aa8844").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(
                window.selected_album_id,
                source,
                title="Original Title",
                description="Original note",
            )

            window.show_detail(photo)
            self.assertEqual("Original note", window.detail_record.toPlainText())
            window.detail_title.setText("Updated Title")
            window.detail_display_date.setText("2026-06-17")
            window.detail_record_level.setText("A")
            window.detail_record.setPlainText("Updated shared record")
            window.detail_resource_note.setPlainText("Updated resource note")
            window.save_detail()

            updated = window.store.get_photo(photo.id)
            self.assertEqual("Updated Title", updated.title)
            self.assertEqual("2026-06-17", updated.display_date)
            self.assertEqual("A", updated.record_level)
            self.assertEqual("Updated shared record", updated.description)
            self.assertEqual("Updated resource note", window.store.list_photo_images(photo.id)[0].record)
            self.assertEqual(photo.id, window.detail_photo_id)
            detail_photo = window.store.get_photo(photo.id)
            self.assertEqual("2026-06-17", detail_photo.display_date)
            window.back_to_list()
            window._complete_back_to_list(window.stack.currentWidget())
            self.assertIsNone(window.detail_photo_id)
            card = window.content_grid.itemAt(0).widget()
            self.assertEqual("书签 1 · 2026-06-17", card.meta_label.text())

            window.close()

    def test_reopening_detail_page_after_return_does_not_use_deleted_record_editor(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "reopen.jpg"
            Image.new("RGB", (420, 260), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(window.selected_album_id, source, title="Reopen")

            window.show_detail(photo)
            deleted_detail_page = window.detail_page
            window._complete_back_to_list(deleted_detail_page)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

            window.show_detail(photo)

            self.assertEqual("1 / 1", window.detail_image_counter.text())
            self.assertTrue(window.detail_record.isEnabled())

            window.close()


if __name__ == "__main__":
    unittest.main()
