"""Lume main window — the floating launcher and entry point."""

from __future__ import annotations

import sys
import time
import shutil
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QEvent, QPoint, QRect, QSize
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QIcon, QKeyEvent, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QDialog, QFileDialog,
    QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSplitter,
    QCheckBox, QSizePolicy, QSystemTrayIcon, QVBoxLayout, QWidget, QToolTip,
)

from lume.qt import smartisan
from lume.config import get_data_dir, load_config, save_config
from lume.autostart import set_autostart
from lume.desktop import detect_desktop
from lume.log_utils import get_logger
from lume.qt.utils import (
    _mix, _qcolor, _rgb_text, _icon, _fallback_icon, register_gnome_shortcut,
)
from lume.qt.widgets import ResultRow, ClipboardChip, ClipboardFlowLayout, PrivacyButton
from lume.qt.clipboard import ClipboardStore
from lume.qt.shell_extension import install_and_enable, is_enabled
from lume.qt.settings import TabbedSettingsDialog
from lume.search import SearchResult, get_category, launch_app, open_folder, open_url, search
from lume.themes import apply_theme, get_theme, list_themes
from lume.version import VERSION

log = get_logger(__name__)


# Single-instance server name — do not change without a good reason.
APP_SERVER_NAME = "com.lume.launcher.qt"

# Project root derived from the lume package location.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

class LumeWindow(QMainWindow):
    def __init__(self, app: QApplication, background: bool = False):
        super().__init__()
        self.app = app
        self.background = background
        self._dismissed = False
        self.config = load_config()
        self.results: list[SearchResult] = []
        self.preview = QFrame(self)
        preview_layout = QVBoxLayout(self.preview)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(6)
        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_image)
        preview_caption = QLabel("左键复制图片 · 双击固定 · 右键菜单")
        preview_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(preview_caption)
        self.preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.preview.setObjectName("imagePreview")
        self.preview.setStyleSheet("QFrame#imagePreview { background: #ffffff; border: 1px solid #d6dfda; border-radius: 8px; } QLabel { background: transparent; border: 0; padding: 0; color: #52665a; font-size: 11px; }")
        self.preview.hide()
        self._settings_open = False
        self.setWindowTitle("Lume")
        icon_path = _PROJECT_ROOT / "lume-256.png"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._setup_tray_and_hotkey(icon_path)
        # Lume is a transient launcher. Keep it out of the dock/task switcher
        # while hidden; unlike a normal app window it should not persist there.
        window_type = Qt.WindowType.Tool
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | window_type)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        root = QFrame()
        root.setObjectName("panel")
        shadow = QGraphicsDropShadowEffect(root)
        self._panel_shadow = shadow
        shadow.setBlurRadius(40); shadow.setOffset(0, 14); shadow.setColor(QColor(22, 32, 48, 58))
        root.setGraphicsEffect(shadow)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(22, 22, 22, 16)
        root_layout.setSpacing(11)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self._suppress_result_tooltips_until = 0.0
        self._search_refresh_timer = QTimer(self)
        self._search_refresh_timer.setSingleShot(True)
        self._search_refresh_timer.setInterval(70 if sys.platform == "win32" else 25)
        self._search_refresh_timer.timeout.connect(self.refresh_results)
        self.search_entry = QLineEdit()
        self.search_entry.setObjectName("searchEntry")
        self.search_entry.setPlaceholderText("搜索应用、文件夹、网页…")
        self.search_entry.setClearButtonEnabled(True)
        self.search_entry.textChanged.connect(self._schedule_results_refresh)
        self.search_entry.returnPressed.connect(self._activate_after_pending_refresh)
        self.search_entry.installEventFilter(self)
        search_row.addWidget(self.search_entry)
        self._search_icon_action = self.search_entry.addAction(smartisan.icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        settings = QPushButton("⚙")
        self.settings_button = settings
        settings.setObjectName("settings")
        settings.setFixedSize(42, 42)
        settings.clicked.connect(self.open_settings)
        search_row.addWidget(settings)
        root_layout.addLayout(search_row)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.result_list = QListWidget()
        self.result_list.setObjectName("resultList")
        self.result_list.setIconSize(QSize(46 if sys.platform == "win32" else 30, 46 if sys.platform == "win32" else 30))
        self.result_list.setMouseTracking(sys.platform != "win32")
        self.result_list.viewport().setMouseTracking(sys.platform != "win32")
        self.result_list.itemActivated.connect(self.activate_item)
        self.result_list.currentItemChanged.connect(lambda *_: self.update_result_selection())
        if sys.platform != "win32":
            self.result_list.itemEntered.connect(self._hover_result)
        self.result_list.installEventFilter(self)
        self.result_list.viewport().installEventFilter(self)
        self.splitter.addWidget(self.result_list)

        clip = QWidget()
        clip.setObjectName("clipboardArea")
        clip_layout = QVBoxLayout(clip)
        clip_layout.setContentsMargins(10, 8, 10, 10)
        clip_layout.setSpacing(8)
        clip_header_bar = QFrame()
        clip_header_bar.setObjectName("clipboardHeaderBar")
        clip_header = QHBoxLayout(clip_header_bar)
        clip_header.setContentsMargins(10, 6, 8, 6)
        clip_header.setSpacing(8)
        clip_title = QLabel("剪贴板")
        clip_title.setObjectName("clipboardTitle")
        clip_header.addWidget(clip_title)
        clip_header.addStretch()
        clear = QPushButton("清空")
        clear.setObjectName("clearClipboard")
        clear.clicked.connect(self.clear_clipboard)
        clip_header.addWidget(clear)
        clip_layout.addWidget(clip_header_bar)
        self.clip_scroll = QScrollArea()
        self.clip_scroll.setWidgetResizable(True)
        self.clip_scroll.verticalScrollBar().valueChanged.connect(lambda _: self.hide_image_preview())
        self.clip_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.clip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.clip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._clipboard_reflow_timer = QTimer(self)
        self._clipboard_reflow_timer.setSingleShot(True)
        self._clipboard_reflow_timer.timeout.connect(self._reflow_clipboard)
        self.clip_scroll.viewport().installEventFilter(self)
        self.clip_content = QWidget()
        self.clip_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.clip_flow = ClipboardFlowLayout(self.clip_content)
        self.clip_flow.setContentsMargins(0, 4, 0, 4)
        self.clip_flow.setSpacing(6)
        self.clip_scroll.setWidget(self.clip_content)
        clip_layout.addWidget(self.clip_scroll)
        private_card = QFrame()
        private_card.setObjectName("privateModeCard")
        private_card.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        private_layout = QHBoxLayout(private_card)
        private_layout.setContentsMargins(0, 0, 8, 0)
        private_layout.setSpacing(6)
        self.private_mode = PrivacyButton(private_card)
        self.private_mode.setObjectName("privateModeToggle")
        self.private_mode.setToolTip("开启后，新的文本和图片不会保存到剪切板历史")
        self.private_mode.setChecked(bool(self.config.get("clipboard_private_mode", False)))
        self.private_mode.toggled.connect(self.set_private_mode)
        private_layout.addWidget(self.private_mode)
        clip_header.insertWidget(2, private_card)
        self.splitter.addWidget(clip)
        root_layout.addWidget(self.splitter)
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        self.status_label.setToolTip("Lume 运行状态")
        root_layout.addWidget(self.status_label)
        self.setCentralWidget(root)

        self.store = ClipboardStore(app, self.config.get("clipboard_max_entries", 50), self.refresh_clipboard, self.config)
        self.refresh_clipboard()
        self.apply_config()
        self.refresh_results()
        if not self.background:
            QTimer.singleShot(350, self._offer_shell_clipboard_component)

    def _offer_shell_clipboard_component(self):
        """Offer the one-click GNOME component only where it is required."""
        if not detect_desktop().needs_gnome_extension or is_enabled():
            return
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle("启用完整剪切板历史")
        dialog.setText("GNOME Wayland 需要 Lume 剪切板组件来保存后台文本和截图历史。")
        dialog.setInformativeText("点击“安装并启用”即可完成，无需 sudo，也不依赖第三方扩展。")
        install = dialog.addButton("安装并启用", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton("稍后", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is install:
            ok, message = install_and_enable()
            QMessageBox.information(self, "Lume 剪切板组件" if ok else "安装失败", message)

    def apply_config(self):
        self.resize(self.config.get("launcher_width", 680), self.config.get("launcher_height", 720))
        self.apply_style()
        saved = self.config.get("paned_position", 0)
        height = self.config.get("launcher_height", 720)
        self.splitter.setSizes([saved or max(200, height - 250), 220])

    def apply_style(self):
        dark = self.config.get("theme") == "dark"
        if self.config.get("theme") == "auto":
            dark = self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        active = smartisan.is_smartisan(self.config)
        self.private_mode.set_visual_style(active, dark)
        self._search_icon_action.setVisible(active)
        self.settings_button.setText("" if active else "⚙")
        self.settings_button.setIcon(smartisan.icon("setting") if active else QIcon())
        self.settings_button.setIconSize(QSize(20, 20))
        self.settings_button.setToolTip("设置")
        self.settings_button.setAccessibleName("设置")
        self._panel_shadow.setBlurRadius(18 if active else 40)
        self._panel_shadow.setOffset(0, 4 if active else 14)
        self._panel_shadow.setColor(QColor(0, 0, 0, 22) if active else QColor(22, 32, 48, 58))
        if active:
            p = smartisan.palette(dark)
            self.setStyleSheet(smartisan.launcher_stylesheet(dark, self.config.get("font_size", 15)))
            self.preview.setStyleSheet(f"QFrame#imagePreview {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 8px; }} QLabel {{ background: transparent; border: 0; padding: 0; color: {p['muted']}; font-size: 11px; }}")
            return
        self.preview.setStyleSheet("QFrame#imagePreview { background: #ffffff; border: 1px solid #d6dfda; border-radius: 8px; } QLabel { background: transparent; border: 0; padding: 0; color: #52665a; font-size: 11px; }")
        appearance = self.config.get("appearance", {})
        accent = appearance.get("accent_color", "#6988b5")
        accent_soft = _mix(accent, "#ffffff", 0.84) if not dark else _mix(accent, "#111827", 0.52)
        result_selected = _mix(accent, "#ffffff", 0.91) if not dark else _mix(accent, "#202329", 0.78)
        result_selected_border = _mix(accent, "#ffffff", 0.40) if not dark else _mix(accent, "#202329", 0.35)
        selected_bg = _qcolor(result_selected)
        luminance = (selected_bg.red() * 299 + selected_bg.green() * 587 + selected_bg.blue() * 114) / 1000
        selected_text = "#172033" if luminance > 165 else "#ffffff"
        selected_desc = "rgba(23,32,51,0.72)" if luminance > 165 else "rgba(255,255,255,0.78)"
        accent_hover = _mix(accent, "#ffffff", 0.74) if not dark else _mix(accent, "#111827", 0.42)
        opacity = 1.0
        radius = 12
        panel_rgb = _rgb_text(appearance.get("panel_bg_dark_rgb" if dark else "panel_bg_rgb", "32,35,42" if dark else "247,249,252"), "32,35,42" if dark else "247,249,252")
        panel = "#25272b" if dark else "#fcfcfb"
        text = appearance.get("text_dark_color" if dark else "text_color", "#f2f4f8" if dark else "#18202d")
        desc = appearance.get("desc_dark_color" if dark else "desc_color", "rgba(218,226,240,0.56)" if dark else "rgba(62,73,94,0.72)")
        result_name = "#e5ebf4" if dark else "#2d3b52"
        result_desc = "rgba(213,222,236,0.68)" if dark else "rgba(78,94,116,0.70)"
        tooltip_bg = "rgba(24, 32, 46, 232)" if dark else "rgba(255, 255, 255, 238)"
        tooltip_text = "#f3f6fb" if dark else "#26354c"
        surface = appearance.get("search_bg_dark" if dark else "search_bg", "#30343d" if dark else "#ffffff")
        border = "#3f4756" if dark else "#dce4ef"
        chip_bg = "rgba(48, 53, 64, 0.78)" if dark else "rgba(255, 255, 255, 0.72)"
        if dark:
            selected_text = "#ffffff"
            selected_desc = "rgba(255,255,255,0.80)"
        hover_row = "rgba(255,255,255,0.06)" if dark else "rgba(255,255,255,0.58)"
        font_size = self.config.get("font_size", 15)
        windows_native_result_font = max(11, font_size - 2)
        self.setStyleSheet(f"""
            QFrame#panel {{ background: {panel}; border: 1px solid {border}; border-radius: {radius}px; }}
            QWidget {{ color: {text}; font-size: {font_size}px; }}
            QLineEdit#searchEntry {{ background: {surface}; border: 1px solid {border}; border-radius: 12px;
                         padding: 10px 14px; selection-background-color: {accent_soft}; selection-color: {selected_text}; }}
            QLineEdit#searchEntry:hover {{ border-color: {_mix(accent, "#ffffff", 0.58)}; }}
            QListWidget, QScrollArea {{ background: transparent; border: 0; outline: 0; padding: 0; }}
            QScrollBar:vertical {{ background: transparent; width: 7px; margin: 4px 1px; }}
            QScrollBar::handle:vertical {{ background: {"#667084" if dark else "#b0bbc9"}; min-height: 34px; border-radius: 3px; }}
            QScrollBar::handle:vertical:hover {{ background: {accent}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; height: 0; }}
            QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 1px 3px; }}
            QScrollBar::handle:horizontal {{ background: {"#667084" if dark else "#b0bbc9"}; min-width: 34px; border-radius: 3px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; width: 0; }}
            QListWidget#resultList::item {{ padding: 0; border: 0; margin: 2px 0; background: transparent; color: {result_name}; }}
            QListWidget#resultList::item:selected {{
                background: transparent;
                color: {selected_text};
                border: 0;
                border-radius: 9px;
            }}
            QListWidget#resultList[winNative="true"]::item {{ font-size: {windows_native_result_font}px; }}
            QWidget#resultRow {{ border-radius: 9px; background: transparent; }}
            QLabel#categoryHeader {{
                color: {desc};
                font-size: {max(11, font_size - 3)}px;
                font-weight: 700;
                padding: 6px 8px 2px 8px;
                background: transparent;
                letter-spacing: 1px;
                border: 0;
            }}

            QWidget#resultRow:hover {{ background: transparent; }}
            QWidget#resultRow[selected="true"] {{ background: transparent; border: 0; }}
            QLabel#resultIcon {{ border-radius: 8px; background: rgba(255,255,255,0.38); }}
            QLabel#resultName {{ color: {result_name}; font-size: 14px; font-weight: 500; }}
            QLabel#resultDescription {{ color: {result_desc}; font-size: 12px; }}
            QWidget#resultRow[selected="true"] QLabel#resultName {{ color: {selected_text}; }}
            QWidget#resultRow[selected="true"] QLabel#resultDescription {{ color: {selected_desc}; }}
            QWidget#clipboardArea {{ background: {"#303338" if dark else "#f0f2f1"}; border: 0; border-radius: 10px; }}
            QWidget#clipboardArea QScrollArea, QWidget#clipboardArea QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QFrame#clipboardHeaderBar {{ background: {"#303338" if dark else "#f0f3f2"}; border: 0; border-top: 0; border-radius: 0; }}
            QLabel#clipboardTitle {{ color: {text}; font-size: 13px; font-weight: 600; }}
            QLabel#statusLabel {{ color: {desc}; font-size: 11px; padding-top: 2px; }}
            QFrame#privateModeCard {{ background: transparent; border: 0; border-radius: 0; }}
            QLabel#privateModeIcon {{ font-size: 15px; background: transparent; }}
            QLabel#privateModeTitle {{ color: {text}; font-size: 12px; font-weight: 700; background: transparent; }}
            QLabel#privateModeDescription {{ color: {desc}; font-size: 11px; background: transparent; }}
            QPushButton#clipboardChip {{ background: {chip_bg}; color: {"#dbe5f3" if dark else "#516071"}; border: 1px solid {"#3c4047" if dark else "#e5e8e6"};
                border-radius: 7px; padding: 3px 9px; font-size: 12px; min-height: 22px; }}
            QPushButton#clipboardChip:hover {{ background: {accent_soft}; color: {selected_text}; border-color: {accent}; }}
            QPushButton#clipboardImage {{ background: {chip_bg}; border: 1px solid {border}; border-radius: 8px; padding: 3px; }}
            QPushButton#clipboardImage:hover {{ background: {accent_soft}; border-color: {accent}; }}
            QLabel#pinMark {{ color: {accent}; font-size: 16px; }}
            QPushButton {{ background: {chip_bg}; border: 1px solid {border}; border-radius: 8px; padding: 7px 12px; }}
            QPushButton:hover {{ border-color: {accent}; background: {accent_soft}; }}
            QPushButton#settings {{ font-size: 16px; color: {accent}; }}
            QPushButton#clearClipboard {{ padding: 5px 12px; color: {"#dbe5f3" if dark else "#516071"}; }}
            QSplitter::handle {{ background: transparent; height: 10px; }}
            QLineEdit#searchEntry:focus {{ border: 1px solid {accent}; }}
            QToolTip {{
                background: {tooltip_bg}; color: {tooltip_text};
                border: 1px solid {_mix(accent, "#ffffff", 0.25)}; border-radius: 6px;
                padding: 4px 7px; font-size: 11px;
                max-width: 320px;
            }}
        """)

    def show_launcher(self):
        if self._dismissed:
            self.hide()
        self._dismissed = False
        self._wake_screen = QGuiApplication.screenAt(QCursor.pos()) or self.screen()
        self.winId()
        if self._wake_screen is not None and self.windowHandle() is not None:
            self.windowHandle().setScreen(self._wake_screen)
        self.search_entry.clear()

        # Restore from invisible state
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_entry.setFocus()
        self._clipboard_reflow_timer.start(0)

        # Schedule fine-tune after compositor has mapped the surface
        QTimer.singleShot(1, self._fine_tune_position)

        # Force-read clipboard NOW.  On Wayland the dataChanged signal
        # fires reliably while our off-screen surface is alive, so this
        # is just a safeguard for the first launch / after window creation.
        QTimer.singleShot(50, self.store.capture)

    def _fine_tune_position(self):
        # Capture the cursor screen now that surfaces and outputs exist.
        screen = getattr(self, "_wake_screen", None) or QGuiApplication.screenAt(QCursor.pos()) or self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return  # Wayland compositor still has no outputs
        area = screen.availableGeometry()
        size = self.frameGeometry().size()
        if not size.isValid() or size.width() <= 0 or size.height() <= 0:
            size = self.sizeHint()
        x = area.x() + (area.width() - size.width()) // 2
        y = area.y() + (area.height() - size.height()) // 2
        offset = int(self.config.get("launcher_vertical_offset", 140))
        y -= offset
        x = max(area.left(), min(x, area.right() - size.width() + 1))
        y = max(area.top(), min(y, area.bottom() - size.height() + 1))
        self.move(QPoint(x, y))

    def center_on_screen(self):
        # Public alias kept for backward compatibility.
        self._fine_tune_position()



    def toggle(self):
        if getattr(self, '_settings_open', False):
            return  # Don't toggle while settings dialog is open
        if self.isVisible() and not self._dismissed and self.windowOpacity() > 0:
            self._dismiss()
        else:
            self.show_launcher()

    def _dismiss(self):
        self.hide_image_preview()
        self._saved_pos = self.pos()
        self.hide()
        self.setWindowOpacity(1.0)
        self._dismissed = True
        sizes = self.splitter.sizes()
        if sizes:
            self.config["paned_position"] = sizes[0]
            save_config(self.config)
        QTimer.singleShot(50, self.store.capture)

    # === System tray + Windows global hotkey ===

    def _setup_tray_and_hotkey(self, icon_path):
        """Create system tray icon and register Windows global hotkey."""
        # System tray icon (all platforms)
        if QSystemTrayIcon.isSystemTrayAvailable():
            tray = QSystemTrayIcon(self)
            tray.setIcon(QIcon(str(icon_path)))
            tray.setToolTip(f"Lume Launcher\n{self.config.get('shortcut', 'ALT+Space')} to open")
            menu = QMenu(self)
            show_action = menu.addAction(QIcon(), "显示 / 隐藏")
            show_action.triggered.connect(self.toggle)
            menu.addSeparator()
            quit_action = menu.addAction(QIcon(), "退出")
            quit_action.triggered.connect(self.app.quit)
            tray.setContextMenu(menu)
            tray.show()
            tray.activated.connect(
                lambda reason: self.toggle() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
            )
            self._tray = tray
            log.info("System tray icon active")

        # Windows global hotkey via Win32 API
        if sys.platform == "win32":
            self._register_win32_hotkey()
        elif sys.platform == "linux":
            # On Linux, shortcut is registered via gsettings or portal
            pass

    def _register_win32_hotkey(self):
        """Register global hotkey via Win32 API. Always unregisters first."""
        try:
            from lume.win32_hotkey import register, unregister_all
            unregister_all()
            shortcut = self.config.get("shortcut", "ALT+space")
            # Queue UI work outside the native event filter. This is important
            # while a modal settings dialog runs its nested Qt event loop.
            ok = register(shortcut, lambda: QTimer.singleShot(0, self.toggle))
            if ok:
                log.info("Windows hotkey registered: %s", shortcut)
                if hasattr(self, "_tray"):
                    self._tray.setToolTip(f"Lume Launcher\n{shortcut} to open")
            else:
                log.warning("RegisterHotKey failed for: %s", shortcut)
        except Exception as e:
            log.warning("Windows hotkey registration error: %s", e)

    def _unregister_win32_hotkey(self):
        try:
            from lume.win32_hotkey import unregister_all
            unregister_all()
        except Exception:
            pass

    def _schedule_results_refresh(self, *_):
        # Destroying and recreating Windows item widgets on every key event can
        # briefly expose the native tooltip top-level window. Hide it first and
        # coalesce rapid typing into one refresh.
        QToolTip.hideText()
        self.hide_image_preview()
        if sys.platform == "win32":
            self._suppress_result_tooltips_until = time.monotonic() + 0.8
        self._search_refresh_timer.start()

    def _activate_after_pending_refresh(self):
        if self._search_refresh_timer.isActive():
            self._search_refresh_timer.stop()
            self.refresh_results()
        self.activate_current()

    def refresh_results(self, *_):
        QToolTip.hideText()
        query = self.search_entry.text()
        show_results = bool(query.strip()) or self.config.get("show_apps_on_open", True)
        was_visible = not self.result_list.isHidden()
        self.result_list.setVisible(show_results)
        if show_results and not was_visible:
            height = self.config.get("launcher_height", 720)
            self.splitter.setSizes([self.config.get("paned_position", 0) or max(200, height - 250), 220])
        self.results = search(query, self.config) if show_results else []
        self.result_list.clear()
        self.result_list.setToolTip("")
        use_native_rows = sys.platform == "win32"
        self.result_list.setProperty("winNative", use_native_rows)
        self.result_list.style().unpolish(self.result_list)
        self.result_list.style().polish(self.result_list)
        grid = self.config.get("layout", "list") == "grid"
        viewport_width = max(1, self.result_list.viewport().width())
        if grid:
            self.result_list.setViewMode(QListWidget.ViewMode.IconMode)
            self.result_list.setMovement(QListWidget.Movement.Static)
            self.result_list.setResizeMode(QListWidget.ResizeMode.Adjust)
            self.result_list.setWrapping(True)
            columns = max(1, (viewport_width - 24) // 150)
            cell_width = max(150, (viewport_width - 24) // columns)
            self.result_list.setItemAlignment(Qt.AlignmentFlag.AlignLeft)
            self.result_list.setGridSize(QSize(cell_width, 132 if use_native_rows else 90))
            self.result_list.setSpacing(0)
        else:
            self.result_list.setViewMode(QListWidget.ViewMode.ListMode)
            self.result_list.setMovement(QListWidget.Movement.Static)
            self.result_list.setResizeMode(QListWidget.ResizeMode.Fixed)
            self.result_list.setWrapping(False)
            self.result_list.setItemAlignment(Qt.AlignmentFlag.AlignLeft)
            self.result_list.setGridSize(QSize())
        density = self.config.get("result_density", "comfortable")
        row_height = {"compact": 62, "comfortable": 72, "airy": 82}.get(density, 72)
        show_description = self.config.get("show_result_descriptions", True)
        dark = smartisan.is_dark(self.config)
        selection_color = smartisan.palette(dark)["selection"] if smartisan.is_smartisan(self.config) else _mix(
            self.config.get("appearance", {}).get("accent_color", "#6988b5"),
            "#202329" if dark else "#ffffff", 0.86,
        )
        prev_category = None
        for result in self.results:
            # Insert category header when category changes (list mode only)
            if not grid:
                _cat_order, cat_label = get_category(result.action_type)
                if cat_label and cat_label != prev_category:
                    prev_category = cat_label
                    header_item = QListWidgetItem()
                    header_item.setFlags(Qt.ItemFlag.NoItemFlags)
                    header_item.setSizeHint(QSize(viewport_width, 32))
                    self.result_list.addItem(header_item)
                    header_widget = QLabel(cat_label)
                    header_widget.setObjectName("categoryHeader")
                    self.result_list.setItemWidget(header_item, header_widget)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, result)
            item.setSizeHint(QSize(cell_width, 132 if (grid and use_native_rows) else 90) if grid else QSize(max(220, viewport_width - 6), row_height))
            if use_native_rows:
                item.setIcon(_fallback_icon(result))
                if grid:
                    item.setText(result.name)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
                else:
                    item.setText(result.name if not (show_description and result.description) else f"{result.name}\n{result.description}")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                item.setToolTip("")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
                if not grid:
                    item.setSizeHint(QSize(max(220, viewport_width - 6), row_height + (18 if show_description and result.description else 0)))
                self.result_list.addItem(item)
                continue
            self.result_list.addItem(item)
            try:
                row = ResultRow(result, show_description, grid=grid)
                if grid:
                    row.set_grid_width(cell_width - 6)
                row.set_selection_color(selection_color)
                row.setToolTip("")
                for child in row.findChildren(QWidget):
                    child.setToolTip("")
                self.result_list.setItemWidget(item, row)
            except Exception:
                item.setIcon(_fallback_icon(result))
                item.setText(result.name if not (show_description and result.description) else f"{result.name}\n{result.description}")
                item.setToolTip("")
        if self.result_list.count():
            self.result_list.setCurrentRow(0)
            self.result_list.scrollToTop()
        self.update_result_selection()

    def _update_grid_geometry(self):
        if self.config.get("layout", "list") != "grid":
            return
        viewport_width = max(1, self.result_list.viewport().width())
        columns = max(1, (viewport_width - 24) // 150)
        cell_width = max(150, (viewport_width - 24) // columns)
        self.result_list.setGridSize(QSize(cell_width, 90))
        for index in range(self.result_list.count()):
            row = self.result_list.itemWidget(self.result_list.item(index))
            if isinstance(row, ResultRow):
                row.set_grid_width(cell_width - 6)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_grid_geometry)

    def update_result_selection(self):
        if sys.platform == "win32":
            return
        for index in range(self.result_list.count()):
            item = self.result_list.item(index)
            row = self.result_list.itemWidget(item)
            if isinstance(row, ResultRow):
                row.set_selected(item is self.result_list.currentItem())

    def _hover_result(self, item):
        """Make the visual selection follow the pointer as it crosses results."""
        if item is not None and item is not self.result_list.currentItem():
            scroll = self.result_list.verticalScrollBar()
            position = scroll.value()
            self.result_list.setCurrentItem(item)
            # Hover selection must not auto-scroll a partly visible row into view.
            scroll.setValue(position)

    def activate_current(self):
        if self.result_list.currentItem():
            self.activate_item(self.result_list.currentItem())

    def activate_item(self, item):
        result = item.data(Qt.ItemDataRole.UserRole)
        if not result:
            return
        if result.action_type == "app":
            launch_app(result.action_data)
        elif result.action_type == "folder":
            open_folder(result.action_data)
        elif result.action_type in ("web", "search"):
            open_url(result.action_data)
        elif result.action_type in ("calculator", "timestamp"):
            self.app.clipboard().setText(result.action_data)
        elif result.action_type == "note":
            notes = get_data_dir() / "notes"
            notes.mkdir(parents=True, exist_ok=True)
            (notes / f"{datetime.now():%Y-%m-%d-%H-%M-%S}.md").write_text(result.action_data, encoding="utf-8")
        self._dismiss()

    def refresh_clipboard(self):
        self.hide_image_preview()
        while self.clip_flow.count():
            item = self.clip_flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        entries = [(0, e) for e in self.store.get_history()]
        for _, entry in entries:
            image = entry.get("content_type") == "image"
            if not image and not entry.get("text", "").strip():
                continue
            if image:
                chip = ClipboardChip()
                chip.setObjectName("clipboardImage")
                pixmap = QPixmap(entry.get("image_path", ""))
                if not pixmap.isNull():
                    ratio = pixmap.width() / max(1, pixmap.height())
                    thumb_width = max(38, min(86, int(42 * ratio)))
                    chip.setIcon(QIcon(pixmap))
                    chip.setIconSize(QSize(thumb_width, 42))
                    chip.setFixedWidth(thumb_width + 10)
                else:
                    chip.setFixedWidth(52)
                chip.setFixedHeight(50)
                chip.setToolTip("")
                chip.setProperty("image_entry", True)
            else:
                text = entry.get("text", "").replace("\n", " ").strip()
                display = text[:8] + ("…" if len(text) > 8 else "")
                chip = ClipboardChip(("📌 " if entry.get("pinned") else "") + display)
                chip.setObjectName("clipboardChip")
                chip.setToolTip(text)
            chip.setProperty("entry", entry)
            chip.singleClicked.connect(lambda e=entry: self.copy_chip(e))
            chip.doubleClicked.connect(lambda e=entry: self.toggle_pin(e))
            chip.contextRequested.connect(lambda pos, e=entry: self.clipboard_menu(e, pos))
            chip.hoverEnded.connect(self.hide_image_preview)
            if image:
                chip.hoverStarted.connect(lambda pos, e=entry, c=chip: self.show_image_preview(e, pos, c))
            chip.ensurePolished()
            self.clip_flow.addWidget(chip)
        self.clip_flow.invalidate()
        self.clip_content.updateGeometry()
        self._clipboard_reflow_timer.start(0)
        desktop = detect_desktop()
        provider = "GNOME 扩展" if desktop.needs_gnome_extension and is_enabled() else "Qt 剪贴板"
        self.status_label.setText(
            f"剪贴板 {len(self.store.entries)}/{self.store.max_entries} · {provider} · {self.config.get('shortcut', 'ALT+Space')} · Lume {VERSION}"
        )

    def _reflow_clipboard(self):
        """Use the settled viewport width rather than the content size hint."""
        viewport = self.clip_scroll.viewport()
        width = viewport.width()
        if width <= 0:
            return
        scroll = self.clip_scroll.verticalScrollBar()
        position = scroll.value()
        height = max(viewport.height(), self.clip_flow.heightForWidth(width))
        self.clip_content.resize(width, height)
        self.clip_flow.invalidate()
        self.clip_flow.setGeometry(self.clip_content.rect())
        scroll.setValue(position)

    def show_image_preview(self, entry, pos, anchor=None):
        pixmap = QPixmap(entry.get("image_path", ""))
        if pixmap.isNull():
            return
        clipboard_area = self.clip_scroll.parentWidget()
        top = clipboard_area.mapTo(self, QPoint()).y()
        available_width = max(1, self.width() - 44)
        available_height = max(1, top - 22 - 6)
        scale = min(0.8, max(1, available_width - 16) / pixmap.width(), max(1, available_height - 42) / pixmap.height())
        image = pixmap.scaled(max(1, round(pixmap.width() * scale)), max(1, round(pixmap.height() * scale)), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.preview_image.setPixmap(image)
        self.preview.layout().invalidate()
        self.preview.setFixedSize(self.preview.layout().sizeHint())
        center = anchor.mapTo(self, anchor.rect().center()).x() if anchor else self.width() // 2
        x = max(22, min(center - self.preview.width() // 2, self.width() - 22 - self.preview.width()))
        self.preview.move(x, top - self.preview.height() - 6)
        self.preview.show()
        self.preview.raise_()

    def hide_image_preview(self):
        self.preview.hide()

    def copy_chip(self, entry):
        self.store.copy(entry)
        self._dismiss()

    def toggle_pin(self, entry):
        entry["pinned"] = not entry.get("pinned", False)
        self.store.save()
        self.refresh_clipboard()

    def clipboard_menu(self, entry, pos):
        menu = QMenu(self)
        if entry.get("content_type") == "image":
            save = menu.addAction("保存截图…")
            save.triggered.connect(lambda: self.save_clipboard_image(entry))
        delete = menu.addAction("删除")
        delete.triggered.connect(lambda: (self.store.remove(entry), self.refresh_clipboard()))
        menu.exec(pos)

    def save_clipboard_image(self, entry):
        dst, _ = QFileDialog.getSaveFileName(self, "保存截图", f"{datetime.now():%Y-%m-%d-%H-%M-%S}.png", "PNG 图片 (*.png)")
        if dst and entry.get("image_path"):
            shutil.copy2(entry["image_path"], dst)

    def clear_clipboard(self):
        if self.store.entries:
            answer = QMessageBox.question(
                self, "清空剪贴板历史", "确定删除全部剪贴板历史（包括固定项）吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.store.clear()
        self.refresh_clipboard()

    def open_settings(self):
        self._settings_open = True
        if sys.platform == "win32":
            self._unregister_win32_hotkey()
        dialog = TabbedSettingsDialog(self.config, self)
        try:
            result = dialog.exec()
        finally:
            self._settings_open = False
        if result == QDialog.DialogCode.Accepted:
            result_config = dialog.values()
            desired_autostart = bool(result_config.get("autostart", False))
            autostart_ok, autostart_message = set_autostart(desired_autostart)
            if not autostart_ok:
                QMessageBox.warning(self, "启动设置", autostart_message)
                result_config["autostart"] = bool(self.config.get("autostart", False))
            self.config = result_config
            if self.config.get("color_theme") in list_themes():
                custom_appearance = dict(self.config.get("appearance", {}))
                apply_theme(self.config, self.config["color_theme"])
                self.config["appearance"].update({k: custom_appearance[k] for k in ("panel_opacity", "border_radius", "accent_color", "panel_bg_rgb", "panel_bg_dark_rgb") if k in custom_appearance})
            save_config(self.config)
            # ClipboardStore keeps its own config reference.  Keep it in sync
            # after settings returns, otherwise privacy/limit changes only
            # affect the next Lume process.
            self.store.config = self.config
            self.store.set_max_entries(self.config.get("clipboard_max_entries", 50))
            self.private_mode.blockSignals(True)
            self.private_mode.setChecked(bool(self.config.get("clipboard_private_mode", False)))
            self.private_mode.blockSignals(False)
            if sys.platform.startswith("linux"):
                register_gnome_shortcut(self.config.get("shortcut", "ALT+space"))
            self.apply_config()
            self._fine_tune_position()
            self.refresh_results()
        # Always re-register Windows hotkey after settings closes
        if sys.platform == "win32":
            self._register_win32_hotkey()
        # Double-check: log what's actually registered
        if sys.platform == "win32":
            try:
                from lume.win32_hotkey import get_active_hotkey_info
                info = get_active_hotkey_info()
                if info:
                    log.info("Active hotkey: %s", info[0])
            except Exception:
                pass

    def set_private_mode(self, enabled: bool):
        """Apply privacy mode immediately from the clipboard footer."""
        self.config["clipboard_private_mode"] = bool(enabled)
        self.store.config = self.config
        save_config(self.config)
        log.info("Clipboard private mode %s", "enabled" if enabled else "disabled")

    def eventFilter(self, watched, event):
        scroll = getattr(self, "clip_scroll", None)
        if scroll is not None and watched is scroll.viewport() and event.type() == QEvent.Type.Resize:
            timer = getattr(self, "_clipboard_reflow_timer", None)
            if timer is not None:
                timer.start(0)
        result_list = getattr(self, "result_list", None)
        result_viewport = result_list.viewport() if result_list is not None else None
        if watched is result_viewport and event.type() == QEvent.Type.ToolTip:
            if sys.platform == "win32" or not self.config.get("show_result_tooltips", True):
                return True
            if sys.platform == "win32" and (
                self.search_entry.hasFocus() or time.monotonic() < getattr(self, "_suppress_result_tooltips_until", 0.0)
            ):
                QToolTip.hideText()
                return True
        if watched is getattr(self, "search_entry", None) and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown,
                       Qt.Key.Key_Home, Qt.Key.Key_End):
                count = getattr(self, "result_list", None)
                count = count.count() if count is not None else 0
                if count:
                    current = max(0, self.result_list.currentRow())
                    grid = self.config.get("layout", "list") == "grid"
                    columns = max(1, self.result_list.viewport().width() // max(1, self.result_list.gridSize().width())) if grid else 1
                    if grid and key == Qt.Key.Key_Left:
                        target = max(0, current - 1)
                    elif grid and key == Qt.Key.Key_Right:
                        target = min(count - 1, current + 1)
                    elif key == Qt.Key.Key_Up:
                        target = max(0, current - columns)
                    elif key == Qt.Key.Key_Down:
                        target = min(count - 1, current + columns)
                    elif key == Qt.Key.Key_PageUp:
                        target = max(0, current - max(1, self.result_list.viewport().height() // 58))
                    elif key == Qt.Key.Key_PageDown:
                        target = min(count - 1, current + max(1, self.result_list.viewport().height() // 58))
                    elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                        target = current
                    elif key == Qt.Key.Key_Home:
                        target = 0
                    else:
                        target = count - 1
                    self.result_list.setCurrentRow(target)
                    self.result_list.scrollToItem(self.result_list.currentItem(), QListWidget.ScrollHint.EnsureVisible)
                return True
        if watched is getattr(self, "result_list", None) and event.type() == QEvent.Type.KeyPress:
            event = event  # type: QKeyEvent
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.activate_current()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._dismiss()
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self._dismissed = False
        super().changeEvent(event)

    def closeEvent(self, event):
        self._unregister_win32_hotkey()
        super().closeEvent(event)

    def hideEvent(self, event):
        self.hide_image_preview()
        sizes = self.splitter.sizes()
        if sizes:
            self.config["paned_position"] = sizes[0]
            save_config(self.config)
        super().hideEvent(event)


def configure_application(app):
    """Match Qt's Wayland app ID and desktop window icon to the launcher."""
    app.setApplicationName("Lume")
    app.setApplicationDisplayName("Lume")
    app.setDesktopFileName("com.lume.launcher")
    app.setWindowIcon(QIcon(str(_PROJECT_ROOT / "lume-256.png")))
    app.setQuitOnLastWindowClosed(False)


def run(argv=None) -> int:
    argv = argv or sys.argv
    background = "--background" in argv
    app = QApplication(argv)
    configure_application(app)

    socket = QLocalSocket()
    socket.connectToServer(APP_SERVER_NAME)
    if socket.waitForConnected(150):
        socket.write(b"background" if background else b"toggle")
        socket.waitForBytesWritten(150)
        return 0

    QLocalServer.removeServer(APP_SERVER_NAME)
    server = QLocalServer()
    if not server.listen(APP_SERVER_NAME):
        QMessageBox.critical(None, "Lume", f"无法创建单实例服务：{server.errorString()}")
        return 1

    window = LumeWindow(app, background=background)

    def accept_connection():
        connection = server.nextPendingConnection()
        if connection:
            connection.waitForReadyRead(100)
            if bytes(connection.readAll()) == b"toggle":
                window.toggle()
            connection.disconnectFromServer()

    server.newConnection.connect(accept_connection)
    if background:
        window._dismiss()
    else:
        window.show_launcher()
    return app.exec()
