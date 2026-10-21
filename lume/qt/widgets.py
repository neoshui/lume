"""Custom widget components for Lume Qt UI — result rows, clipboard chips."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QPixmap, QPainter, QPainterPath, QPen, QFontMetrics
from PySide6.QtWidgets import QApplication, QAbstractButton, QLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from lume.qt import smartisan
from lume.qt.utils import _icon, _fallback_icon
from lume.search import SearchResult

class ResultRow(QWidget):
    """Two-line result row matching the original launcher's visual hierarchy."""
    def __init__(self, result: SearchResult, show_description: bool = True, grid: bool = False, parent=None):
        super().__init__(parent)
        self._grid = grid
        self._show_description = show_description
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
        desc.setVisible(False if grid else show_description and bool(result.description))
        self._full_name = result.name
        self._full_description = result.description or ""
        self._name_label = name
        self._description_label = desc
        desc.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        if grid:
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text.setSpacing(3)
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
        if self._grid:
            self._description_label.setVisible(False)
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
            if self._grid:
                rect.setLeft(self.width() // 2 - 26)
                rect.setWidth(52)
                rect.setTop(2)
                rect.setHeight(48)
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
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._emit_hover_if_inside)

    def paintEvent(self, event):
        super().paintEvent(event)
        entry = self.property("entry") or {}
        if self.property("image_entry") and entry.get("pinned"):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            badge = QRectF(self.width() - 22, 2, 20, 20)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ffffff"))
            painter.drawRoundedRect(badge, 4, 4)
            font = painter.font()
            font.setPixelSize(14)
            painter.setFont(font)
            painter.setPen(QColor("#52665a"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "📌")
            painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._click_timer:
                self._click_timer.stop()
            self._click_timer = QTimer(self)
            self._click_timer.setSingleShot(True)
            self._click_timer.timeout.connect(self.singleClicked.emit)
            self._click_timer.start(QApplication.doubleClickInterval() + 40)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._click_timer:
                self._click_timer.stop()
            self.doubleClicked.emit()
        event.accept()
        return

    def contextMenuEvent(self, event):
        self.contextRequested.emit(event.globalPos())

    def enterEvent(self, event):
        if self.property("image_entry"):
            self._hover_timer.start(300)
        else:
            self.hoverEnded.emit()
        super().enterEvent(event)

    def _emit_hover_if_inside(self):
        if not self.underMouse():
            return
        self.hoverStarted.emit(QCursor.pos())

    def leaveEvent(self, event):
        self._hover_timer.stop()
        self.hoverEnded.emit()
        super().leaveEvent(event)



class ClipboardFlowLayout(QLayout):
    """Wrap clipboard items by their actual widths, preserving history order."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(0, 4, 0, 4)
        self.setSpacing(6)

    def addItem(self, item):
        self._items.append(item)
        self.invalidate()

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        item = self._items.pop(index) if 0 <= index < len(self._items) else None
        if item is not None:
            self.invalidate()
        return item

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), False)

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, True)

    def _arrange(self, rect, apply):
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, row_height = area.x(), area.y(), 0
        for item in self._items:
            size = item.sizeHint()
            if row_height and x + size.width() > area.x() + area.width():
                x = area.x()
                y += row_height + self.spacing()
                row_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), size))
            x += size.width() + self.spacing()
            row_height = max(row_height, size.height())
        return y + row_height - rect.y() + margins.bottom()


class PrivacyButton(QPushButton):
    """Compact checkable privacy action with an explicit enabled label."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._smartisan = False
        self._dark = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("私密模式")
        self.setFixedSize(98, 30)
        self.setToolTip("开启后不保存新复制内容")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 0, 9, 0)
        layout.setSpacing(8)
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(16, 16)
        self._text_label = QLabel("私密模式")
        for label in (self._icon_label, self._text_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            label.setStyleSheet("background: transparent; border: 0; padding: 0; font-size: 12px;")
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)
        self.toggled.connect(self._refresh)
        self._refresh()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._refresh()

    def set_visual_style(self, active, dark=False):
        self._smartisan = active
        self._dark = dark
        self._refresh()

    @staticmethod
    def _lock_icon(protected, smartisan_style=False, dark=False):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(64 / 24, 64 / 24)
        color = QColor(("#ffffff" if protected else smartisan.palette(dark)["muted"]) if smartisan_style else ("#347753" if protected else "#69746e"))
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        shield = QPainterPath()
        shield.moveTo(12, 2.5)
        shield.cubicTo(14.5, 4, 17, 4.8, 20, 5)
        shield.lineTo(20, 11)
        shield.cubicTo(20, 16, 16, 19.8, 12, 21.5)
        shield.cubicTo(8, 19.8, 4, 16, 4, 11)
        shield.lineTo(4, 5)
        shield.cubicTo(7, 4.8, 9.5, 4, 12, 2.5)
        painter.drawPath(shield)
        if protected:
            mark = QPainterPath()
            mark.moveTo(8, 11.5)
            mark.lineTo(10.5, 14)
            mark.lineTo(16, 8.5)
            painter.drawPath(mark)
        else:
            painter.drawLine(8, 8, 16, 16)
        painter.end()
        return QIcon(pixmap)

    def _refresh(self, *_):
        enabled = self.isChecked()
        self._icon_label.setPixmap(self._lock_icon(enabled, self._smartisan, self._dark).pixmap(16, 16))
        self.setAccessibleDescription("已开启，不保存新复制内容" if enabled else "已关闭，保存新复制内容")
        if self._smartisan:
            sheet, color = smartisan.button_style(self._dark, enabled)
            self._text_label.setStyleSheet(f"background: transparent; border: 0; padding: 0; font-size: 12px; color: {color};")
            self.setStyleSheet(sheet)
            return
        bg = "#e3f1e9" if enabled else "#f6f7f6"
        border = "#b7d7c5" if enabled else "#dde2df"
        text = "#396b51" if enabled else "#66726b"
        self._text_label.setStyleSheet(f"background: transparent; border: 0; padding: 0; font-size: 12px; color: {text};")
        self.setStyleSheet(f"""
            QPushButton {{ background: {bg}; color: {text}; border: 1px solid {border};
                border-radius: 7px; padding: 0; font-size: 12px; font-weight: 500; }}
            QPushButton:hover {{ border-color: #91b6a1; background: {bg}; }}
            QPushButton:focus {{ border: 1px solid #719e85; }}
        """)
