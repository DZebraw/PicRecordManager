from __future__ import annotations

import ctypes
import json
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QParallelAnimationGroup, QPropertyAnimation, QRectF, QSignalBlocker, QThread, QTimer, QSize, QUrl, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .archive_store import Album, ArchiveStore, Photo
from .import_worker import ImageImportWorker
from .image_preview import load_media_preview_pixmap
from .media_types import MEDIA_FILE_FILTER, is_video_file
from .theme_assets import ThemeAssets
from .ui_constants import (
    APP_TITLE,
    BASE_FONT_POINT_SIZE,
    COLOR_BG,
    COLOR_BG_GRADIENT_END,
    COLOR_BG_GRADIENT_START,
    COLOR_BORDER,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_SUCCESS_HOVER,
    COLOR_SURFACE,
    COLOR_SURFACE_2,
    COLOR_SURFACE_3,
    COLOR_TEXT,
    DETAIL_IMAGE_FINAL_SIZE,
    DETAIL_IMAGE_SLIDE_OFFSET,
    FONT_FAMILY,
    FONT_STACK,
    PHOTO_CARD_HEIGHT,
    PHOTO_CARD_META_HEIGHT,
    PHOTO_CARD_PREVIEW_HEIGHT,
    PHOTO_CARD_TITLE_HEIGHT,
    PHOTO_CARD_WIDTH,
    PHOTO_GRID_COLUMNS,
    PHOTO_GRID_ROWS,
    SIDEBAR_WIDTH,
    TRANSITION_ANIMATION_MS,
    WINDOW_SIZE,
)
from .ui_widgets import (
    AlbumItem,
    AnimatedButton,
    AnimatedFrame,
    OutlinedLabel,
    PhotoCard,
    PhotoRow,
    StackedImagePreview,
    TiltImagePreview,
    apply_surface_shadow,
    apply_text_shadow,
    photo_meta_text,
    set_photo_pixmap,
)


APP_USER_MODEL_ID = "PicRecordManager.EndField"
DEFAULT_BACKGROUND_BRIGHTNESS = 80
def set_windows_app_user_model_id() -> bool:
    if sys.platform != "win32":
        return False
    try:
        result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        return False
    return result == 0


class ArchiveWindow(QMainWindow):
    FRAMELESS_WINDOW_FLAG = Qt.WindowType.FramelessWindowHint
    DRAG_REGION_HEIGHT = 96

    def __init__(self, workspace: Path):
        super().__init__()
        self.workspace = workspace
        self.theme = ThemeAssets(workspace)
        self.preferences_path = self.workspace / "data" / "preferences.json"
        self.text_color, self.theme_color, self.background_brightness = self._load_theme_preferences()
        self.app_icon_path = self.theme.end_field_icon()
        background_path = self.theme.background_pixmap()
        self.background_pixmap = QPixmap(str(background_path)) if background_path else QPixmap()
        self.store = ArchiveStore(workspace / "data" / "archive.db", workspace / "data" / "media")
        self.albums: list[Album] = []
        self.selected_album_id: int | None = self.store.list_albums()[0].id
        self.page = 1
        self.per_page = PHOTO_GRID_COLUMNS * PHOTO_GRID_ROWS
        self.query = ""
        self.view_mode = "grid"
        self.current_page = None
        self.detail_photo_id: int | None = None
        self.album_item_widgets: list[AlbumItem] = []
        self.image_import_thread: QThread | None = None
        self.image_import_worker: ImageImportWorker | None = None
        self._pending_import_photo_id: int | None = None
        self._status_before_import = ""
        self.last_video_play_request_path: Path | None = None
        self._drag_offset: QPoint | None = None
        self.last_transition_direction: str | None = None
        self.detail_transition_animation: QParallelAnimationGroup | None = None
        self.detail_zoom_animation: QPropertyAnimation | None = None
        self.detail_slide_animation: QPropertyAnimation | None = None

        set_windows_app_user_model_id()
        self.setWindowTitle(APP_TITLE)
        self._apply_app_icon()
        self.resize(*WINDOW_SIZE)
        self.setMinimumSize(*WINDOW_SIZE)
        self.setObjectName("ArchiveWindow")
        self.setWindowFlag(self.FRAMELESS_WINDOW_FLAG, True)
        self.setFont(QFont(FONT_FAMILY, BASE_FONT_POINT_SIZE))
        self.setPalette(self._dark_palette())
        self.setStyleSheet(build_app_qss(self.text_color, self.theme_color))

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._build_list_page()
        self.refresh()

    def _apply_app_icon(self) -> None:
        if self.app_icon_path is None:
            return
        icon = QIcon(str(self.app_icon_path))
        if icon.isNull():
            return
        app = QApplication.instance()
        if app is not None:
            app.setWindowIcon(icon)
        self.setWindowIcon(icon)

    def paintEvent(self, event) -> None:
        if self.background_pixmap.isNull():
            return super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        scaled = self.background_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) / 2
        y = (self.height() - scaled.height()) / 2
        painter.drawPixmap(QRectF(x, y, scaled.width(), scaled.height()), scaled, QRectF(scaled.rect()))
        painter.fillRect(self.rect(), QColor(0, 0, 0, self._background_overlay_alpha()))
        painter.end()

    def closeEvent(self, event) -> None:
        self._stop_detail_video_playback()
        if self.detail_transition_animation is not None:
            self.detail_transition_animation.stop()
            self.detail_transition_animation = None
        self.detail_zoom_animation = None
        self.detail_slide_animation = None
        super().closeEvent(event)

    @staticmethod
    def _normal_color(value: object, fallback: str) -> str:
        color = QColor(str(value))
        return color.name() if color.isValid() else fallback

    @staticmethod
    def _normal_brightness(value: object, fallback: int = DEFAULT_BACKGROUND_BRIGHTNESS) -> int:
        try:
            brightness = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(0, min(100, brightness))

    def _background_overlay_alpha(self) -> int:
        return round((100 - self.background_brightness) * 255 / 100)

    def _load_theme_preferences(self) -> tuple[str, str, int]:
        if not self.preferences_path.exists():
            return COLOR_TEXT, COLOR_SURFACE_2, DEFAULT_BACKGROUND_BRIGHTNESS
        try:
            data = json.loads(self.preferences_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return COLOR_TEXT, COLOR_SURFACE_2, DEFAULT_BACKGROUND_BRIGHTNESS
        return (
            self._normal_color(data.get("text_color"), COLOR_TEXT),
            self._normal_color(data.get("theme_color"), COLOR_SURFACE_2),
            self._normal_brightness(data.get("background_brightness")),
        )

    def _save_theme_preferences(self) -> None:
        self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
        self.preferences_path.write_text(
            json.dumps(
                {
                    "text_color": self.text_color,
                    "theme_color": self.theme_color,
                    "background_brightness": self.background_brightness,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def apply_theme_preferences(
        self,
        text_color: str,
        theme_color: str,
        background_brightness: int | None = None,
        *,
        persist: bool = True,
    ) -> None:
        self.text_color = self._normal_color(text_color, COLOR_TEXT)
        self.theme_color = self._normal_color(theme_color, COLOR_SURFACE_2)
        if background_brightness is not None:
            self.background_brightness = self._normal_brightness(background_brightness)
        if persist:
            self._save_theme_preferences()
        self.setPalette(self._dark_palette())
        self.setStyleSheet(build_app_qss(self.text_color, self.theme_color))
        self.update()

    def _dark_palette(self) -> QPalette:
        text_color = QColor(self.text_color)
        theme_color = QColor(self.theme_color)
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_BG))
        palette.setColor(QPalette.ColorRole.WindowText, text_color)
        palette.setColor(QPalette.ColorRole.Base, theme_color)
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLOR_SURFACE))
        palette.setColor(QPalette.ColorRole.Text, text_color)
        palette.setColor(QPalette.ColorRole.Button, theme_color)
        palette.setColor(QPalette.ColorRole.ButtonText, text_color)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(COLOR_PRIMARY))
        palette.setColor(QPalette.ColorRole.HighlightedText, text_color)
        return palette

    def _build_list_page(self) -> None:
        self.list_page = QWidget()
        self.list_page.setObjectName("ListPage")
        root = QHBoxLayout(self.list_page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(18, 20, 18, 18)
        sidebar_layout.setSpacing(12)

        sidebar_title = OutlinedLabel("书签")
        sidebar_title.setObjectName("SidebarTitle")
        sidebar_layout.addWidget(sidebar_title)
        new_album = AnimatedButton("新建书签")
        new_album.clicked.connect(self.create_album)
        sidebar_layout.addWidget(new_album)
        self.album_list_layout = QVBoxLayout()
        self.album_list_layout.setSpacing(8)
        sidebar_layout.addLayout(self.album_list_layout)
        sidebar_layout.addStretch()

        self.main_panel = QFrame()
        self.main_panel.setObjectName("MainPanel")
        main_layout = QVBoxLayout(self.main_panel)
        main_layout.setContentsMargins(24, 20, 24, 18)
        main_layout.setSpacing(16)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(6)
        title = OutlinedLabel("档案管理")
        title.setObjectName("Title")
        subtitle = OutlinedLabel("按书签整理照片档案，预览、检索和编辑基础信息。")
        subtitle.setObjectName("Subtitle")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)
        header.addLayout(self._create_window_controls(remember=True))
        main_layout.addLayout(header)

        toolbar = QHBoxLayout()
        import_button = AnimatedButton("新建档案")
        import_button.setObjectName("PrimaryButton")
        import_button.clicked.connect(self.create_empty_archive)
        toolbar.addWidget(import_button)
        prev_button = AnimatedButton("上一页")
        prev_button.clicked.connect(self.previous_page)
        toolbar.addWidget(prev_button)
        next_button = AnimatedButton("下一页")
        next_button.clicked.connect(self.next_page)
        toolbar.addWidget(next_button)
        self.page_label = OutlinedLabel("")
        self.page_label.setObjectName("MutedText")
        toolbar.addWidget(self.page_label)
        toolbar.addStretch()
        self.search_entry = QLineEdit()
        apply_surface_shadow(self.search_entry, blur_radius=18, y_offset=5, alpha=75)
        self.search_entry.setPlaceholderText("搜索标题、记录或书签")
        self.search_entry.returnPressed.connect(self.apply_search)
        toolbar.addWidget(self.search_entry)
        search_button = AnimatedButton("搜索")
        search_button.clicked.connect(self.apply_search)
        toolbar.addWidget(search_button)
        main_layout.addLayout(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("ContentScroll")
        self.scroll.viewport().setObjectName("ContentViewport")
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().installEventFilter(self)
        self.content_widget = QWidget()
        self.content_widget.setObjectName("ContentWidget")
        self.content_grid = QGridLayout(self.content_widget)
        self.content_grid.setContentsMargins(4, 4, 4, 4)
        self.content_grid.setHorizontalSpacing(16)
        self.content_grid.setVerticalSpacing(16)
        self.content_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll, 1)

        footer = QHBoxLayout()
        self.status_label = OutlinedLabel("")
        self.status_label.setObjectName("MutedText")
        footer.addWidget(self.status_label)
        footer.addStretch()
        settings_button = AnimatedButton("设置")
        settings_button.clicked.connect(self.show_settings)
        footer.addWidget(settings_button)
        help_button = AnimatedButton("帮助")
        help_button.clicked.connect(self.show_help)
        footer.addWidget(help_button)
        main_layout.addLayout(footer)

        root.addWidget(self.sidebar)
        root.addWidget(self.main_panel, 1)
        self.stack.addWidget(self.list_page)
        self._install_drag_filter(self.list_page, self.sidebar, self.main_panel, title, subtitle)

    def refresh(self) -> None:
        self.albums = self.store.list_albums()
        self.current_page = self.store.paginate_photos(
            album_id=self.selected_album_id,
            query=self.query,
            page=self.page,
            per_page=self.per_page,
        )
        self.page = self.current_page.page
        self._render_albums()
        self._render_content()
        self.page_label.setText(f"{self.current_page.page} / {self.current_page.total_pages}")
        self.status_label.setText(f"{self._active_album_name()} · 共 {self.current_page.total} 份档案")
        self._apply_text_shadows(self.list_page)

    def _render_albums(self) -> None:
        clear_layout(self.album_list_layout)
        self.album_item_widgets = []
        for index, album in enumerate(self.albums):
            item = AlbumItem(
                album,
                index + 1,
                album.id == self.selected_album_id,
                self.select_album,
                self.delete_album_from_sidebar,
                self.rename_album_from_sidebar,
            )
            self.album_item_widgets.append(item)
            self.album_list_layout.addWidget(item)

    def _render_content(self) -> None:
        clear_layout(self.content_grid)
        self.content_widget.setMinimumHeight(0)
        for column in range(PHOTO_GRID_COLUMNS):
            self.content_grid.setColumnStretch(column, 1)
        if not self.current_page.items:
            empty = OutlinedLabel("当前书签还没有档案。点击“新建档案”开始添加。")
            empty.setObjectName("EmptyText")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            apply_text_shadow(empty)
            self.content_grid.addWidget(empty, 0, 0, 1, PHOTO_GRID_COLUMNS)
            return

        for index, photo in enumerate(self.current_page.items[: PHOTO_GRID_COLUMNS * PHOTO_GRID_ROWS]):
            row, column = divmod(index, PHOTO_GRID_COLUMNS)
            self.content_grid.addWidget(
                PhotoCard(photo, self.show_detail, self.delete_photo_from_grid, theme=self.theme),
                row,
                column,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            )
        self._resize_content_grid()

    def _resize_content_grid(self) -> None:
        if not hasattr(self, "scroll") or not hasattr(self, "content_grid"):
            return
        viewport_size = self.scroll.viewport().size()
        if viewport_size.width() <= 0 or viewport_size.height() <= 0:
            return
        self.content_widget.setFixedSize(viewport_size)
        if not self.current_page or not self.current_page.items:
            return

        margins = self.content_grid.contentsMargins()
        horizontal_spacing = self.content_grid.horizontalSpacing()
        vertical_spacing = self.content_grid.verticalSpacing()
        available_width = (
            viewport_size.width()
            - margins.left()
            - margins.right()
            - horizontal_spacing * (PHOTO_GRID_COLUMNS - 1)
        )
        available_height = (
            viewport_size.height()
            - margins.top()
            - margins.bottom()
            - vertical_spacing * (PHOTO_GRID_ROWS - 1)
        )
        card_width = max(1, available_width // PHOTO_GRID_COLUMNS)
        card_height = max(1, available_height // PHOTO_GRID_ROWS)
        for index in range(self.content_grid.count()):
            widget = self.content_grid.itemAt(index).widget()
            if isinstance(widget, PhotoCard):
                widget.set_grid_cell_size(card_width, card_height)

    def show_detail(self, photo: Photo) -> None:
        self.detail_photo_id = photo.id
        self.detail_album_id = photo.album_id
        self.detail_photo_description = photo.description
        self.detail_images = self.store.list_photo_images(photo.id)
        self.detail_image_index = 0
        self.detail_page = QWidget()
        self.detail_page.setObjectName("DetailPage")
        layout = QVBoxLayout(self.detail_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_bar = QHBoxLayout()
        back_button = AnimatedButton("← 返回")
        back_button.clicked.connect(self.back_to_list)
        top_bar.addWidget(back_button, 0, Qt.AlignmentFlag.AlignLeft)
        top_bar.addStretch()
        top_bar.addLayout(self._create_window_controls())
        layout.addLayout(top_bar)

        split = QHBoxLayout()
        split.setSpacing(18)

        self.detail_image_panel = QFrame()
        image_layout = QVBoxLayout(self.detail_image_panel)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(0)
        image_view = QHBoxLayout()
        image_view.setSpacing(10)
        self.detail_prev_image_button = AnimatedButton("<")
        self.detail_prev_image_button.setObjectName("ImageNavButton")
        self.detail_prev_image_button.setAccessibleName("上一张图片")
        self.detail_prev_image_button.setToolTip("上一张图片")
        self.detail_prev_image_button.setFixedSize(44, 44)
        self.detail_prev_image_button.clicked.connect(self.previous_detail_image)
        image_view.addWidget(self.detail_prev_image_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.detail_image = TiltImagePreview(theme=self.theme)
        image_view.addWidget(self.detail_image, 1)
        self._create_detail_video_player()
        self.detail_video_play_button = AnimatedButton("▶", self.detail_image)
        self.detail_video_play_button.setObjectName("VideoPlayButton")
        self.detail_video_play_button.setAccessibleName("播放视频")
        self.detail_video_play_button.setToolTip("播放视频")
        self.detail_video_play_button.setFixedSize(68, 68)
        self.detail_video_play_button.clicked.connect(self.handle_video_play_clicked)
        self.detail_video_play_button.hide()
        self._create_detail_video_controls()
        self.detail_image.installEventFilter(self)
        self.detail_next_image_button = AnimatedButton(">")
        self.detail_next_image_button.setObjectName("ImageNavButton")
        self.detail_next_image_button.setAccessibleName("下一张图片")
        self.detail_next_image_button.setToolTip("下一张图片")
        self.detail_next_image_button.setFixedSize(44, 44)
        self.detail_next_image_button.clicked.connect(self.next_detail_image)
        image_view.addWidget(self.detail_next_image_button, 0, Qt.AlignmentFlag.AlignVCenter)
        image_layout.addLayout(image_view, 1)
        image_actions = QHBoxLayout()
        self.detail_image_counter = OutlinedLabel("")
        self.detail_image_counter.setObjectName("MutedText")
        image_actions.addWidget(self.detail_image_counter)
        image_actions.addStretch()
        self.detail_import_images_button = AnimatedButton("导入图片")
        self.detail_import_images_button.setObjectName("PrimaryButton")
        self.detail_import_images_button.clicked.connect(self.import_images_to_detail)
        image_actions.addWidget(self.detail_import_images_button)
        image_layout.addLayout(image_actions)
        split.addWidget(self.detail_image_panel, 1)

        self.detail_editor = QFrame()
        self.detail_editor.setObjectName("DetailEditorPanel")
        editor_layout = QVBoxLayout(self.detail_editor)
        editor_layout.setSpacing(12)
        archive_heading = OutlinedLabel("档案信息")
        archive_heading.setObjectName("SectionTitle")
        archive_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor_layout.addWidget(archive_heading)
        meta_layout = QGridLayout()
        meta_layout.setHorizontalSpacing(10)
        meta_layout.setVerticalSpacing(8)
        meta_layout.setColumnStretch(1, 1)

        self.detail_title = QLineEdit(photo.title)
        self.detail_title.setObjectName("DetailTitleInput")
        self._apply_detail_field_shadow(self.detail_title, blur_radius=36, y_offset=10)
        self.detail_display_date = QLineEdit(photo.display_date)
        self.detail_display_date.setObjectName("DetailDateInput")
        self._apply_detail_field_shadow(self.detail_display_date, blur_radius=36, y_offset=10)
        self.detail_display_date.setPlaceholderText("例如 2026-06-17")
        self.detail_record_level = QLineEdit(photo.record_level)
        self.detail_record_level.setObjectName("DetailRecordLevelInput")
        self._apply_detail_field_shadow(self.detail_record_level, blur_radius=36, y_offset=10)

        for row, (label_text, field) in enumerate(
            (
                ("标题", self.detail_title),
                ("日期", self.detail_display_date),
                ("记录等级", self.detail_record_level),
            )
        ):
            label = OutlinedLabel(label_text)
            label.setObjectName("CompactFieldLabel")
            meta_layout.addWidget(label, row, 0)
            meta_layout.addWidget(field, row, 1)

        editor_layout.addLayout(meta_layout)
        editor_layout.addSpacing(8)
        self.detail_record_label = OutlinedLabel("记录")
        self.detail_record_label.setObjectName("SectionTitle")
        self.detail_record_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor_layout.addWidget(self.detail_record_label)
        self.detail_record = QTextEdit()
        self.detail_record.setObjectName("DetailRecordInput")
        self._apply_detail_field_shadow(self.detail_record, blur_radius=48, y_offset=14)
        self.detail_record.setPlaceholderText("记录当前档案的信息")
        self.detail_record.setPlainText(photo.description)
        editor_layout.addWidget(self.detail_record, 2)
        self.detail_resource_note_label = OutlinedLabel("资源标注")
        self.detail_resource_note_label.setObjectName("SectionTitle")
        self.detail_resource_note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor_layout.addWidget(self.detail_resource_note_label)
        self.detail_resource_note = QTextEdit()
        self.detail_resource_note.setObjectName("DetailResourceNoteInput")
        self._apply_detail_field_shadow(self.detail_resource_note, blur_radius=48, y_offset=14)
        self.detail_resource_note.setPlaceholderText("标注当前图片或视频")
        editor_layout.addWidget(self.detail_resource_note, 1)
        self._refresh_detail_image()
        actions = QHBoxLayout()
        actions.addStretch()
        save_button = AnimatedButton("保存")
        save_button.setObjectName("SuccessButton")
        save_button.clicked.connect(self.save_detail)
        actions.addWidget(save_button)
        editor_layout.addLayout(actions)
        split.addWidget(self.detail_editor, 1)

        layout.addLayout(split, 1)
        self.stack.addWidget(self.detail_page)
        self.stack.setCurrentWidget(self.detail_page)
        self._install_drag_filter(self.detail_page)
        self._apply_text_shadows(self.detail_page)
        self._run_detail_transition("enter")

    def _apply_text_shadows(self, root: QWidget) -> None:
        for label in root.findChildren(QLabel):
            apply_text_shadow(label)

    def _apply_detail_field_shadow(self, field: QWidget, *, blur_radius: int, y_offset: int) -> None:
        shadow = QGraphicsDropShadowEffect(field)
        shadow.setBlurRadius(blur_radius)
        shadow.setOffset(0, y_offset)
        shadow.setColor(QColor(56, 40, 12, 100))
        field.setGraphicsEffect(shadow)

    def save_detail(self) -> None:
        if self.detail_photo_id is None:
            return
        self._save_current_image_record()
        photo = self.store.update_photo(
            self.detail_photo_id,
            title=self.detail_title.text(),
            description=self.detail_record.toPlainText(),
            album_id=self.detail_album_id,
            display_date=self.detail_display_date.text(),
            record_level=self.detail_record_level.text(),
        )
        self.selected_album_id = photo.album_id
        self.show_detail(photo)

    def create_empty_archive(self) -> None:
        if self.selected_album_id is None:
            QMessageBox.information(self, "新建档案", "请先选择一个书签。")
            return
        self.store.create_empty_photo(self.selected_album_id)
        self.page = self.store.paginate_photos(album_id=self.selected_album_id, query=self.query, per_page=self.per_page).total_pages
        self.refresh()

    def import_images_to_detail(self) -> None:
        if self.detail_photo_id is None:
            return
        if self.image_import_thread is not None:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择档案图片或视频",
            str(self.workspace),
            MEDIA_FILE_FILTER,
        )
        if not files:
            return
        self._save_current_image_record()
        self._start_image_import(self.detail_photo_id, [Path(filename) for filename in files])

    def _start_image_import(self, photo_id: int, source_paths: list[Path]) -> None:
        self._pending_import_photo_id = photo_id
        self._status_before_import = self.status_label.text()
        self._set_detail_import_busy(True)
        self.image_import_thread = QThread()
        self.image_import_worker = ImageImportWorker(
            self.store.database_path,
            self.store.media_dir,
            photo_id,
            source_paths,
        )
        thread = self.image_import_thread
        worker = self.image_import_worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda *_args, thread=thread: thread.quit())
        worker.failed.connect(lambda *_args, thread=thread: thread.quit())
        worker.finished.connect(self._on_image_import_finished)
        worker.failed.connect(self._on_image_import_failed)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _set_detail_import_busy(self, busy: bool) -> None:
        if hasattr(self, "detail_import_images_button"):
            self.detail_import_images_button.setEnabled(not busy)
        if hasattr(self, "detail_prev_image_button"):
            self.detail_prev_image_button.setEnabled(False if busy else len(self.detail_images) > 1)
        if hasattr(self, "detail_next_image_button"):
            self.detail_next_image_button.setEnabled(False if busy else len(self.detail_images) > 1)
        if busy:
            self.status_label.setText("正在导入媒体...")
        elif self._status_before_import:
            self.status_label.setText(self._status_before_import)

    def _on_image_import_finished(self, photo_id: int, images: list) -> None:
        stale_detail = self.detail_photo_id != photo_id
        self._cleanup_image_import_state()
        if stale_detail:
            self.refresh()
            return
        was_empty = not self.detail_images
        self.detail_images = images
        self.detail_image_index = 0 if was_empty else min(self.detail_image_index, len(self.detail_images) - 1)
        self._refresh_detail_image()
        self.status_label.setText(f"已导入 {len(images)} 个媒体文件")

    def _on_image_import_failed(self, photo_id: int, message: str) -> None:
        stale_detail = self.detail_photo_id != photo_id
        self._cleanup_image_import_state()
        if stale_detail:
            self.refresh()
            return
        QMessageBox.warning(self, "导入媒体失败", message)

    def _cleanup_image_import_state(self) -> None:
        self._pending_import_photo_id = None
        self._set_detail_import_busy(False)
        self.image_import_worker = None
        self.image_import_thread = None

    def previous_detail_image(self) -> None:
        total = len(self.detail_images)
        if total <= 1:
            return
        self._save_current_image_record()
        self.detail_image_index = (self.detail_image_index - 1) % total
        self._refresh_detail_image(animate=True, direction="previous")

    def next_detail_image(self) -> None:
        total = len(self.detail_images)
        if total <= 1:
            return
        self._save_current_image_record()
        self.detail_image_index = (self.detail_image_index + 1) % total
        self._refresh_detail_image(animate=True, direction="next")

    def _refresh_detail_image(self, *, animate: bool = False, direction: str = "next") -> None:
        self._stop_detail_video_playback()
        total = len(self.detail_images)
        if total == 0:
            self.detail_image.set_empty_text("暂无图片")
            self.detail_image.set_preview_stack([])
            self.detail_image_counter.setText("0 / 0")
            self.detail_prev_image_button.setEnabled(False)
            self.detail_next_image_button.setEnabled(False)
            self._update_detail_video_play_button()
            self._load_current_image_record()
            return
        self.detail_image_index = max(0, min(self.detail_image_index, total - 1))
        self._set_detail_image_stack(animate=animate, direction=direction)
        self.detail_image_counter.setText(f"{self.detail_image_index + 1} / {total}")
        can_cycle = total > 1
        self.detail_prev_image_button.setEnabled(can_cycle)
        self.detail_next_image_button.setEnabled(can_cycle)
        self._update_detail_video_play_button()
        self._load_current_image_record()

    def _current_detail_media_path(self) -> Path | None:
        if not self.detail_images:
            return None
        return self.detail_images[self.detail_image_index].stored_path

    def _current_detail_media_is_video(self) -> bool:
        path = self._current_detail_media_path()
        return path is not None and is_video_file(path)

    def _update_detail_video_play_button(self) -> None:
        if not hasattr(self, "detail_video_play_button"):
            return
        visible = self._current_detail_media_is_video() and not self._detail_video_widget_is_visible()
        self.detail_video_play_button.setVisible(visible)
        if visible:
            self._position_detail_video_play_button()

    def _detail_video_widget_is_visible(self) -> bool:
        return hasattr(self, "detail_video_widget") and self.detail_video_widget.isVisible()

    def _position_detail_video_play_button(self) -> None:
        if not hasattr(self, "detail_video_play_button") or not hasattr(self, "detail_image"):
            return
        button = self.detail_video_play_button
        x = (self.detail_image.width() - button.width()) // 2
        y = (self.detail_image.height() - button.height()) // 2
        button.move(max(0, x), max(0, y))
        button.raise_()

    def _create_detail_video_player(self) -> None:
        self._detail_video_is_playing = False
        self.detail_video_widget = QVideoWidget(self.detail_image)
        self.detail_video_widget.setObjectName("DetailVideoWidget")
        self.detail_video_widget.hide()
        self.detail_video_audio = QAudioOutput(self)
        self.detail_video_player = QMediaPlayer(self)
        self.detail_video_player.setVideoOutput(self.detail_video_widget)
        self.detail_video_player.setAudioOutput(self.detail_video_audio)
        self.detail_video_player.positionChanged.connect(self._on_detail_video_position_changed)
        self.detail_video_player.durationChanged.connect(self._on_detail_video_duration_changed)
        self.detail_video_player.playbackStateChanged.connect(self._on_detail_video_playback_state_changed)

    def _create_detail_video_controls(self) -> None:
        self.detail_video_controls = QWidget(self.detail_image)
        self.detail_video_controls.setObjectName("DetailVideoControls")
        self.detail_video_controls.setFixedHeight(44)
        controls_layout = QHBoxLayout(self.detail_video_controls)
        controls_layout.setContentsMargins(8, 6, 8, 6)
        controls_layout.setSpacing(8)

        self.detail_video_pause_button = AnimatedButton("||", self.detail_video_controls)
        self.detail_video_pause_button.setObjectName("DetailVideoPauseButton")
        self.detail_video_pause_button.setAccessibleName("暂停视频")
        self.detail_video_pause_button.setToolTip("暂停 / 继续")
        self.detail_video_pause_button.setFixedSize(32, 32)
        self.detail_video_pause_button.clicked.connect(self.handle_detail_video_pause_clicked)
        controls_layout.addWidget(self.detail_video_pause_button)

        self.detail_video_progress = QSlider(Qt.Orientation.Horizontal, self.detail_video_controls)
        self.detail_video_progress.setObjectName("DetailVideoProgressSlider")
        self.detail_video_progress.setRange(0, 0)
        self.detail_video_progress.sliderReleased.connect(self._seek_detail_video_to_slider)
        controls_layout.addWidget(self.detail_video_progress, 1)
        self.detail_video_controls.hide()

    def _position_detail_video_widget(self) -> None:
        if not hasattr(self, "detail_video_widget") or not hasattr(self, "detail_image"):
            return
        self._position_detail_video_controls()
        video_bottom = self.detail_image.height()
        if hasattr(self, "detail_video_controls"):
            video_bottom = max(1, self.detail_video_controls.y() - 6)
        self.detail_video_widget.setGeometry(0, 0, self.detail_image.width(), video_bottom)
        self.detail_video_widget.raise_()
        self._position_detail_video_controls()

    def _position_detail_video_controls(self) -> None:
        if not hasattr(self, "detail_video_controls") or not hasattr(self, "detail_image"):
            return
        width = max(160, self.detail_image.width() - 48)
        height = self.detail_video_controls.height()
        x = max(0, (self.detail_image.width() - width) // 2)
        y = max(0, self.detail_image.height() - height - 14)
        self.detail_video_controls.setGeometry(x, y, width, height)
        if self.detail_video_controls.isVisible():
            self.detail_video_controls.raise_()

    def handle_video_play_clicked(self) -> None:
        path = self._current_detail_media_path()
        if path is None or not is_video_file(path):
            return
        self.last_video_play_request_path = path
        self.detail_video_play_button.hide()
        QTimer.singleShot(0, lambda path=path: self._start_detail_video_playback(path))

    def _start_detail_video_playback(self, path: Path) -> None:
        if path != self.last_video_play_request_path:
            return
        if path != self._current_detail_media_path() or not is_video_file(path):
            self._update_detail_video_play_button()
            return
        if hasattr(self, "detail_page") and self.detail_page.layout() is not None:
            self.detail_page.layout().activate()
        self._position_detail_video_widget()
        self.detail_video_widget.show()
        self.detail_video_controls.show()
        self._position_detail_video_widget()
        self.detail_video_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.detail_video_player.play()
        self._set_detail_video_playing(True)
        self.status_label.setText("正在播放视频")

    def handle_detail_video_pause_clicked(self) -> None:
        if not self._detail_video_widget_is_visible():
            return
        if self._detail_video_is_playing:
            self.detail_video_player.pause()
            self._set_detail_video_playing(False)
        else:
            self.detail_video_player.play()
            self._set_detail_video_playing(True)

    def _set_detail_video_playing(self, playing: bool) -> None:
        self._detail_video_is_playing = playing
        if hasattr(self, "detail_video_pause_button"):
            self.detail_video_pause_button.setText("||" if playing else ">")

    def _on_detail_video_position_changed(self, position: int) -> None:
        if not hasattr(self, "detail_video_progress"):
            return
        with QSignalBlocker(self.detail_video_progress):
            self.detail_video_progress.setValue(position)

    def _on_detail_video_duration_changed(self, duration: int) -> None:
        if not hasattr(self, "detail_video_progress"):
            return
        self.detail_video_progress.setRange(0, max(0, duration))
        self.detail_video_progress.setPageStep(max(1, duration // 20) if duration else 1)

    def _on_detail_video_playback_state_changed(self, state) -> None:
        self._set_detail_video_playing(state == QMediaPlayer.PlaybackState.PlayingState)

    def _seek_detail_video_to_slider(self) -> None:
        if not hasattr(self, "detail_video_progress"):
            return
        self.detail_video_player.setPosition(self.detail_video_progress.value())

    def _stop_detail_video_playback(self) -> None:
        if hasattr(self, "detail_video_player"):
            self.detail_video_player.stop()
        self._set_detail_video_playing(False)
        if hasattr(self, "detail_video_widget"):
            self.detail_video_widget.hide()
        if hasattr(self, "detail_video_controls"):
            self.detail_video_controls.hide()

    def _save_current_image_record(self) -> None:
        if not hasattr(self, "detail_resource_note"):
            return
        if not self.detail_images:
            return
        image = self.detail_images[self.detail_image_index]
        updated = self.store.update_photo_image_record(image.id, self.detail_resource_note.toPlainText())
        self.detail_images[self.detail_image_index] = updated

    def _load_current_image_record(self) -> None:
        if not hasattr(self, "detail_resource_note"):
            return
        if not self.detail_images:
            self.detail_resource_note.clear()
            self.detail_resource_note.setEnabled(False)
            return
        self.detail_resource_note.setEnabled(True)
        self.detail_resource_note.setPlainText(self.detail_images[self.detail_image_index].record)

    def back_to_list(self) -> None:
        self._stop_detail_video_playback()
        current = self.stack.currentWidget()
        self.detail_photo_id = None
        if current is not None and current is not self.list_page:
            self._run_detail_transition("return", lambda: self._complete_back_to_list(current))
            return
        self._complete_back_to_list(current)

    def _complete_back_to_list(self, current: QWidget | None) -> None:
        self.stack.setCurrentWidget(self.list_page)
        if current is not None and current is not self.list_page:
            self.stack.removeWidget(current)
            current.deleteLater()
        self.refresh()

    def select_album(self, album_id: int) -> None:
        self.selected_album_id = album_id
        self.page = 1
        self.refresh()

    def delete_photo_from_grid(self, photo_id: int) -> None:
        photo = self.store.get_photo(photo_id)
        if not self._confirm_delete("删除照片", f"删除照片「{photo.title}」后无法撤销，确定删除吗？"):
            return
        self.store.delete_photo(photo_id)
        self.refresh()

    def delete_album_from_sidebar(self, album_id: int) -> None:
        album = next((item for item in self.store.list_albums() if item.id == album_id), None)
        album_name = album.name if album is not None else str(album_id)
        if not self._confirm_delete("删除书签", f"删除书签「{album_name}」会同时删除其中所有档案和图片，确定删除吗？"):
            return
        self.store.delete_album(album_id)
        remaining_albums = self.store.list_albums()
        if self.selected_album_id == album_id:
            self.selected_album_id = remaining_albums[0].id if remaining_albums else None
        self.page = 1
        self.refresh()

    def _confirm_delete(self, title: str, message: str) -> bool:
        result = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def rename_album_from_sidebar(self, album_id: int, name: str) -> None:
        self.store.rename_album(album_id, name)
        self.refresh()

    def create_album(self) -> None:
        name = "新书签"
        existing = {album.name for album in self.store.list_albums()}
        index = 1
        while name in existing:
            index += 1
            name = f"新书签 {index}"
        album = self.store.create_album(name)
        self.selected_album_id = album.id
        self.page = 1
        self.refresh()

    def apply_search(self) -> None:
        self.query = self.search_entry.text().strip()
        self.page = 1
        self.refresh()

    def toggle_view(self) -> None:
        self.view_mode = "grid"
        self.refresh()

    def previous_page(self) -> None:
        self.page = max(1, self.page - 1)
        self.refresh()

    def next_page(self) -> None:
        self.page += 1
        self.refresh()

    def show_settings(self) -> None:
        self._create_settings_dialog().exec()

    def _create_settings_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("设置")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        text_input = QLineEdit(self.text_color)
        text_input.setObjectName("SettingsTextColorInput")
        theme_input = QLineEdit(self.theme_color)
        theme_input.setObjectName("SettingsThemeColorInput")
        brightness_slider = QSlider(Qt.Orientation.Horizontal)
        brightness_slider.setObjectName("SettingsBackgroundBrightnessSlider")
        brightness_slider.setRange(0, 100)
        brightness_slider.setValue(self.background_brightness)
        brightness_spin = QSpinBox()
        brightness_spin.setObjectName("SettingsBackgroundBrightnessSpinBox")
        brightness_spin.setRange(0, 100)
        brightness_spin.setSuffix("%")
        brightness_spin.setValue(self.background_brightness)
        brightness_slider.valueChanged.connect(brightness_spin.setValue)
        brightness_spin.valueChanged.connect(brightness_slider.setValue)

        def choose_color(field: QLineEdit, title: str) -> None:
            color = QColorDialog.getColor(QColor(field.text()), dialog, title)
            if color.isValid():
                field.setText(color.name())

        def make_color_row(field: QLineEdit, title: str) -> QWidget:
            row = QWidget(dialog)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(field, 1)
            choose = QPushButton("选择")
            choose.clicked.connect(lambda _checked=False: choose_color(field, title))
            row_layout.addWidget(choose)
            return row

        form.addRow("字体颜色", make_color_row(text_input, "选择字体颜色"))
        form.addRow("主题配色", make_color_row(theme_input, "选择主题配色"))
        brightness_row = QWidget(dialog)
        brightness_layout = QHBoxLayout(brightness_row)
        brightness_layout.setContentsMargins(0, 0, 0, 0)
        brightness_layout.addWidget(brightness_slider, 1)
        brightness_layout.addWidget(brightness_spin)
        form.addRow("背景亮度", brightness_row)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)

        def accept_settings() -> None:
            text_color = QColor(text_input.text())
            theme_color = QColor(theme_input.text())
            if not text_color.isValid() or not theme_color.isValid():
                QMessageBox.warning(dialog, "颜色无效", "请输入类似 #111111 的颜色值。")
                return
            self.apply_theme_preferences(text_color.name(), theme_color.name(), brightness_spin.value())
            dialog.accept()

        buttons.accepted.connect(accept_settings)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog

    def show_help(self) -> None:
        QMessageBox.information(
            self,
            "帮助",
            "左侧书签切换分类；点击“新建档案”添加空档案；点击预览卡片进入详情页；详情页可导入多张图片并编辑文字。",
        )

    def _active_album_name(self) -> str:
        for album in self.albums:
            if album.id == self.selected_album_id:
                return album.name
        return "全部档案"

    def _set_label_pixmap(self, label: QWidget, photo: Photo, size: QSize) -> None:
        self._set_image_path_pixmap(label, photo.stored_path, size, empty_text="暂无图片" if photo.image_count else "空档案")

    def _set_image_path_pixmap(self, label: QWidget, path: Path, size: QSize, empty_text: str = "暂无图片") -> None:
        try:
            pixmap = load_media_preview_pixmap(path, size.width(), size.height())
        except OSError:
            pixmap = QPixmap()
        if pixmap.isNull():
            if isinstance(label, TiltImagePreview):
                label.set_empty_text(empty_text)
                label.set_preview_stack([])
            elif isinstance(label, StackedImagePreview):
                label.set_preview_pixmaps([], empty_text=empty_text)
            elif isinstance(label, QLabel):
                label.setPixmap(QPixmap())
                label.setText(empty_text)
            return
        if isinstance(label, TiltImagePreview):
            label.set_preview_pixmap(pixmap)
        elif isinstance(label, StackedImagePreview):
            label.set_preview_pixmaps([pixmap], empty_text=empty_text)
        elif isinstance(label, QLabel):
            label.setText("")
            label.setPixmap(pixmap)

    def _set_detail_image_stack(self, *, animate: bool, direction: str) -> None:
        total = len(self.detail_images)
        indexes = [self.detail_image_index]
        if total > 1:
            indexes.append((self.detail_image_index + 1) % total)
        if total > 2:
            indexes.append((self.detail_image_index - 1) % total)
        pixmaps = [
            self._load_image_path_pixmap(self.detail_images[index].stored_path, QSize(720, 620))
            for index in indexes[:3]
        ]
        self.detail_image.set_preview_stack(pixmaps, animate=animate, direction=direction)

    def _load_image_path_pixmap(self, path: Path, size: QSize) -> QPixmap:
        try:
            return load_media_preview_pixmap(path, size.width(), size.height())
        except OSError:
            if is_video_file(path):
                return self._load_video_placeholder_pixmap(size)
            return QPixmap()

    def _load_video_placeholder_pixmap(self, size: QSize) -> QPixmap:
        ground_path = self.theme.ground_pixmap()
        if ground_path is None:
            return QPixmap()
        pixmap = QPixmap(str(ground_path))
        if pixmap.isNull():
            return QPixmap()
        return pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _create_window_controls(self, remember: bool = False) -> QHBoxLayout:
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.setContentsMargins(0, 0, 0, 0)

        minimize = AnimatedButton("-")
        minimize.setObjectName("WindowMinimizeButton")
        minimize.setAccessibleName("最小化")
        minimize.setToolTip("最小化")
        minimize.setFixedSize(36, 36)
        minimize.clicked.connect(self.showMinimized)

        maximize = AnimatedButton("□")
        maximize.setObjectName("WindowMaximizeButton")
        maximize.setAccessibleName("最大化")
        maximize.setToolTip("最大化")
        maximize.setFixedSize(36, 36)
        maximize.clicked.connect(self.toggle_maximized)

        close = AnimatedButton("×")
        close.setObjectName("WindowCloseButton")
        close.setAccessibleName("关闭")
        close.setToolTip("关闭")
        close.setFixedSize(36, 36)
        close.clicked.connect(self.close)

        for button in (minimize, maximize, close):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            controls.addWidget(button)

        if remember:
            self.minimize_button = minimize
            self.maximize_button = maximize
            self.close_button = close

        return controls

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
            state_text = "□"
            tooltip = "最大化"
            accessible = "最大化"
        else:
            self.showMaximized()
            state_text = "❐"
            tooltip = "还原"
            accessible = "还原"

        if hasattr(self, "maximize_button"):
            self.maximize_button.setText(state_text)
            self.maximize_button.setToolTip(tooltip)
            self.maximize_button.setAccessibleName(accessible)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_content_grid()

    def _run_detail_transition(self, direction: str, on_finished=None) -> None:
        if not hasattr(self, "detail_page") or not hasattr(self, "detail_image_panel"):
            if on_finished is not None:
                on_finished()
            return

        self.last_transition_direction = direction
        entering = direction == "enter"
        self.detail_zoom_animation = None

        opacity_effect = QGraphicsOpacityEffect(self.detail_page)
        self.detail_page.setGraphicsEffect(opacity_effect)
        opacity_effect.setOpacity(0.0 if entering else 1.0)

        group = QParallelAnimationGroup(self)
        group.setObjectName("DetailSlideTransition")

        final_position = self.detail_image_panel.pos()
        hidden_position = final_position - QPoint(DETAIL_IMAGE_SLIDE_OFFSET, 0)
        start_position = hidden_position if entering else final_position
        end_position = final_position if entering else hidden_position
        self.detail_image_panel.move(start_position)

        self.detail_slide_animation = QPropertyAnimation(self.detail_image_panel, b"pos", group)
        self.detail_slide_animation.setDuration(TRANSITION_ANIMATION_MS)
        self.detail_slide_animation.setStartValue(start_position)
        self.detail_slide_animation.setEndValue(end_position)
        self.detail_slide_animation.setEasingCurve(QEasingCurve.Type.OutCubic if entering else QEasingCurve.Type.InCubic)
        group.addAnimation(self.detail_slide_animation)

        opacity_animation = QPropertyAnimation(opacity_effect, b"opacity", group)
        opacity_animation.setDuration(TRANSITION_ANIMATION_MS)
        opacity_animation.setStartValue(0.0 if entering else 1.0)
        opacity_animation.setEndValue(1.0 if entering else 0.0)
        opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(opacity_animation)

        def finish_transition() -> None:
            if entering:
                self.detail_image_panel.move(final_position)
                self.detail_page.setGraphicsEffect(None)
            if on_finished is not None:
                on_finished()

        group.finished.connect(finish_transition)
        self.detail_transition_animation = group
        group.start()

    def _install_drag_filter(self, *widgets: QWidget) -> None:
        for widget in widgets:
            widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (
            hasattr(self, "scroll")
            and watched is self.scroll.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self._resize_content_grid()
        if (
            hasattr(self, "detail_image")
            and watched is self.detail_image
            and event.type() == QEvent.Type.Resize
        ):
            self._position_detail_video_play_button()
            self._position_detail_video_widget()
            self._position_detail_video_controls()

        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if self._is_window_drag_event(event):
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return False

        if event.type() == QEvent.Type.MouseMove and self._drag_offset is not None:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                return True

        if event.type() == QEvent.Type.MouseButtonRelease:
            self._drag_offset = None

        return super().eventFilter(watched, event)

    def _is_window_drag_event(self, event) -> bool:
        window_position = self.mapFromGlobal(event.globalPosition().toPoint())
        return 0 <= window_position.y() <= self.DRAG_REGION_HEIGHT


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


APP_QSS = f"""
QMainWindow {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLOR_BG_GRADIENT_START}, stop:1 {COLOR_BG_GRADIENT_END});
    color: {COLOR_TEXT};
    font-family: {FONT_STACK};
    font-size: 15px;
    font-weight: 700;
}}
QWidget#ListPage, QWidget#DetailPage {{
    background: transparent;
    color: {COLOR_TEXT};
    font-family: {FONT_STACK};
    font-size: 15px;
    font-weight: 700;
}}
QFrame#Sidebar {{
    background: transparent;
    border: none;
}}
QFrame#PhotoCard {{
    background: transparent;
    border: none;
}}
QFrame#PhotoCardContainer {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
}}
QFrame#DetailEditorPanel {{
    background: transparent;
    border: none;
}}
QFrame#AlbumItem {{
    background: transparent;
    border: none;
}}
QFrame#MainPanel {{
    background: transparent;
    border: none;
}}
QLabel {{
    color: {COLOR_TEXT};
    background: transparent;
    font-size: 15px;
    font-weight: 700;
}}
QLabel#Title {{
    font-size: 30px;
    font-weight: 700;
}}
QLabel#Subtitle {{
    color: {COLOR_MUTED};
    font-size: 14px;
    font-weight: 700;
}}
QLabel#MutedText {{
    color: {COLOR_MUTED};
    font-size: 13px;
    font-weight: 700;
}}
QLabel#CardMetaText {{
    color: {COLOR_MUTED};
    font-size: 9px;
    font-weight: 700;
    margin: 0px;
    padding: 0px;
}}
QLabel#SidebarTitle {{
    font-size: 16px;
    font-weight: 700;
}}
QLabel#SectionTitle {{
    font-size: 18px;
    font-weight: 700;
}}
QLabel#CardTitle {{
    font-size: 18px;
    font-weight: 700;
}}
QLabel#EmptyText {{
    color: {COLOR_MUTED};
    font-size: 15px;
    padding: 80px;
}}
QLabel#ImagePreview, QWidget#ImagePreview, QWidget#DetailImage {{
    background: transparent;
    border: none;
}}
QPushButton {{
    background: {COLOR_SURFACE_2};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 9px 13px;
    min-height: 22px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton:hover {{
    background: {COLOR_SURFACE_3};
}}
QPushButton:pressed {{
    background: {COLOR_PRIMARY_HOVER};
}}
QPushButton#PrimaryButton, QPushButton#SelectedAlbumButton {{
    background: {COLOR_PRIMARY};
    border-color: {COLOR_PRIMARY};
    color: {COLOR_TEXT};
}}
QPushButton#PrimaryButton:hover, QPushButton#SelectedAlbumButton:hover {{
    background: {COLOR_PRIMARY_HOVER};
}}
QPushButton#SuccessButton {{
    background: {COLOR_SUCCESS};
    border-color: {COLOR_SUCCESS};
    color: {COLOR_TEXT};
}}
QPushButton#SuccessButton:hover {{
    background: {COLOR_SUCCESS_HOVER};
}}
QPushButton#AlbumButton {{
    text-align: left;
    font-weight: 700;
}}
QPushButton#PhotoDeleteButton, QPushButton#AlbumDeleteButton {{
    background: {COLOR_SURFACE_2};
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
    color: {COLOR_TEXT};
    font-size: 14px;
    font-weight: 700;
    padding: 0;
    min-width: 22px;
    min-height: 22px;
}}
QPushButton#PhotoDeleteButton:hover, QPushButton#AlbumDeleteButton:hover {{
    background: {COLOR_DANGER};
    border-color: {COLOR_DANGER};
    color: #ffffff;
}}
QPushButton#WindowMinimizeButton, QPushButton#WindowMaximizeButton, QPushButton#WindowCloseButton {{
    background: {COLOR_SURFACE_2};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 0;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    color: {COLOR_MUTED};
    font-size: 18px;
    font-weight: 700;
}}
QPushButton#WindowMinimizeButton:hover, QPushButton#WindowMaximizeButton:hover {{
    background: {COLOR_SURFACE_3};
    border-color: {COLOR_BORDER};
    color: {COLOR_TEXT};
}}
QPushButton#WindowCloseButton:hover {{
    background: {COLOR_DANGER};
    border-color: {COLOR_DANGER};
    color: #ffffff;
}}
QPushButton#ImageNavButton {{
    background: {COLOR_SURFACE_2};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    color: {COLOR_TEXT};
    font-size: 26px;
    font-weight: 700;
    padding: 0;
    min-width: 44px;
    min-height: 44px;
}}
QPushButton#ImageNavButton:hover {{
    background: {COLOR_SURFACE_3};
    border-color: {COLOR_PRIMARY};
}}
QPushButton#ImageNavButton:disabled {{
    color: {COLOR_MUTED};
    background: #ead9ad;
    border-color: #c3a65c;
}}
QPushButton#VideoPlayButton {{
    background: #000000;
    border: 1px solid {COLOR_BORDER};
    border-radius: 34px;
    color: {COLOR_TEXT};
    font-size: 28px;
    font-weight: 700;
    padding: 0;
    min-width: 68px;
    max-width: 68px;
    min-height: 68px;
    max-height: 68px;
}}
QPushButton#VideoPlayButton:hover {{
    background: #111111;
    border-color: {COLOR_PRIMARY};
}}
QWidget#DetailVideoControls {{
    background: #000000;
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
}}
QPushButton#DetailVideoPauseButton {{
    background: #111111;
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    color: {COLOR_TEXT};
    font-size: 14px;
    font-weight: 700;
    padding: 0;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
}}
QPushButton#DetailVideoPauseButton:hover {{
    background: #1b1b1b;
    border-color: {COLOR_PRIMARY};
}}
QSlider#DetailVideoProgressSlider::groove:horizontal {{
    background: #272727;
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    height: 8px;
}}
QSlider#DetailVideoProgressSlider::sub-page:horizontal {{
    background: {COLOR_TEXT};
    border-radius: 4px;
}}
QSlider#DetailVideoProgressSlider::handle:horizontal {{
    background: {COLOR_SURFACE_2};
    border: 1px solid {COLOR_BORDER};
    border-radius: 7px;
    width: 14px;
    margin: -4px 0;
}}
QLineEdit, QTextEdit, QComboBox {{
    background: {COLOR_SURFACE_2};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 9px 11px;
    font-size: 15px;
    font-weight: 700;
    min-height: 24px;
    selection-background-color: {COLOR_PRIMARY};
    selection-color: {COLOR_TEXT};
}}
QTextEdit {{
    padding: 12px;
}}
QLineEdit#DetailTitleInput, QLineEdit#DetailDateInput, QLineEdit#DetailRecordLevelInput, QTextEdit#DetailRecordInput, QTextEdit#DetailResourceNoteInput {{
    background: {COLOR_SURFACE};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: {COLOR_PRIMARY};
    selection-color: {COLOR_TEXT};
}}
QLineEdit#DetailTitleInput:focus, QLineEdit#DetailDateInput:focus, QLineEdit#DetailRecordLevelInput:focus, QTextEdit#DetailRecordInput:focus, QTextEdit#DetailResourceNoteInput:focus {{
    border: 1px solid #6f520c;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QWidget#ContentViewport, QWidget#ContentWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: {COLOR_SURFACE_2};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    border-radius: 5px;
}}
"""


def build_app_qss(text_color: str = COLOR_TEXT, theme_color: str = COLOR_SURFACE_2) -> str:
    text = ArchiveWindow._normal_color(text_color, COLOR_TEXT)
    theme = ArchiveWindow._normal_color(theme_color, COLOR_SURFACE_2)
    style = APP_QSS.replace(COLOR_TEXT, text).replace(COLOR_MUTED, text)
    if theme == COLOR_SURFACE_2:
        return style

    theme_qcolor = QColor(theme)
    hover = theme_qcolor.darker(108).name()
    border = theme_qcolor.darker(170).name()
    surface = theme_qcolor.lighter(104).name()
    replacements = {
        COLOR_SURFACE: surface,
        COLOR_SURFACE_2: theme,
        COLOR_SURFACE_3: hover,
        COLOR_PRIMARY: theme,
        COLOR_PRIMARY_HOVER: hover,
        COLOR_SUCCESS: surface,
        COLOR_SUCCESS_HOVER: hover,
        COLOR_BORDER: border,
        "#ead9ad": theme_qcolor.darker(104).name(),
        "#c3a65c": border,
        "#6f520c": border,
    }
    for source, target in replacements.items():
        style = style.replace(source, target)
    return style


def main(workspace: Path | None = None) -> None:
    set_windows_app_user_model_id()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, BASE_FONT_POINT_SIZE))
    window = ArchiveWindow(workspace or Path.cwd())
    window.show()
    app.exec()
