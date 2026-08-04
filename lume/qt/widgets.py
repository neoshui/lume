"""Custom widget components for Lume Qt UI — result rows, clipboard chips."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QPixmap, QPainter, QPen, QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from lume.qt.utils import _icon, _fallback_icon
from lume.search import SearchResult

class ResultRow(QWidget):
    """Two-line result row matching the original launcher's visual hierarchy."""
    def __init__(self, result: SearchResult, show_description: bool = True, grid: bool = False, parent=None):
        super().__init__(parent)
        self._grid = grid
        self._selected = False
        self._selection_color = QColor("#6988b5")
        self.setObjectName("resultRow")
        layout = QVBoxLayout(self) if grid else QHBoxLayout(self)
        layout.setContentsMargins(8 if grid else 12, 8 if grid else 8, 8 if grid else 14, 8 if grid else 8)
        layout.setSpacing(4 if grid else 14)
        icon = QLabel()
        icon.setPixmap(_icon(result.icon).pixmap(30, 30))
        icon.setObjectName("resultIcon")
        icon.setFixedSize(38, 38)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if grid:
            layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        else:
            layout.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(4)
        name = QLabel(result.name)
        name.setObjectName("resultName")
        name.setMinimumHeight(18)
        desc = QLabel(result.description or "")
        desc.setObjectName("resultDescription")
        desc.setMinimumHeight(15)
        desc.setWordWrap(False)
        desc.setVisible(show_description and bool(result.description))
        self._full_name = result.name
        self._full_description = result.description or ""
        self._name_label = name
        self._description_label = desc
        desc.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        if grid:
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text.setSpacing(1)
            text.addWidget(name)
            text.addWidget(desc)
            layout.addLayout(text)
            self.setFixedSize(178, 82)
        else:
            text.addWidget(name)
            text.addWidget(desc)
            layout.addLayout(text, 1)

    def set_selected(self, selected: bool):
        self._selected = bool(selected)
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_selection_color(self, color: str):
        parsed = QColor(color)
        if parsed.isValid():
            self._selection_color = parsed
            self.update()

    def set_grid_width(self, width: int):
        if self._grid:
            self.setFixedWidth(max(150, width))

    def resizeEvent(self, event):
        """Elide long desktop names/descriptions to keep rows aligned."""
        width = max(40, self.width() - (20 if getattr(self, "_grid", False) else 68))
        self._name_label.setText(QFontMetrics(self._name_label.font()).elidedText(
            self._full_name, Qt.TextElideMode.ElideRight, width))
        self._description_label.setText(QFontMetrics(self._description_label.font()).elidedText(
            self._full_description, Qt.TextElideMode.ElideRight, width))
        super().resizeEvent(event)

    def paintEvent(self, event):
        # Draw this directly instead of relying solely on a stylesheet selector:
        # item widgets inside QListWidget can otherwise lose their dynamic-property
        # background when focus moves to the search field.
        if self._selected:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect().adjusted(1, 1, -1, -1)
            color = QColor(self._selection_color)
            painter.setBrush(color)
            painter.setPen(QPen(color, 1))
            painter.drawRoundedRect(rect, 9, 9)
            painter.end()
        super().paintEvent(event)


class ClipboardRow(QWidget):
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        if entry.get("content_type") == "image":
            preview = QLabel()
            preview.setFixedSize(54, 42)
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(entry.get("image_path", ""))
            if not pixmap.isNull():
                preview.setPixmap(pixmap.scaled(54, 42, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(preview)
            label_text = "图片"
        else:
            preview = QLabel("▣")
            preview.setObjectName("clipboardGlyph")
            preview.setFixedWidth(28)
            layout.addWidget(preview)
            label_text = entry.get("text", "").replace("\n", " ").strip()
            if len(label_text) > 120:
                label_text = label_text[:120] + "…"
        label = QLabel(label_text)
        label.setObjectName("clipboardText")
        label.setWordWrap(True)
        layout.addWidget(label, 1)
        if entry.get("pinned"):
            pin = QLabel("★")
            pin.setObjectName("pinMark")
            layout.addWidget(pin)


class ClipboardChip(QPushButton):
    """Compact clipboard chip: single click copies, double click pins."""
    singleClicked = Signal()
    doubleClicked = Signal()
    contextRequested = Signal(QPoint)
    hoverStarted = Signal(QPoint)
    hoverEnded = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._click_timer = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._click_timer:
                self._click_timer.stop()
            self._click_timer = QTimer(self)
            self._click_timer.setSingleShot(True)
            self._click_timer.timeout.connect(self.singleClicked.emit)
            self._click_timer.start(280)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._click_timer:
                self._click_timer.stop()
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        self.contextRequested.emit(event.globalPos())

    def enterEvent(self, event):
        if self.property("image_entry"):
            QTimer.singleShot(300, lambda: self._emit_hover_if_inside())
        super().enterEvent(event)

    def _emit_hover_if_inside(self):
        if not self.underMouse():
            return
        # Don't trigger preview while user is typing in the search bar
        window = self.window()
        if window and hasattr(window, 'search_entry') and window.search_entry.hasFocus():
            return
        self.hoverStarted.emit(QCursor.pos())

    def leaveEvent(self, event):
        self.hoverEnded.emit()
        super().leaveEvent(event)

