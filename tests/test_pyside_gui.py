import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QPoint, QPointF, QEvent, Qt
from PySide6.QtGui import QEnterEvent, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QLabel, QMessageBox, QPushButton

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

    def test_uses_dark_window_and_renders_without_theme_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            self.assertEqual("#0f172a", window.palette().window().color().name())
            self.assertEqual(4, len(window.albums))

            window.close()

    def test_window_uses_dimmed_theme_background_when_available(self):
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
            rendered.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rendered)
            window.render(painter, QPoint(0, 0))
            painter.end()
            background_pixel = rendered.pixelColor(300, 10)

            self.assertGreater(background_pixel.red(), 80)
            self.assertLess(background_pixel.red(), 220)
            self.assertLess(background_pixel.green(), 190)
            self.assertLess(background_pixel.blue(), 140)

            window.close()

    def test_applies_polished_ui_font_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            self.assertEqual(FONT_FAMILY, window.font().family())
            self.assertEqual(BASE_FONT_POINT_SIZE, window.font().pointSize())
            self.assertIn("font-size: 15px", window.styleSheet())

            window.close()

    def test_content_scroll_background_matches_page_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = ArchiveWindow(Path(tmp))

            self.assertEqual("ContentViewport", window.scroll.viewport().objectName())
            self.assertEqual("ContentWidget", window.content_widget.objectName())
            self.assertIn("QWidget#ContentViewport, QWidget#ContentWidget", window.styleSheet())

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

    def test_photo_cards_show_obvious_glow_only_while_hovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "card.jpg"
            Image.new("RGB", (320, 180), "#4488aa").save(source, format="JPEG")
            window = ArchiveWindow(workspace)
            photo = window.store.import_photo(window.selected_album_id, source, title="动画卡片")
            card = PhotoCard(photo, window.show_detail)
            effect = card.graphicsEffect()

            self.assertFalse(card.property("previewGlow"))
            self.assertFalse(card.property("interactiveMotion"))
            self.assertIsInstance(effect, QGraphicsDropShadowEffect)
            self.assertEqual(0, effect.blurRadius())
            self.assertFalse(hasattr(card, "hover_animation"))

            card.enterEvent(QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
            self.assertTrue(card.property("previewGlow"))
            self.assertGreaterEqual(effect.blurRadius(), 32)

            card.leaveEvent(QEvent(QEvent.Type.Leave))
            self.assertFalse(card.property("previewGlow"))
            self.assertEqual(0, effect.blurRadius())

            card.deleteLater()
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
            self.assertFalse(hasattr(window, "detail_album"))

            window.detail_images = window.store.add_photo_images(photo.id, [first, second])
            window._refresh_detail_image()

            self.assertEqual(2, len(window.detail_images))
            self.assertEqual(2, window.detail_image.stack_depth)
            self.assertEqual("1 / 2", window.detail_image_counter.text())
            self.assertTrue(window.detail_prev_image_button.isEnabled())
            self.assertTrue(window.detail_next_image_button.isEnabled())

            window.detail_record.setPlainText("first image record")
            window.next_detail_image()

            self.assertEqual(1, window.detail_image_index)
            self.assertEqual("2 / 2", window.detail_image_counter.text())
            self.assertEqual("", window.detail_record.toPlainText())
            self.assertTrue(window.detail_image.page_transition_active)
            self.assertEqual("next", window.detail_image.page_transition_direction)
            self.assertTrue(window.detail_prev_image_button.isEnabled())
            self.assertTrue(window.detail_next_image_button.isEnabled())

            window.detail_record.setPlainText("second image record")
            window.next_detail_image()
            self.assertEqual(0, window.detail_image_index)
            self.assertEqual("1 / 2", window.detail_image_counter.text())
            self.assertEqual("first image record", window.detail_record.toPlainText())
            self.assertEqual("next", window.detail_image.page_transition_direction)

            window.previous_detail_image()
            self.assertEqual(1, window.detail_image_index)
            self.assertEqual("2 / 2", window.detail_image_counter.text())
            self.assertEqual("second image record", window.detail_record.toPlainText())
            self.assertEqual("previous", window.detail_image.page_transition_direction)

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

    def test_preview_grid_is_fixed_three_by_three_without_scroll_and_resizes_with_window(self):
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

            positions = [(row, column) for row in range(3) for column in range(3)]
            titles = [window.content_grid.itemAtPosition(row, column).widget().photo.title for row, column in positions]
            self.assertEqual([f"Fixed card {index + 1}" for index in range(9)], titles)
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
            self.assertGreaterEqual(card.delete_button.x(), card.width() - card.delete_button.width() - 12)
            self.assertLessEqual(card.delete_button.y(), 12)

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
            ), patch("pic_record_manager.gui.QThread", FakeThread), patch(
                "pic_record_manager.gui.ImageImportWorker",
                FakeWorker,
            ):
                window.import_images_to_detail()

            self.assertEqual(1, len(FakeWorker.instances))
            worker = FakeWorker.instances[0]
            self.assertEqual(photo.id, worker.photo_id)
            self.assertEqual([source], worker.source_paths)
            self.assertFalse(window.detail_import_images_button.isEnabled())
            self.assertIn("导入", window.status_label.text())
            self.assertTrue(window.image_import_thread.started_called)

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
            window.detail_record.setPlainText("Updated image record")
            window.save_detail()

            updated = window.store.get_photo(photo.id)
            self.assertEqual("Updated Title", updated.title)
            self.assertEqual("2026-06-17", updated.display_date)
            self.assertEqual("Original note", updated.description)
            self.assertEqual("Updated image record", window.store.list_photo_images(photo.id)[0].record)
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
