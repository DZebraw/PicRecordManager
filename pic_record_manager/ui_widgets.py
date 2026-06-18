from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

from .archive_store import Album, Photo
from .image_preview import load_preview_pixmap
from .theme_assets import ThemeAssets
from .ui_constants import (
    BASE_FONT_POINT_SIZE,
    COLOR_MUTED,
    DETAIL_IMAGE_FINAL_SIZE,
    FONT_FAMILY,
    PHOTO_CARD_HEIGHT,
    PHOTO_CARD_META_HEIGHT,
    PHOTO_CARD_PREVIEW_HEIGHT,
    PHOTO_CARD_TITLE_HEIGHT,
    PHOTO_CARD_WIDTH,
    SIDEBAR_WIDTH,
)


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
    def __init__(self, parent: QWidget | None = None, theme: ThemeAssets | None = None):
        super().__init__(parent)
        self.setObjectName("ImagePreview")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._pixmaps: list[QPixmap] = []
        self._empty_text = "空档案"
        self.stack_depth = 0
        self.scale_mode = Qt.AspectRatioMode.KeepAspectRatio
        ground_path = theme.ground_pixmap() if theme else None
        self._ground_pixmap = QPixmap(str(ground_path)) if ground_path else QPixmap()

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
            self._draw_layer(painter, self._pixmaps[1], available.translated(12, 7), opacity=1.0, rotation=2.6)
        if len(self._pixmaps) > 2:
            self._draw_layer(painter, self._pixmaps[2], available.translated(20, 13), opacity=1.0, rotation=4.8)
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
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(2, 6, 23, 90))
        painter.drawRoundedRect(target.translated(0, 8), 10, 10)
        border_width = 8
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
        painter.drawPixmap(target, scaled, QRectF(scaled.rect()))
        painter.restore()


class TiltImagePreview(QWidget):
    MAX_OFFSET_X = 22.0
    MAX_OFFSET_Y = 16.0
    MAX_TILT_X = 9.0
    MAX_TILT_Y = 12.0
    EASING = 0.18

    def __init__(self, parent: QWidget | None = None, theme: ThemeAssets | None = None):
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
        ground_path = theme.ground_pixmap() if theme else None
        self._ground_pixmap = QPixmap(str(ground_path)) if ground_path else QPixmap()
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

        available = QRectF(self.rect().adjusted(48, 48, -48, -48)).translated(self.current_offset)
        tilt_rotation = self.current_tilt.y() * 0.22

        for index, pixmap in enumerate(reversed(self._stack_pixmaps), start=1):
            layer_rect = QRectF(available).translated(22 * index, -14 * index)
            self._draw_pixmap_layer(painter, pixmap, layer_rect, opacity=1.0, rotation=tilt_rotation + 2.8 * index)
        if self.page_transition_active and not self._incoming_pixmap.isNull():
            direction = 1 if self.page_transition_direction == "next" else -1
            progress = self.page_transition_progress
            outgoing_offset = -direction * progress * self.width()
            incoming_offset = direction * (1.0 - progress) * self.width()
            self._draw_pixmap_layer(painter, self._pixmap, QRectF(available).translated(outgoing_offset, 0), opacity=max(0.0, 1.0 - progress * 0.35), rotation=tilt_rotation)
            self._draw_pixmap_layer(painter, self._incoming_pixmap, QRectF(available).translated(incoming_offset, 0), opacity=min(1.0, 0.45 + progress * 0.55), rotation=tilt_rotation)
        else:
            self._draw_pixmap_layer(painter, self._pixmap, QRectF(available), opacity=1.0, rotation=tilt_rotation)

    def _draw_pixmap_layer(self, painter: QPainter, pixmap: QPixmap, rect: QRectF, *, opacity: float, rotation: float) -> None:
        scaled = pixmap.scaled(rect.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        painter.save()
        painter.setOpacity(opacity)
        center = rect.center()
        painter.translate(center)
        painter.rotate(rotation)
        target = QRectF(-scaled.width() / 2, -scaled.height() / 2, scaled.width(), scaled.height())
        border_width = 20
        border_rect = target.adjusted(-border_width, -border_width, border_width, border_width)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(2, 6, 23, 95))
        painter.drawRoundedRect(border_rect.translated(0, 18), 18, 18)
        if not self._ground_pixmap.isNull():
            ground_scaled = self._ground_pixmap.scaled(border_rect.size().toSize(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(border_rect, ground_scaled, QRectF(ground_scaled.rect()))
        else:
            painter.setBrush(QColor(255, 255, 255))
            painter.drawRoundedRect(border_rect, 14, 14)
        painter.drawPixmap(target, scaled, QRectF(scaled.rect()))
        painter.restore()

    def _start_tilt_animation(self) -> None:
        if not self._animation_timer.isActive():
            self._animation_timer.start()

    def _is_settled(self) -> bool:
        return (
            abs(self.current_offset.x() - self.target_offset.x()) < 0.1
            and abs(self.current_offset.y() - self.target_offset.y()) < 0.1
            and abs(self.current_tilt.x() - self.target_tilt.x()) < 0.1
            and abs(self.current_tilt.y() - self.target_tilt.y()) < 0.1
        )

    @classmethod
    def _ease_point(cls, current: QPointF, target: QPointF) -> QPointF:
        return QPointF(
            current.x() + (target.x() - current.x()) * cls.EASING,
            current.y() + (target.y() - current.y()) * cls.EASING,
        )


class AlbumItem(QFrame):
    def __init__(self, album: Album, index: int, selected: bool, select_callback, delete_callback, rename_callback):
        super().__init__()
        self.album = album
        self.rename_callback = rename_callback
        self.setObjectName("AlbumItem")
        self.setFixedWidth(SIDEBAR_WIDTH - 36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.select_button = AnimatedButton(f"{index}. {album.name}")
        self.select_button.setObjectName("SelectedAlbumButton" if selected else "AlbumButton")
        self.select_button.setFixedWidth(SIDEBAR_WIDTH - 36)
        self.select_button.clicked.connect(lambda _checked=False: select_callback(self.album.id))
        self.select_button.installEventFilter(self)
        layout.addWidget(self.select_button)
        self.rename_editor = QLineEdit(album.name)
        self.rename_editor.hide()
        self.rename_editor.returnPressed.connect(self.commit_rename)
        self.rename_editor.editingFinished.connect(self.commit_rename)
        layout.addWidget(self.rename_editor)
        self.delete_button = AnimatedButton("×", self)
        self.delete_button.setObjectName("AlbumDeleteButton")
        self.delete_button.setAccessibleName(f"删除书签 {album.name}")
        self.delete_button.setToolTip("删除书签")
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.clicked.connect(lambda _checked=False: delete_callback(self.album.id))
        self._position_delete_button()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin_rename()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self.select_button
            and event.type() == QEvent.Type.MouseButtonDblClick
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.begin_rename()
            return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_delete_button()

    def _position_delete_button(self) -> None:
        self.delete_button.move(self.width() - self.delete_button.width() - 5, 5)
        self.delete_button.raise_()

    def begin_rename(self) -> None:
        self.select_button.hide()
        self.rename_editor.show()
        self.rename_editor.setFocus()
        self.rename_editor.selectAll()

    def commit_rename(self) -> None:
        if not self.rename_editor.isVisible():
            return
        self.select_button.show()
        self.rename_editor.hide()
        self.rename_callback(self.album.id, self.rename_editor.text())


class PhotoCard(AnimatedFrame):
    def __init__(self, photo: Photo, open_callback, delete_callback=None, theme: ThemeAssets | None = None):
        super().__init__()
        self.photo = photo
        self.open_callback = open_callback
        self.delete_callback = delete_callback
        self.setObjectName("PhotoCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(PHOTO_CARD_WIDTH, PHOTO_CARD_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 6)
        layout.setSpacing(2)
        self.delete_button = AnimatedButton("×", self)
        self.delete_button.setObjectName("PhotoDeleteButton")
        self.delete_button.setAccessibleName(f"删除照片 {photo.title}")
        self.delete_button.setToolTip("删除照片")
        self.delete_button.setFixedSize(26, 26)
        self.delete_button.clicked.connect(self._delete_photo)
        self._position_delete_button()
        self.preview = StackedImagePreview(theme=theme)
        self.preview.setFixedHeight(PHOTO_CARD_PREVIEW_HEIGHT)
        set_photo_pixmap(self.preview, photo, 220, 120)
        layout.addWidget(self.preview)
        self.title_label = QLabel(photo.title)
        self.title_label.setObjectName("CardTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setContentsMargins(0, 0, 0, 0)
        self.title_label.setMaximumHeight(PHOTO_CARD_TITLE_HEIGHT)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        title_font = QFont(FONT_FAMILY, BASE_FONT_POINT_SIZE)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)
        self.meta_label = QLabel(photo_meta_text(photo))
        self.meta_label.setObjectName("CardMetaText")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meta_label.setContentsMargins(0, 0, 0, 0)
        self.meta_label.setMaximumHeight(PHOTO_CARD_META_HEIGHT)
        self.meta_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
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
        self.setObjectName("PhotoCardContainer")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        preview = QLabel()
        preview.setObjectName("ImagePreview")
        preview.setFixedSize(112, 72)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_photo_pixmap(preview, photo, 112, 72)
        layout.addWidget(preview)
        text = QVBoxLayout()
        title = QLabel(photo.title)
        title.setObjectName("CardTitle")
        meta = QLabel(photo_meta_text(photo))
        meta.setObjectName("CardMetaText")
        text.addWidget(title)
        text.addWidget(meta)
        layout.addLayout(text)
        layout.addStretch()
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
