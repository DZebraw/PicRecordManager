from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPointF, QParallelAnimationGroup, QPropertyAnimation, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
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
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyleOption,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .archive_store import Album, ArchiveStore, Photo
from .image_preview import load_preview_pixmap


APP_TITLE = "档案管理"
WINDOW_SIZE = (1180, 740)
SIDEBAR_WIDTH = 220
PHOTO_GRID_COLUMNS = 3
PHOTO_GRID_ROWS = 2
PHOTO_CARD_WIDTH = 280
PHOTO_CARD_HEIGHT = 250
FONT_FAMILY = "Microsoft YaHei UI"
FONT_STACK = '"Microsoft YaHei UI", "Segoe UI Variable", "Segoe UI"'
BASE_FONT_POINT_SIZE = 11
TRANSITION_ANIMATION_MS = 460
DETAIL_IMAGE_FINAL_SIZE = QSize(440, 420)
DETAIL_IMAGE_SLIDE_OFFSET = 220

COLOR_BG = "#0f172a"
COLOR_BG_GRADIENT_START = "#1e293b"
COLOR_BG_GRADIENT_END = "#0f172a"
COLOR_SURFACE = "rgba(17, 24, 39, 0.7)"
COLOR_SURFACE_2 = "rgba(31, 41, 55, 0.6)"
COLOR_SURFACE_3 = "rgba(39, 52, 73, 0.5)"
COLOR_TEXT = "#f8fafc"
COLOR_MUTED = "#94a3b8"
COLOR_BORDER = "rgba(51, 65, 85, 0.5)"
COLOR_PRIMARY = "#2563eb"
COLOR_PRIMARY_HOVER = "#1d4ed8"
COLOR_SUCCESS = "#059669"
COLOR_SUCCESS_HOVER = "#047857"
COLOR_DANGER = "#dc2626"


def apply_preview_glow(widget: QWidget) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(0)
    effect.setOffset(0, 0)
    effect.setColor(QColor(59, 130, 246, 145))
    widget.setGraphicsEffect(effect)
    widget.setProperty("previewGlow", False)
    widget.setProperty("interactiveMotion", False)


class AnimatedButton(QPushButton):
    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setProperty("interactiveMotion", False)


class AnimatedFrame(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        apply_preview_glow(self)

    def enterEvent(self, event) -> None:
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsDropShadowEffect):
            effect.setBlurRadius(36)
        self.setProperty("previewGlow", True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsDropShadowEffect):
            effect.setBlurRadius(0)
        self.setProperty("previewGlow", False)
        super().leaveEvent(event)


class StackedImagePreview(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Preview")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._pixmaps: list[QPixmap] = []
        self._empty_text = "空档案"
        self.stack_depth = 0
        self.scale_mode = Qt.AspectRatioMode.KeepAspectRatio
        self._ground_pixmap = QPixmap("C:/Users/daiwei/Desktop/PicRecordManager/Themes/Default/PicGround.png")

    def set_preview_pixmaps(self, pixmaps: list[QPixmap], empty_text: str = "空档案") -> None:
        self._pixmaps = [pixmap for pixmap in pixmaps if not pixmap.isNull()]
        self._empty_text = empty_text
        self.stack_depth = len(self._pixmaps)
        self.update()

    def text(self) -> str:
        return self._empty_text if not self._pixmaps else ""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        option = QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)

        if not self._pixmaps:
            painter.setPen(QColor(COLOR_MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_text)
            return

        available = self.rect().adjusted(14, 10, -14, -10)
        if len(self._pixmaps) > 1:
            self._draw_layer(painter, self._pixmaps[1], available.translated(12, -7), opacity=0.55, rotation=2.6)
        if len(self._pixmaps) > 2:
            self._draw_layer(painter, self._pixmaps[2], available.translated(20, -13), opacity=0.32, rotation=4.8)
        self._draw_layer(painter, self._pixmaps[0], available, opacity=1.0, rotation=0.0)

    def _draw_layer(self, painter: QPainter, pixmap: QPixmap, rect, *, opacity: float, rotation: float) -> None:
        scaled = pixmap.scaled(
            rect.size(),
            self.scale_mode,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.save()
        painter.setOpacity(opacity)
        center = QRectF(rect).center()
        painter.translate(center)
        painter.rotate(rotation)
        target = QRectF(-scaled.width() / 2, -scaled.height() / 2, scaled.width(), scaled.height())
        # 绘制阴影
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(2, 6, 23, 90))
        painter.drawRoundedRect(target.translated(0, 8), 10, 10)
        # 绘制相纸背景图片
        border_width = 18
        border_rect = target.adjusted(-border_width, -border_width, border_width, border_width)
        if not self._ground_pixmap.isNull():
            ground_scaled = self._ground_pixmap.scaled(
                border_rect.size().toSize(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(border_rect, ground_scaled, QRectF(ground_scaled.rect()))
        else:
            painter.setBrush(QColor(255, 255, 255))
            painter.drawRoundedRect(border_rect, 8, 8)
        # 绘制图片
        painter.drawPixmap(target, scaled, QRectF(scaled.rect()))
        painter.restore()


class TiltImagePreview(QWidget):
    MAX_OFFSET_X = 22.0
    MAX_OFFSET_Y = 16.0
    MAX_TILT_X = 9.0
    MAX_TILT_Y = 12.0
    EASING = 0.18

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DetailImage")
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumSize(DETAIL_IMAGE_FINAL_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tilt_motion_enabled = True
        self.target_offset = QPointF(0, 0)
        self.current_offset = QPointF(0, 0)
        self.target_tilt = QPointF(0, 0)
        self.current_tilt = QPointF(0, 0)
        self._pixmap = QPixmap()
        self._stack_pixmaps: list[QPixmap] = []
        self._incoming_pixmap = QPixmap()
        self._ground_pixmap = QPixmap("C:/Users/daiwei/Desktop/PicRecordManager/Themes/Default/PicGround.png")
        self.stack_depth = 0
        self.page_transition_active = False
        self.page_transition_direction = ""
        self.page_transition_progress = 1.0
        self._empty_text = "无法预览此图片"
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(16)
        self._animation_timer.timeout.connect(self.advance_tilt_frame)
        self._page_transition_timer = QTimer(self)
        self._page_transition_timer.setInterval(16)
        self._page_transition_timer.timeout.connect(self.advance_page_transition_frame)

    def set_preview_pixmap(self, pixmap: QPixmap) -> None:
        self.set_preview_stack([pixmap] if not pixmap.isNull() else [])

    def set_preview_stack(self, pixmaps: list[QPixmap], *, animate: bool = False, direction: str = "next") -> None:
        clean_pixmaps = [pixmap for pixmap in pixmaps if not pixmap.isNull()]
        next_front = clean_pixmaps[0] if clean_pixmaps else QPixmap()
        if animate and not self._pixmap.isNull() and not next_front.isNull():
            self._incoming_pixmap = next_front
            self.page_transition_active = True
            self.page_transition_direction = direction
            self.page_transition_progress = 0.0
            self._page_transition_timer.start()
        else:
            self._incoming_pixmap = QPixmap()
            self.page_transition_active = False
            self.page_transition_direction = direction if animate else ""
            self.page_transition_progress = 1.0
            self._pixmap = next_front
        self._stack_pixmaps = clean_pixmaps[1:3]
        self.stack_depth = len(clean_pixmaps)
        self.update()

    def set_empty_text(self, text: str) -> None:
        self._empty_text = text
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return super().mouseMoveEvent(event)
        position = event.position()
        normalized_x = max(-1.0, min(1.0, (position.x() / self.width() - 0.5) * 2.0))
        normalized_y = max(-1.0, min(1.0, (position.y() / self.height() - 0.5) * 2.0))
        self.target_offset = QPointF(normalized_x * self.MAX_OFFSET_X, normalized_y * self.MAX_OFFSET_Y)
        self.target_tilt = QPointF(-normalized_y * self.MAX_TILT_X, normalized_x * self.MAX_TILT_Y)
        self._start_tilt_animation()
        return super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self.target_offset = QPointF(0, 0)
        self.target_tilt = QPointF(0, 0)
        self._start_tilt_animation()
        return super().leaveEvent(event)

    def advance_tilt_frame(self) -> None:
        self.current_offset = self._ease_point(self.current_offset, self.target_offset)
        self.current_tilt = self._ease_point(self.current_tilt, self.target_tilt)
        self.update()
        if self._is_settled():
            self.current_offset = QPointF(self.target_offset)
            self.current_tilt = QPointF(self.target_tilt)
            self._animation_timer.stop()

    def advance_page_transition_frame(self) -> None:
        self.page_transition_progress = min(1.0, self.page_transition_progress + 0.08)
        if self.page_transition_progress >= 1.0:
            if not self._incoming_pixmap.isNull():
                self._pixmap = self._incoming_pixmap
            self._incoming_pixmap = QPixmap()
            self.page_transition_active = False
            self._page_transition_timer.stop()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        option = QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)

        if self._pixmap.isNull():
            painter.setPen(QColor(COLOR_MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_text)
            return

        available = self.rect().adjusted(32, 32, -32, -32)
        center = QPointF(self.width() / 2, self.height() / 2) + self.current_offset

        painter.save()
        painter.translate(center)
        painter.shear(self.current_tilt.y() / 85.0, self.current_tilt.x() / 95.0)
        painter.rotate(self.current_tilt.y() * 0.22)
        for index, pixmap in enumerate(reversed(self._stack_pixmaps), start=1):
            layer_rect = QRectF(available).translated(22 * index, -14 * index)
            self._draw_pixmap_layer(painter, pixmap, layer_rect, opacity=max(0.35, 0.62 - index * 0.14), rotation=2.8 * index)
        if self.page_transition_active and not self._incoming_pixmap.isNull():
            direction = 1 if self.page_transition_direction == "next" else -1
            progress = self.page_transition_progress
            outgoing_rect = QRectF(available).translated(-direction * progress * 90, progress * 16)
            incoming_rect = QRectF(available).translated(direction * (1.0 - progress) * 90, -(1.0 - progress) * 10)
            self._draw_pixmap_layer(painter, self._pixmap, outgoing_rect, opacity=1.0 - progress * 0.72, rotation=-direction * progress * 8)
            self._draw_pixmap_layer(painter, self._incoming_pixmap, incoming_rect, opacity=0.35 + progress * 0.65, rotation=direction * (1.0 - progress) * 8)
        else:
            self._draw_pixmap_layer(painter, self._pixmap, QRectF(available), opacity=1.0, rotation=0.0)
        painter.restore()

    def _draw_pixmap_layer(self, painter: QPainter, pixmap: QPixmap, rect: QRectF, *, opacity: float, rotation: float) -> None:
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            rect.size().toSize(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        draw_rect = QRectF(
            -scaled.width() / 2,
            -scaled.height() / 2,
            scaled.width(),
            scaled.height(),
        )
        painter.save()
        painter.setOpacity(opacity)
        center = rect.center() - QPointF(self.width() / 2, self.height() / 2)
        painter.translate(center)
        painter.rotate(rotation)
        # 绘制阴影
        shadow_rect = draw_rect.translated(0, 12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(2, 6, 23, 90))
        painter.drawRoundedRect(shadow_rect, 18, 18)
        # 绘制相纸背景图片
        border_width = 24
        border_rect = draw_rect.adjusted(-border_width, -border_width, border_width, border_width)
        if not self._ground_pixmap.isNull():
            ground_scaled = self._ground_pixmap.scaled(
                border_rect.size().toSize(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(border_rect, ground_scaled, QRectF(ground_scaled.rect()))
        else:
            painter.setBrush(QColor(255, 255, 255))
            painter.drawRoundedRect(border_rect, 10, 10)
        # 绘制图片
        painter.drawPixmap(draw_rect, scaled, QRectF(scaled.rect()))
        painter.restore()

    def _start_tilt_animation(self) -> None:
        if not self._animation_timer.isActive():
            self._animation_timer.start()

    def _is_settled(self) -> bool:
        return (
            abs(self.current_offset.x() - self.target_offset.x()) < 0.12
            and abs(self.current_offset.y() - self.target_offset.y()) < 0.12
            and abs(self.current_tilt.x() - self.target_tilt.x()) < 0.08
            and abs(self.current_tilt.y() - self.target_tilt.y()) < 0.08
        )

    def _ease_point(self, current: QPointF, target: QPointF) -> QPointF:
        return QPointF(
            current.x() + (target.x() - current.x()) * self.EASING,
            current.y() + (target.y() - current.y()) * self.EASING,
        )


class ArchiveWindow(QMainWindow):
    FRAMELESS_WINDOW_FLAG = Qt.WindowType.FramelessWindowHint
    DRAG_REGION_HEIGHT = 96

    def __init__(self, workspace: Path):
        super().__init__()
        self.workspace = workspace
        self.store = ArchiveStore(workspace / "data" / "archive.db", workspace / "data" / "media")
        self.albums: list[Album] = []
        self.selected_album_id: int | None = self.store.list_albums()[0].id
        self.page = 1
        self.per_page = 6
        self.query = ""
        self.view_mode = "grid"
        self.current_page = None
        self.detail_photo_id: int | None = None
        self.album_item_widgets: list[AlbumItem] = []
        self._drag_offset: QPoint | None = None
        self.last_transition_direction: str | None = None
        self.detail_transition_animation: QParallelAnimationGroup | None = None
        self.detail_zoom_animation: QPropertyAnimation | None = None
        self.detail_slide_animation: QPropertyAnimation | None = None

        self.setWindowTitle(APP_TITLE)
        self.resize(*WINDOW_SIZE)
        self.setMinimumSize(*WINDOW_SIZE)
        self.setObjectName("ArchiveWindow")
        self.setWindowFlag(self.FRAMELESS_WINDOW_FLAG, True)
        self.setFont(QFont(FONT_FAMILY, BASE_FONT_POINT_SIZE))
        self.setPalette(self._dark_palette())
        self.setStyleSheet(APP_QSS)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._build_list_page()
        self.refresh()

    def _dark_palette(self) -> QPalette:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_BG))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_TEXT))
        palette.setColor(QPalette.ColorRole.Base, QColor(COLOR_SURFACE_2))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLOR_SURFACE))
        palette.setColor(QPalette.ColorRole.Text, QColor(COLOR_TEXT))
        palette.setColor(QPalette.ColorRole.Button, QColor(COLOR_SURFACE_2))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_TEXT))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(COLOR_PRIMARY))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
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

        sidebar_title = QLabel("书签")
        sidebar_title.setObjectName("SidebarTitle")
        sidebar_layout.addWidget(sidebar_title)
        new_album = AnimatedButton("新建书签")
        new_album.clicked.connect(self.create_album)
        sidebar_layout.addWidget(new_album)
        self.album_list_layout = QVBoxLayout()
        self.album_list_layout.setSpacing(8)
        sidebar_layout.addLayout(self.album_list_layout)
        sidebar_layout.addStretch()

        main = QFrame()
        main.setObjectName("MainPanel")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(24, 20, 24, 18)
        main_layout.setSpacing(16)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(6)
        title = QLabel("档案管理")
        title.setObjectName("Title")
        subtitle = QLabel("按书签整理照片档案，预览、检索和编辑基础信息。")
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
        self.page_label = QLabel("")
        self.page_label.setObjectName("MutedText")
        toolbar.addWidget(self.page_label)
        toolbar.addStretch()
        self.search_entry = QLineEdit()
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
        self.status_label = QLabel("")
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
        root.addWidget(main, 1)
        self.stack.addWidget(self.list_page)
        self._install_drag_filter(self.list_page, self.sidebar, main, title, subtitle)

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
            self.content_grid.setColumnStretch(column, 0)
        if not self.current_page.items:
            empty = QLabel("当前书签还没有档案。点击“新建档案”开始添加。")
            empty.setObjectName("EmptyText")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_grid.addWidget(empty, 0, 0, 1, PHOTO_GRID_COLUMNS)
            return

        for index, photo in enumerate(self.current_page.items[: PHOTO_GRID_COLUMNS * PHOTO_GRID_ROWS]):
            row, column = divmod(index, PHOTO_GRID_COLUMNS)
            self.content_grid.addWidget(
                PhotoCard(photo, self.show_detail, self.delete_photo_from_grid),
                row,
                column,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            )

    def show_detail(self, photo: Photo) -> None:
        self.detail_photo_id = photo.id
        self.detail_album_id = photo.album_id
        self.detail_photo_description = photo.description
        self.detail_images = self.store.list_photo_images(photo.id)
        self.detail_image_index = 0
        self.detail_page = QWidget()
        self.detail_page.setObjectName("DetailPage")
        layout = QVBoxLayout(self.detail_page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

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
        self.detail_image_panel.setObjectName("Card")
        image_layout = QVBoxLayout(self.detail_image_panel)
        image_layout.setSpacing(10)
        image_view = QHBoxLayout()
        image_view.setSpacing(10)
        self.detail_prev_image_button = AnimatedButton("<")
        self.detail_prev_image_button.setObjectName("ImageNavButton")
        self.detail_prev_image_button.setAccessibleName("上一张图片")
        self.detail_prev_image_button.setToolTip("上一张图片")
        self.detail_prev_image_button.setFixedSize(44, 44)
        self.detail_prev_image_button.clicked.connect(self.previous_detail_image)
        image_view.addWidget(self.detail_prev_image_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.detail_image = TiltImagePreview()
        image_view.addWidget(self.detail_image, 1)
        self.detail_next_image_button = AnimatedButton(">")
        self.detail_next_image_button.setObjectName("ImageNavButton")
        self.detail_next_image_button.setAccessibleName("下一张图片")
        self.detail_next_image_button.setToolTip("下一张图片")
        self.detail_next_image_button.setFixedSize(44, 44)
        self.detail_next_image_button.clicked.connect(self.next_detail_image)
        image_view.addWidget(self.detail_next_image_button, 0, Qt.AlignmentFlag.AlignVCenter)
        image_layout.addLayout(image_view, 1)
        image_actions = QHBoxLayout()
        self.detail_image_counter = QLabel("")
        self.detail_image_counter.setObjectName("MutedText")
        image_actions.addWidget(self.detail_image_counter)
        image_actions.addStretch()
        self.detail_import_images_button = AnimatedButton("导入图片")
        self.detail_import_images_button.setObjectName("PrimaryButton")
        self.detail_import_images_button.clicked.connect(self.import_images_to_detail)
        image_actions.addWidget(self.detail_import_images_button)
        image_layout.addLayout(image_actions)
        split.addWidget(self.detail_image_panel, 1)

        editor = QFrame()
        editor.setObjectName("Card")
        editor_layout = QVBoxLayout(editor)
        editor_layout.setSpacing(12)
        archive_heading = QLabel("档案信息")
        archive_heading.setObjectName("SectionTitle")
        archive_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor_layout.addWidget(archive_heading)
        editor_layout.addWidget(QLabel("标题"))
        self.detail_title = QLineEdit(photo.title)
        editor_layout.addWidget(self.detail_title)
        editor_layout.addWidget(QLabel("日期"))
        self.detail_display_date = QLineEdit(photo.display_date)
        self.detail_display_date.setPlaceholderText("例如 2026-06-17")
        editor_layout.addWidget(self.detail_display_date)
        editor_layout.addSpacing(8)
        self.detail_record_label = QLabel("记录")
        self.detail_record_label.setObjectName("SectionTitle")
        self.detail_record_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor_layout.addWidget(self.detail_record_label)
        self.detail_record = QTextEdit()
        self.detail_record.setPlaceholderText("记录当前图片的信息")
        editor_layout.addWidget(self.detail_record, 1)
        self._refresh_detail_image()
        actions = QHBoxLayout()
        actions.addStretch()
        save_button = AnimatedButton("保存")
        save_button.setObjectName("SuccessButton")
        save_button.clicked.connect(self.save_detail)
        actions.addWidget(save_button)
        editor_layout.addLayout(actions)
        split.addWidget(editor, 1)

        layout.addLayout(split, 1)
        self.stack.addWidget(self.detail_page)
        self.stack.setCurrentWidget(self.detail_page)
        self._install_drag_filter(self.detail_page)
        self._run_detail_transition("enter")

    def save_detail(self) -> None:
        if self.detail_photo_id is None:
            return
        self._save_current_image_record()
        photo = self.store.update_photo(
            self.detail_photo_id,
            title=self.detail_title.text(),
            description=self.detail_photo_description,
            album_id=self.detail_album_id,
            display_date=self.detail_display_date.text(),
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
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择档案图片",
            str(self.workspace),
            "图片文件 (*.png *.gif *.jpg *.jpeg *.bmp);;所有文件 (*.*)",
        )
        if not files:
            return
        self._save_current_image_record()
        was_empty = not self.detail_images
        self.detail_images = self.store.add_photo_images(self.detail_photo_id, [Path(filename) for filename in files])
        self.detail_image_index = 0 if was_empty else min(self.detail_image_index, len(self.detail_images) - 1)
        self._refresh_detail_image()

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
        total = len(self.detail_images)
        if total == 0:
            self.detail_image.set_empty_text("暂无图片")
            self.detail_image.set_preview_stack([])
            self.detail_image_counter.setText("0 / 0")
            self.detail_prev_image_button.setEnabled(False)
            self.detail_next_image_button.setEnabled(False)
            self._load_current_image_record()
            return
        self.detail_image_index = max(0, min(self.detail_image_index, total - 1))
        self._set_detail_image_stack(animate=animate, direction=direction)
        self.detail_image_counter.setText(f"{self.detail_image_index + 1} / {total}")
        can_cycle = total > 1
        self.detail_prev_image_button.setEnabled(can_cycle)
        self.detail_next_image_button.setEnabled(can_cycle)
        self._load_current_image_record()

    def _save_current_image_record(self) -> None:
        if not hasattr(self, "detail_record"):
            return
        if not self.detail_images:
            return
        image = self.detail_images[self.detail_image_index]
        updated = self.store.update_photo_image_record(image.id, self.detail_record.toPlainText())
        self.detail_images[self.detail_image_index] = updated

    def _load_current_image_record(self) -> None:
        if not hasattr(self, "detail_record"):
            return
        if not self.detail_images:
            self.detail_record.clear()
            self.detail_record.setEnabled(False)
            return
        self.detail_record.setEnabled(True)
        self.detail_record.setPlainText(self.detail_images[self.detail_image_index].record)

    def back_to_list(self) -> None:
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
        self.store.delete_photo(photo_id)
        self.refresh()

    def delete_album_from_sidebar(self, album_id: int) -> None:
        self.store.delete_album(album_id)
        remaining_albums = self.store.list_albums()
        if self.selected_album_id == album_id:
            self.selected_album_id = remaining_albums[0].id if remaining_albums else None
        self.page = 1
        self.refresh()

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
        QMessageBox.information(
            self,
            "设置",
            f"数据库：{self.workspace / 'data' / 'archive.db'}\n媒体目录：{self.workspace / 'data' / 'media'}",
        )

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
            pixmap = load_preview_pixmap(path, size.width(), size.height())
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
            return load_preview_pixmap(path, size.width(), size.height())
        except OSError:
            return QPixmap()

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


class AlbumItem(QFrame):
    def __init__(self, album: Album, index: int, selected: bool, select_callback, delete_callback, rename_callback):
        super().__init__()
        self.album = album
        self.select_callback = select_callback
        self.delete_callback = delete_callback
        self.rename_callback = rename_callback
        self.setObjectName("AlbumItem")
        self.setFixedWidth(SIDEBAR_WIDTH - 36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.select_button = AnimatedButton(f"{index}. {album.name}")
        self.select_button.setObjectName("SelectedAlbumButton" if selected else "AlbumButton")
        self.select_button.setFixedWidth(SIDEBAR_WIDTH - 36)
        self.select_button.clicked.connect(lambda _checked=False: self.select_callback(self.album.id))
        self.select_button.installEventFilter(self)
        layout.addWidget(self.select_button, 1)

        self.rename_editor = QLineEdit(self)
        self.rename_editor.setObjectName("AlbumRenameEditor")
        self.rename_editor.setText(album.name)
        self.rename_editor.hide()
        self.rename_editor.returnPressed.connect(self.commit_rename)
        self.rename_editor.editingFinished.connect(self.commit_rename)

        self.delete_button = AnimatedButton("×", self)
        self.delete_button.setObjectName("AlbumDeleteButton")
        self.delete_button.setAccessibleName(f"删除书签 {album.name}")
        self.delete_button.setToolTip("删除书签")
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.clicked.connect(lambda _checked=False: self.delete_callback(self.album.id))
        self._position_delete_button()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.select_button and event.type() == QEvent.Type.MouseButtonDblClick:
            self.begin_rename()
            return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_delete_button()

    def _position_delete_button(self) -> None:
        self.delete_button.move(self.width() - self.delete_button.width() - 5, 5)
        self.delete_button.raise_()
        self.rename_editor.setGeometry(self.select_button.geometry())

    def begin_rename(self) -> None:
        self.rename_editor.setText(self.album.name)
        self.rename_editor.setGeometry(self.select_button.geometry())
        self.rename_editor.show()
        self.rename_editor.raise_()
        self.rename_editor.setFocus(Qt.FocusReason.MouseFocusReason)
        self.rename_editor.selectAll()

    def commit_rename(self) -> None:
        if not self.rename_editor.isVisible():
            return
        self.rename_editor.hide()
        self.rename_callback(self.album.id, self.rename_editor.text())


class PhotoCard(AnimatedFrame):
    def __init__(self, photo: Photo, open_callback, delete_callback=None):
        super().__init__()
        self.photo = photo
        self.open_callback = open_callback
        self.delete_callback = delete_callback
        self.setObjectName("PhotoCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(PHOTO_CARD_WIDTH, PHOTO_CARD_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 12)
        layout.setSpacing(12)
        self.delete_button = AnimatedButton("×", self)
        self.delete_button.setObjectName("PhotoDeleteButton")
        self.delete_button.setAccessibleName(f"删除照片 {photo.title}")
        self.delete_button.setToolTip("删除照片")
        self.delete_button.setFixedSize(26, 26)
        self.delete_button.clicked.connect(self._delete_photo)
        self._position_delete_button()
        self.preview = StackedImagePreview()
        self.preview.setFixedHeight(150)
        set_photo_pixmap(self.preview, photo, 250, 140)
        layout.addWidget(self.preview)
        self.title_label = QLabel(photo.title)
        self.title_label.setObjectName("CardTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        title_font = QFont(FONT_FAMILY, BASE_FONT_POINT_SIZE + 3)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)
        self.meta_label = QLabel(photo_meta_text(photo))
        self.meta_label.setObjectName("CardMetaText")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.meta_label)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_callback(self.photo)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_delete_button()

    def _position_delete_button(self) -> None:
        self.delete_button.move(self.width() - self.delete_button.width() - 12, 12)
        self.delete_button.raise_()

    def _delete_photo(self) -> None:
        if self.delete_callback is not None:
            self.delete_callback(self.photo.id)


class PhotoRow(AnimatedFrame):
    def __init__(self, photo: Photo, open_callback, delete_callback=None):
        super().__init__()
        self.photo = photo
        self.open_callback = open_callback
        self.delete_callback = delete_callback
        self.setObjectName("PhotoCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        preview = QLabel()
        preview.setObjectName("Preview")
        preview.setFixedSize(112, 72)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_photo_pixmap(preview, photo, 112, 72)
        layout.addWidget(preview)
        text = QVBoxLayout()
        title = QLabel(photo.title)
        title.setObjectName("CardTitle")
        text.addWidget(title)
        meta = QLabel(f"{photo.album_name} · {photo.original_name} · {photo.display_date}")
        meta.setObjectName("MutedText")
        text.addWidget(meta)
        layout.addLayout(text, 1)
        self.delete_button = AnimatedButton("×", self)
        self.delete_button.setObjectName("PhotoDeleteButton")
        self.delete_button.setAccessibleName(f"删除照片 {photo.title}")
        self.delete_button.setToolTip("删除照片")
        self.delete_button.setFixedSize(26, 26)
        self.delete_button.clicked.connect(self._delete_photo)
        self._position_delete_button()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_callback(self.photo)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_delete_button()

    def _position_delete_button(self) -> None:
        self.delete_button.move(self.width() - self.delete_button.width() - 12, 12)
        self.delete_button.raise_()

    def _delete_photo(self) -> None:
        if self.delete_callback is not None:
            self.delete_callback(self.photo.id)


def set_photo_pixmap(label: QWidget, photo: Photo, width: int, height: int) -> None:
    try:
        pixmap = load_preview_pixmap(photo.stored_path, width, height)
    except OSError:
        pixmap = QPixmap()
    if pixmap.isNull():
        empty_text = "空档案" if photo.image_count == 0 else "图片"
        if isinstance(label, StackedImagePreview):
            label.set_preview_pixmaps([], empty_text=empty_text)
        elif isinstance(label, QLabel):
            label.setText(empty_text)
    else:
        if isinstance(label, StackedImagePreview):
            pixmaps = [pixmap for _ in range(max(1, min(photo.image_count, 3)))]
            label.set_preview_pixmaps(pixmaps)
        elif isinstance(label, QLabel):
            label.setText("")
            label.setPixmap(pixmap)


def photo_meta_text(photo: Photo) -> str:
    if photo.display_date.strip():
        return f"{photo.album_name} · {photo.display_date.strip()}"
    return photo.album_name


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
QMainWindow, QWidget#ListPage, QWidget#DetailPage {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLOR_BG_GRADIENT_START}, stop:1 {COLOR_BG_GRADIENT_END});
    color: {COLOR_TEXT};
    font-family: {FONT_STACK};
    font-size: 15px;
    font-weight: 400;
}}
QFrame#Sidebar, QFrame#Card, QFrame#PhotoCard {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}}
QFrame#AlbumItem {{
    background: transparent;
    border: none;
}}
QFrame#MainPanel {{
    background: transparent;
}}
QLabel {{
    color: {COLOR_TEXT};
    background: transparent;
    font-size: 15px;
}}
QLabel#Title {{
    font-size: 30px;
    font-weight: 700;
}}
QLabel#Subtitle {{
    color: {COLOR_MUTED};
    font-size: 14px;
    font-weight: 400;
}}
QLabel#MutedText {{
    color: {COLOR_MUTED};
    font-size: 13px;
    font-weight: 400;
}}
QLabel#CardMetaText {{
    color: {COLOR_MUTED};
    font-size: 13px;
    font-weight: 500;
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
QLabel#Preview, QWidget#Preview, QWidget#DetailImage {{
    background: {COLOR_SURFACE_2};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
}}
QPushButton {{
    background: {COLOR_SURFACE_2};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 9px 13px;
    min-height: 22px;
    font-size: 14px;
    font-weight: 600;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
}}
QPushButton:hover {{
    background: {COLOR_SURFACE_3};
}}
QPushButton:pressed {{
    background: #1e3a5f;
}}
QPushButton#PrimaryButton, QPushButton#SelectedAlbumButton {{
    background: {COLOR_PRIMARY};
    border-color: {COLOR_PRIMARY};
    color: white;
}}
QPushButton#PrimaryButton:hover, QPushButton#SelectedAlbumButton:hover {{
    background: {COLOR_PRIMARY_HOVER};
}}
QPushButton#SuccessButton {{
    background: {COLOR_SUCCESS};
    border-color: {COLOR_SUCCESS};
    color: white;
}}
QPushButton#SuccessButton:hover {{
    background: {COLOR_SUCCESS_HOVER};
}}
QPushButton#AlbumButton {{
    text-align: left;
    font-weight: 500;
}}
QPushButton#PhotoDeleteButton, QPushButton#AlbumDeleteButton {{
    background: rgba(15, 23, 42, 0.78);
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
    color: {COLOR_MUTED};
    font-size: 14px;
    font-weight: 700;
    padding: 0;
    min-width: 22px;
    min-height: 22px;
}}
QPushButton#PhotoDeleteButton:hover, QPushButton#AlbumDeleteButton:hover {{
    background: {COLOR_DANGER};
    border-color: {COLOR_DANGER};
    color: white;
}}
QPushButton#WindowMinimizeButton, QPushButton#WindowMaximizeButton, QPushButton#WindowCloseButton {{
    background: transparent;
    border: 1px solid transparent;
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
    background: {COLOR_SURFACE_2};
    border-color: {COLOR_BORDER};
    color: {COLOR_TEXT};
}}
QPushButton#WindowCloseButton:hover {{
    background: {COLOR_DANGER};
    border-color: {COLOR_DANGER};
    color: white;
}}
QPushButton#ImageNavButton {{
    background: rgba(15, 23, 42, 0.68);
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
    background: rgba(15, 23, 42, 0.28);
    border-color: rgba(51, 65, 85, 0.55);
}}
QLineEdit, QTextEdit, QComboBox {{
    background: {COLOR_SURFACE_2};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 9px 11px;
    font-size: 15px;
    font-weight: 400;
    min-height: 24px;
    selection-background-color: {COLOR_PRIMARY};
}}
QTextEdit {{
    padding: 12px;
}}
QScrollArea {{
    border: none;
    background: {COLOR_BG};
}}
QWidget#ContentViewport, QWidget#ContentWidget {{
    background: {COLOR_BG};
}}
QScrollBar:vertical {{
    background: {COLOR_BG};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    border-radius: 5px;
}}
"""


def main(workspace: Path | None = None) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, BASE_FONT_POINT_SIZE))
    window = ArchiveWindow(workspace or Path.cwd())
    window.show()
    app.exec()
