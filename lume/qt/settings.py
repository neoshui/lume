"""Settings dialogs for Lume Qt UI — old single-page SettingsDialog and current TabbedSettingsDialog."""

from __future__ import annotations

import sys

from lume.log_utils import get_logger
from lume.autostart import is_autostart_enabled
from lume.desktop import detect_desktop
from lume.qt.shell_extension import install_and_enable, is_enabled
from lume.version import VERSION

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
    QColorDialog,
)

from lume.qt import smartisan
from lume.qt.utils import _mix
from lume.themes import list_themes, get_theme

class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Lume 设置")
        self.setMinimumWidth(500)
        self.resize(500, 560)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background: #f7f9fc; }
            QLabel#settingsTitle { color: #18202d; font-size: 22px; font-weight: 700; padding: 4px 0 2px; }
            QLabel#settingsHint { color: #7a8798; font-size: 12px; padding-bottom: 8px; }
            QLabel#settingsSection { color: #6988b5; font-size: 11px; font-weight: 700;
                letter-spacing: 1px; padding-top: 12px; padding-bottom: 2px; }
            QFormLayout > QLabel { color: #536176; }
            QSpinBox, QComboBox, QLineEdit { min-height: 32px; border: 1px solid #d5ddea;
                border-radius: 9px; background: white; padding: 0 10px; }
            QSlider::groove:horizontal { height: 5px; background: #dce3ee; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #6988b5; border-radius: 2px; }
            QSlider::handle:horizontal { width: 16px; height: 16px; margin: -6px 0;
                background: #6988b5; border: 2px solid white; border-radius: 8px; }
            QLabel#sliderValue { color: #6988b5; font-weight: 600; min-width: 42px; }
            QSpinBox:focus, QComboBox:focus, QLineEdit:focus { border-color: #6988b5; }
            QPushButton { min-height: 32px; border-radius: 9px; padding: 0 16px;
                border: 1px solid #d5ddea; background: white; color: #42536a; }
            QPushButton:hover { border-color: #6988b5; }
            QPushButton#primary { background: #6988b5; color: white; border: 0; font-weight: 600; }
        """)
        form = QFormLayout(self)
        form.setContentsMargins(28, 24, 28, 24)
        form.setVerticalSpacing(11)
        title = QLabel("Lume 设置")
        title.setObjectName("settingsTitle")
        hint = QLabel("调整启动器外观、尺寸和使用习惯")
        hint.setObjectName("settingsHint")
        form.addRow(title)
        form.addRow(hint)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(480, 1400)
        self.width_spin.setValue(config.get("launcher_width", 680))
        form.addRow(self._section("窗口与布局"))
        self.width_slider, self.width_value = self._slider_row(480, 1400, self.width_spin.value(), self.width_spin)
        form.addRow("窗口宽度", self._slider_control(self.width_slider, self.width_value))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(400, 1200)
        self.height_spin.setValue(config.get("launcher_height", 720))
        self.height_slider, self.height_value = self._slider_row(400, 1200, self.height_spin.value(), self.height_spin)
        form.addRow("窗口高度", self._slider_control(self.height_slider, self.height_value))
        self.max_results = QSpinBox()
        self.max_results.setRange(4, 100)
        self.max_results.setValue(min(config.get("max_results", 20), 100))
        form.addRow("最大结果数", self.max_results)
        self.theme = QComboBox()
        self.theme.addItems(["auto", "light", "dark"])
        self.theme.setCurrentText(config.get("theme", "auto"))
        form.addRow(self._section("外观"))
        form.addRow("主题", self.theme)
        self.shortcut = QLineEdit(config.get("shortcut", "ALT+space"))
        self.shortcut.setPlaceholderText("例如 ALT+space")
        form.addRow("快捷键", self.shortcut)
        self.clipboard_max = QSpinBox()
        self.clipboard_max.setRange(10, 200)
        self.clipboard_max.setValue(config.get("clipboard_max_entries", 50))
        form.addRow(self._section("剪贴板"))
        form.addRow("剪贴板条目数", self.clipboard_max)
        self.font_size = QSpinBox()
        self.font_size.setRange(11, 24)
        self.font_size.setValue(config.get("font_size", 15))
        self.font_slider, self.font_value = self._slider_row(11, 24, self.font_size.value(), self.font_size)
        form.addRow("界面字体大小", self._slider_control(self.font_slider, self.font_value))
        self.density = QComboBox()
        self.density.addItems(["compact", "comfortable", "airy"])
        self.density.setCurrentText(config.get("result_density", "comfortable"))
        form.addRow("结果行密度", self.density)
        self.layout_mode = QComboBox()
        self.layout_mode.addItems(["list", "grid"])
        self.layout_mode.setCurrentText(config.get("layout", "list"))
        form.addRow("结果布局", self.layout_mode)

        buttons = QHBoxLayout()
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setObjectName("primary")
        save.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        form.addRow(buttons)

    def _slider_row(self, minimum, maximum, value, spin):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        label = QLabel(str(value))
        label.setObjectName("sliderValue")
        label.setAlignment(Qt.AlignmentFlag.AlignRight)
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        spin.valueChanged.connect(lambda v, target=label: target.setText(str(v)))
        return slider, label

    def _slider_control(self, slider, value):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(slider, 1)
        row.addWidget(value)
        return box

    def _section(self, title):
        label = QLabel(title.upper())
        label.setObjectName("settingsSection")
        return label

    def values(self):
        result = dict(self.config)
        result.update({
            "launcher_width": self.width_spin.value(),
            "launcher_height": self.height_spin.value(),
            "max_results": self.max_results.value(),
            "theme": self.theme.currentText(),
            "layout": self.layout_mode.currentText(),
            "shortcut": self.shortcut.text().strip() or "ALT+space",
            "clipboard_max_entries": self.clipboard_max.value(),
            "font_size": self.font_size.value(),
            "result_density": self.density.currentText(),
        })
        return result


class TabbedSettingsDialog(QDialog):
    """Multi-page settings matching the original GTK settings structure."""
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("设置")
        self.resize(680, 580)
        self.setMinimumSize(520, 400)
        appearance = self.config.get("appearance", {})
        # Settings keeps its stable blue-grey chrome; the user accent is for
        # the launcher/search surface and must not tint the settings UI.
        accent = "#6988b5"
        accent_soft = _mix(accent, "#ffffff", 0.82)
        self.setStyleSheet(f"""
            QDialog {{ background: #f5f7fb; }}
            QLabel#settingsTitle {{ color: #152033; font-size: 22px; font-weight: 800; }}
            QLabel#settingsHint {{ color: #7d8898; font-size: 12px; }}
            QTabWidget::pane {{ border: 0; background: transparent; top: -1px; }}
            QTabBar::tab {{ min-height: 28px; padding: 6px 14px; margin-right: 5px;
                color: #68758a; border: 1px solid transparent; border-radius: 8px; background: transparent; }}
            QTabBar::tab:hover {{ background: rgba(255, 255, 255, 0.68); border-color: #e0e6f0; }}
            QTabBar::tab:selected {{ color: {accent}; background: {accent_soft}; border-color: {_mix(accent, "#ffffff", 0.55)}; font-weight: 700; }}
            QScrollArea {{ background: transparent; border: 0; }}
            QFrame#settingsCard {{ background: rgba(255, 255, 255, 0.82); border: 1px solid #dde5f0; border-radius: 8px; }}
            QFrame#settingsCard:hover {{ border-color: {_mix(accent, "#ffffff", 0.48)}; }}
            QLabel#cardTitle {{ color: #263a5a; font-size: 14px; font-weight: 800; }}
            QLabel#cardHint {{ color: #8995a8; font-size: 11px; }}
            QLabel#settingsValue {{ color: {accent}; font-size: 12px; font-weight: 700; }}
            QLineEdit, QComboBox, QSpinBox, QKeySequenceEdit {{
                min-height: 32px; max-width: 250px; border: 1px solid #d4deeb; border-radius: 8px;
                background: rgba(255, 255, 255, 0.92); padding: 0 10px; color: #172033;
                selection-background-color: {accent_soft}; selection-color: #172033;
            }}
            QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QKeySequenceEdit:hover {{ border-color: #b9c7d9; }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QKeySequenceEdit:focus {{
                border: 1px solid {accent}; background: #ffffff;
            }}
            QComboBox {{ min-width: 140px; max-width: 178px; padding-right: 24px; }}
            QComboBox::drop-down {{ width: 24px; border: 0; }}
            QComboBox::down-arrow {{
                image: none; width: 0; height: 0; margin-right: 8px;
                border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {accent};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: 0; }}
            QSpinBox {{ padding-right: 10px; }}
            QSlider::groove:horizontal {{ height: 4px; background: #d9e1ec; border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -6px 0;
                background: white; border: 2px solid {accent}; border-radius: 8px; }}
            QSlider::handle:horizontal:hover {{ background: {accent_soft}; }}
            QPushButton {{ min-height: 32px; border-radius: 8px; padding: 0 14px;
                border: 1px solid #d4deeb; background: rgba(255, 255, 255, 0.9); color: #253148; }}
            QPushButton:hover {{ border-color: {accent}; background: #ffffff; }}
            QPushButton#primary {{ background: {accent}; color: white; border: 0; font-weight: 700; }}
            QPushButton#primary:hover {{ background: {_mix(accent, "#000000", 0.1)}; }}
            QCheckBox {{ spacing: 8px; color: #40506a; }}
            QListWidget {{ background: rgba(255, 255, 255, 0.55); border: 1px solid #dce4ef; border-radius: 8px; padding: 4px; }}
            QListWidget::item {{ min-height: 26px; padding: 4px 8px; border-radius: 6px; }}
            QListWidget::item:selected {{ background: {accent_soft}; color: #172033; }}
            QScrollBar:vertical {{ background: transparent; width: 7px; margin: 4px 1px; }}
            QScrollBar::handle:vertical {{ background: #b3bfce; min-height: 32px; border-radius: 3px; }}
            QScrollBar::handle:vertical:hover {{ background: {accent}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; height: 0; }}
        """)
        self._classic_stylesheet = self.styleSheet()
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(8)
        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)
        self._build_appearance()
        self._build_shortcut()
        self._build_web()
        self._build_about()
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton("取消"); cancel.clicked.connect(self.reject)
        save = QPushButton("保存"); save.setObjectName("primary"); save.clicked.connect(self.accept)
        buttons.addWidget(cancel); buttons.addWidget(save); root.addLayout(buttons)
        self.ui_style.currentIndexChanged.connect(self._apply_ui_style)
        self.theme.currentTextChanged.connect(self._apply_ui_style)
        self._apply_ui_style()

    def _page(self):
        page = QWidget(); layout = QFormLayout(page); layout.setContentsMargins(22, 22, 22, 22); layout.setVerticalSpacing(10)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        return page, layout

    def _add_tab(self, page, title):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, title)

    def _build_appearance(self):
        page = QWidget(); root = QVBoxLayout(page); root.setContentsMargins(0, 12, 0, 0); root.setSpacing(10)
        self.width = QSlider(Qt.Orientation.Horizontal); self.width.setRange(480, 1400); self.width.setValue(self.config.get("launcher_width", 680))
        self.height = QSlider(Qt.Orientation.Horizontal); self.height.setRange(400, 1200); self.height.setValue(self.config.get("launcher_height", 720))
        self.vertical_offset = QSlider(Qt.Orientation.Horizontal); self.vertical_offset.setRange(-260, 260); self.vertical_offset.setValue(int(self.config.get("launcher_vertical_offset", 140)))
        self.ui_style = QComboBox()
        self.ui_style.addItem("Smartisan", "smartisan")
        self.ui_style.addItem("Lume 经典", "classic")
        self.ui_style.setCurrentIndex(0 if smartisan.is_smartisan(self.config) else 1)
        self.ui_style.setToolTip("Smartisan 采用浅灰层次与轻拟物控件；深色是 Lume 的适配版本")
        self.theme = QComboBox()
        for title, value in [("跟随系统", "auto"), ("浅色", "light"), ("深色", "dark")]:
            self.theme.addItem(title, value)
        self.theme.setCurrentIndex(max(0, self.theme.findData(self.config.get("theme", "auto"))))
        self.palette = QComboBox(); self.palette.addItems(list_themes()); self.palette.setCurrentText(self.config.get("color_theme", "晨雾"))
        self.theme_preview = QFrame(); self.theme_preview.setFixedSize(118, 22)
        self.theme_preview_text = QLabel(); self.theme_preview_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout = QVBoxLayout(self.theme_preview); preview_layout.setContentsMargins(7, 0, 7, 0); preview_layout.addWidget(self.theme_preview_text)
        self.palette.currentTextChanged.connect(self._update_theme_preview)
        self.layout_mode = QComboBox()
        self.layout_mode.addItem("列表", "list"); self.layout_mode.addItem("图标网格", "grid")
        self.layout_mode.setCurrentIndex(max(0, self.layout_mode.findData(self.config.get("layout", "list"))))
        self.density = QComboBox()
        for title, value in [("紧凑", "compact"), ("舒适", "comfortable"), ("宽松", "airy")]:
            self.density.addItem(title, value)
        self.density.setCurrentIndex(max(0, self.density.findData(self.config.get("result_density", "comfortable"))))
        self.font = QSlider(Qt.Orientation.Horizontal); self.font.setRange(11, 24); self.font.setValue(self.config.get("font_size", 15))
        appearance = self.config.get("appearance", {})
        self.opacity = QSlider(Qt.Orientation.Horizontal); self.opacity.setRange(70, 100); self.opacity.setValue(round(float(appearance.get("panel_opacity", 0.97)) * 100))
        self.radius = QSlider(Qt.Orientation.Horizontal); self.radius.setRange(8, 28); self.radius.setValue(int(appearance.get("border_radius", 18)))
        self.accent = appearance.get("accent_color", "rgb(105, 136, 181)")
        self.panel_rgb = QLineEdit(appearance.get("panel_bg_rgb", "247, 249, 252"))
        self.show_apps_on_open = QCheckBox("打开时显示应用列表")
        self.show_apps_on_open.setChecked(self.config.get("show_apps_on_open", True))
        self.show_apps_on_open.setToolTip("关闭后，输入关键词才显示搜索结果")
        self.show_descriptions = QCheckBox("显示搜索结果详情")
        self.show_descriptions.setChecked(self.config.get("show_result_descriptions", True))
        self.show_tooltips = QCheckBox("鼠标悬停显示结果提示")
        self.show_tooltips.setChecked(self.config.get("show_result_tooltips", True))
        self.accent_palette = self._accent_palette()
        theme_card, theme_form = self._settings_card("主题与显示", "选择界面风格与明暗模式；Smartisan 深色为适配版本")
        theme_form.addRow("界面风格", self.ui_style)
        theme_form.addRow("主题模式", self.theme); theme_form.addRow("配色主题", self.palette); theme_form.addRow("主题预览", self.theme_preview)
        theme_form.addRow("启动显示", self.show_apps_on_open)
        theme_form.addRow("结果布局", self.layout_mode); theme_form.addRow("结果密度", self.density); theme_form.addRow("详情显示", self.show_descriptions); theme_form.addRow("悬停提示", self.show_tooltips)
        surface_card, surface_form = self._settings_card("面板与窗口", "调整启动器的尺寸、字体和表面质感")
        surface_form.addRow("窗口宽度", self._slider_control(self.width)); surface_form.addRow("窗口高度", self._slider_control(self.height)); surface_form.addRow("垂直偏移", self._slider_control(self.vertical_offset)); surface_form.addRow("字体大小", self._slider_control(self.font))
        surface_form.addRow("面板透明度", self._slider_control(self.opacity)); surface_form.addRow("面板圆角", self._slider_control(self.radius)); surface_form.addRow("强调色", self.accent_palette); surface_form.addRow("浅色面板颜色", self.panel_rgb)
        self._update_theme_preview(self.palette.currentText())
        root.addWidget(theme_card); root.addWidget(surface_card); root.addStretch()
        self._add_tab(page, "外观")

    def _build_shortcut(self):
        page = QWidget(); root = QVBoxLayout(page); root.setContentsMargins(0, 12, 0, 0); root.setSpacing(10)
        self._capturing = False
        self._pending_shortcut = self.config.get("shortcut", "ALT+space")
        self.clipboard_max = QSpinBox(); self.clipboard_max.setRange(10, 200); self.clipboard_max.setValue(self.config.get("clipboard_max_entries", 50))
        self.clipboard_expire = QSpinBox(); self.clipboard_expire.setRange(0, 8760); self.clipboard_expire.setValue(int(self.config.get("clipboard_auto_expire_hours", 0)))
        self.clipboard_text_limit = QSpinBox(); self.clipboard_text_limit.setRange(100, 1000000); self.clipboard_text_limit.setValue(int(self.config.get("clipboard_max_text_length", 10000)))
        self.clipboard_image_limit = QSpinBox(); self.clipboard_image_limit.setRange(1, 200); self.clipboard_image_limit.setValue(max(1, int(self.config.get("clipboard_max_image_bytes", 10 * 1024 * 1024) / 1024 / 1024)))
        self.clipboard_filter_sensitive = QCheckBox("跳过疑似密钥、令牌和密码"); self.clipboard_filter_sensitive.setChecked(self.config.get("clipboard_filter_sensitive", True))
        card, form = self._settings_card("系统快捷键", "点击按钮后按下组合键")
        # Custom capture button (works on Windows where Alt+Space is intercepted by system)
        self.shortcut_btn = QPushButton()
        self.shortcut_btn.setFixedWidth(220)
        self.shortcut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_shortcut_display()
        self.shortcut_btn.clicked.connect(self._on_capture_clicked)
        reset_shortcut = QPushButton("恢复 Alt+Space")
        reset_shortcut.clicked.connect(lambda: self._finish_shortcut_capture("ALT+SPACE"))
        shortcut_row = QHBoxLayout()
        shortcut_row.setContentsMargins(0, 0, 0, 0)
        shortcut_row.setSpacing(8)
        shortcut_row.addWidget(self.shortcut_btn)
        shortcut_row.addWidget(reset_shortcut)
        hint = QLabel("点击按钮，然后按下键盘快捷键组合")
        hint.setStyleSheet("color:#7f7f7f; font-size:12px;")
        form.addRow("全局快捷键", shortcut_row); form.addRow("剪贴板历史数量", self.clipboard_max)
        form.addRow("自动过期（小时，0=关闭）", self.clipboard_expire)
        form.addRow("单条文本上限", self.clipboard_text_limit)
        form.addRow("单张图片上限（MB）", self.clipboard_image_limit)
        form.addRow(self.clipboard_filter_sensitive); form.addRow(hint)
        startup_card, startup_form = self._settings_card("启动设置", "控制当前用户登录系统后是否在后台启动 Lume")
        self.autostart = QCheckBox("登录系统后自动启动 Lume")
        self.autostart.setChecked(is_autostart_enabled())
        startup_form.addRow(self.autostart)
        root.addWidget(startup_card)
        root.addWidget(card)
        if detect_desktop().needs_gnome_extension:
            clip_card, clip_form = self._settings_card("GNOME 剪切板组件", "用于 Wayland 下可靠保存后台文本和截图历史")
            self.shell_clipboard_status = QLabel()
            install_shell = QPushButton("安装并启用")
            install_shell.clicked.connect(self._install_shell_clipboard_component)
            clip_form.addRow("当前状态", self.shell_clipboard_status)
            clip_form.addRow("Lume 组件", install_shell)
            root.addWidget(clip_card)
            self._update_shell_clipboard_status()
        root.addStretch()
        self._add_tab(page, "快捷键")
        # Install event filter to capture keys at LumeWindow level
        self.tabs.installEventFilter(self)

    def _update_shell_clipboard_status(self):
        if hasattr(self, "shell_clipboard_status"):
            enabled = is_enabled()
            self.shell_clipboard_status.setText("已启用：完整后台历史可用" if enabled else "未启用：只能读取当前剪切板")
            self.shell_clipboard_status.setStyleSheet("color: #4f8a64;" if enabled else "color: #a46b38;")

    def _install_shell_clipboard_component(self):
        ok, message = install_and_enable()
        self._update_shell_clipboard_status()
        QMessageBox.information(self, "Lume 剪切板组件" if ok else "安装失败", message)

    def _update_shortcut_display(self):
        text = getattr(self, "_pending_shortcut", self.config.get("shortcut", "ALT+space"))
        display = text.replace("ALT", "Alt").replace("CTRL", "Ctrl").replace("SHIFT", "Shift").replace("LOGO", "Win")
        if hasattr(self, 'shortcut_btn'):
            self.shortcut_btn.setText(f"  {display}  ")

    def _on_capture_clicked(self):
        self._capturing = True
        self.shortcut_btn.setText("  按下快捷键...  ")
        self.shortcut_btn.setEnabled(False)
        # Temporarily unregister the Windows hotkey so Alt+Space reaches Qt
        if sys.platform == "win32":
            try:
                from lume.win32_hotkey import unregister_all
                unregister_all()
                log.info("Hotkey unregistered for capture")
            except Exception:
                pass
        # grabKeyboard on self to capture all keys
        self.grabKeyboard()
        self.setFocus()

    def _finish_shortcut_capture(self, shortcut: str):
        self._pending_shortcut = shortcut
        self._capturing = False
        self._update_shortcut_display()
        self.shortcut_btn.setEnabled(True)
        if QWidget.keyboardGrabber() is self:
            self.releaseKeyboard()

    def keyPressEvent(self, event):
        if getattr(self, '_capturing', False):
            key = event.key()
            mods = event.modifiers()
            parts = []
            if mods & Qt.KeyboardModifier.ControlModifier: parts.append("CTRL")
            if mods & Qt.KeyboardModifier.AltModifier: parts.append("ALT")
            if mods & Qt.KeyboardModifier.ShiftModifier: parts.append("SHIFT")
            if mods & Qt.KeyboardModifier.MetaModifier: parts.append("LOGO")
            # Get key name
            key_str = QKeySequence(key).toString().upper()
            # Ignore modifier-only keys
            if key_str not in {"CTRL", "ALT", "SHIFT", "META"} and key_str:
                parts.append(key_str)
            elif event.text() and event.text().upper() not in {"CTRL", "ALT", "SHIFT", "META"}:
                parts.append(event.text().upper())

            if len(parts) >= 2:
                self._finish_shortcut_capture("+".join(parts))
                # Hotkey will be re-registered when user saves settings
            event.accept()
            return
        super().keyPressEvent(event)

    def nativeEvent(self, event_type, message):
        """Capture Windows-reserved Alt+Space before it opens the system menu."""
        if sys.platform == "win32":
            try:
                import ctypes
                import ctypes.wintypes

                msg = ctypes.wintypes.MSG.from_address(int(message))
                wm_syskeydown = 0x0104
                wm_syscommand = 0x0112
                sc_keymenu = 0xF100
                vk_space = 0x20
                vk_menu = 0x12

                if getattr(self, "_capturing", False) and msg.message == wm_syskeydown and msg.wParam == vk_space:
                    if ctypes.windll.user32.GetKeyState(vk_menu) & 0x8000:
                        self._suppress_alt_space_menu = True
                        self._finish_shortcut_capture("ALT+SPACE")
                        QTimer.singleShot(300, lambda: setattr(self, "_suppress_alt_space_menu", False))
                        return True, 0
                if getattr(self, "_suppress_alt_space_menu", False) and msg.message == wm_syscommand:
                    if int(msg.wParam) & 0xFFF0 == sc_keymenu:
                        return True, 0
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    def _build_web(self):
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 12, 0, 0)
        root.setSpacing(10)
        engine = self.config.get("search_engine", {})
        self.engine = QComboBox()
        self.engine_presets = {
            "Google": "https://www.google.com/search?q={query}",
            "Bing": "https://www.bing.com/search?q={query}",
            "DuckDuckGo": "https://duckduckgo.com/?q={query}",
            "百度": "https://www.baidu.com/s?wd={query}",
            "Brave": "https://search.brave.com/search?q={query}",
        }
        self.engine.addItems(list(self.engine_presets))
        current = engine.get("name", "Google")
        if current not in self.engine_presets:
            self.engine.addItem(current)
        self.engine.setCurrentText(current)
        self.engine_url = QLineEdit(engine.get("url", self.engine_presets.get(current, "")))
        self.engine.currentTextChanged.connect(lambda name: self.engine_url.setText(self.engine_presets.get(name, self.engine_url.text())))
        search_card, search_form = self._settings_card("搜索引擎配置", "输入普通关键词时使用的默认搜索服务")
        search_form.addRow("搜索引擎", self.engine)
        search_form.addRow("搜索 URL", self.engine_url)
        root.addWidget(search_card)

        pin_card, pin_form = self._settings_card("固定网址快捷方式", "常用网站会作为独立结果出现在主搜索中")
        self.web_list = QListWidget(); self.web_list.setFixedHeight(86)
        for item in self.config.get("web_shortcuts", []):
            self.web_list.addItem(f"{item.get('name', '')}  ·  {item.get('url', '')}")
        self.web_list.itemClicked.connect(self._load_web_shortcut)
        pin_form.addRow(self.web_list)
        self.web_empty_hint = QLabel("暂未固定网址，可在下方添加")
        self.web_empty_hint.setStyleSheet("color:#94a0b0; font-size:12px;")
        self.web_empty_hint.setVisible(self.web_list.count() == 0)
        pin_form.addRow(self.web_empty_hint)
        add_row = QHBoxLayout(); self.web_name = QLineEdit(); self.web_name.setPlaceholderText("名称")
        self.web_url = QLineEdit(); self.web_url.setPlaceholderText("https://example.com/{query}")
        add = QPushButton("添加"); add.clicked.connect(self._add_web_shortcut)
        add_row.addWidget(self.web_name); add_row.addWidget(self.web_url, 2); add_row.addWidget(add)
        pin_form.addRow("名称与网址", add_row)
        remove = QPushButton("删除选中网址"); remove.clicked.connect(self._remove_web_shortcut)
        edit = QPushButton("用输入内容更新选中网址"); edit.clicked.connect(self._update_web_shortcut)
        action_row = QHBoxLayout(); action_row.addWidget(remove); action_row.addWidget(edit)
        pin_form.addRow(action_row)
        hint = QLabel("搜索 URL 必须包含 {query}；网址快捷方式会出现在搜索结果中。")
        hint.setStyleSheet("color:#7f7f7f; font-size:12px;"); pin_form.addRow(hint)
        root.addWidget(pin_card)
        root.addStretch()
        self._add_tab(page, "搜索 & 网址")

    def _settings_card(self, title, subtitle):
        card = QFrame(); card.setObjectName("settingsCard")
        box = QVBoxLayout(card); box.setContentsMargins(16, 13, 16, 13); box.setSpacing(7)
        heading = QLabel(title); heading.setObjectName("cardTitle")
        hint = QLabel(subtitle); hint.setObjectName("cardHint")
        form_host = QWidget(); form = QFormLayout(form_host); form.setContentsMargins(0, 3, 0, 0); form.setVerticalSpacing(8)
        form.setHorizontalSpacing(14)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        box.addWidget(heading); box.addWidget(hint); box.addWidget(form_host)
        return card, form

    def _build_about(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0, 12, 0, 0); layout.setSpacing(10)
        card, card_form = self._settings_card("关于 Lume", "跨平台浮动启动器")
        info = QLabel(f"Lume 是一款跨平台浮动启动器。\n\n版本：{VERSION}\n快捷键：系统全局快捷键呼出\nEsc：关闭启动器\nEnter：执行选中结果\n\n配置：~/.config/lume/config.json\n数据：~/.local/share/lume/")
        info.setStyleSheet("color:#7f7f7f;")
        card_form.addRow(info)
        credit = QLabel('Smartisan UI：<a href="https://github.com/lemonteaau/smartisan-ui-skill">lemonteaau / smartisan-ui-skill</a><br>原始设计：Paix Chan · Smartisan OS UI Kit (Unofficial) · CC BY 4.0')
        credit.setOpenExternalLinks(True)
        credit.setWordWrap(True)
        credit.setObjectName("cardHint")
        card_form.addRow(credit)
        layout.addWidget(card); layout.addStretch()
        self._add_tab(page, "关于")

    def values(self):
        shortcut_text = getattr(self, "_pending_shortcut", self.config.get("shortcut", "ALT+space"))
        shortcuts = []
        for i in range(self.web_list.count()):
            text = self.web_list.item(i).text()
            if "  ·  " in text:
                name, url = text.split("  ·  ", 1); shortcuts.append({"name": name, "url": url})
        result = dict(self.config)
        appearance = dict(result.get("appearance", {})); appearance.update({"panel_opacity": self.opacity.value() / 100.0, "border_radius": self.radius.value(), "accent_color": self.accent, "panel_bg_rgb": self.panel_rgb.text().strip() or "247, 249, 252"})
        result.update({"ui_style": self.ui_style.currentData(), "launcher_width": self.width.value(), "launcher_height": self.height.value(), "launcher_vertical_offset": self.vertical_offset.value(), "theme": self.theme.currentData(), "color_theme": self.palette.currentText(), "appearance": appearance,
                       "layout": self.layout_mode.currentData(), "result_density": self.density.currentData(), "font_size": self.font.value(), "show_apps_on_open": self.show_apps_on_open.isChecked(), "show_result_descriptions": self.show_descriptions.isChecked(), "show_result_tooltips": self.show_tooltips.isChecked(),
                       "shortcut": shortcut_text, "clipboard_max_entries": self.clipboard_max.value(),
                       "clipboard_auto_expire_hours": self.clipboard_expire.value(),
                       "clipboard_max_text_length": self.clipboard_text_limit.value(),
                       "clipboard_max_image_bytes": self.clipboard_image_limit.value() * 1024 * 1024,
                       "clipboard_filter_sensitive": self.clipboard_filter_sensitive.isChecked(),
                       "autostart": self.autostart.isChecked(),
                       # Privacy mode is intentionally controlled from the
                       # clipboard footer for quick, visible access.
                       "clipboard_private_mode": self.config.get("clipboard_private_mode", False),
                       "web_shortcuts": shortcuts,
                       "search_engine": {"name": self.engine.currentText() or "Google", "url": self.engine_url.text().strip() or "https://www.google.com/search?q={query}"}})
        return result

    def _accent_palette(self):
        holder = QWidget(); row = QHBoxLayout(holder); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(8)
        colors = ["#7da2d8", "#79b89b", "#a995d3", "#d6a36a", "#d58b9a", "#78b8c8", "#93a0b2"]
        self._accent_swatches = []
        for color in colors:
            swatch = QPushButton(); swatch.setFixedSize(30, 30); swatch.setToolTip(f"强调色 {color}")
            swatch.clicked.connect(lambda checked=False, c=color: self._set_accent(c))
            row.addWidget(swatch)
            self._accent_swatches.append((color, swatch))
        custom = QPushButton("自定义")
        custom.setToolTip("从调色盘选择强调色")
        self._custom_accent_button = custom
        custom.clicked.connect(self._choose_accent)
        row.addWidget(custom); row.addStretch()
        self._refresh_accent_palette()
        return holder

    def _set_accent(self, color):
        self.accent = QColor(color).name()
        self._refresh_accent_palette()

    def _choose_accent(self):
        color = QColorDialog.getColor(QColor(self.accent), self, "选择强调色")
        if color.isValid():
            self._set_accent(color.name())

    def _refresh_accent_palette(self):
        """Make the active preset/custom accent unambiguous before saving."""
        active = QColor(self.accent).name().lower()
        for color, swatch in getattr(self, "_accent_swatches", []):
            selected = QColor(color).name().lower() == active
            border = "#172033" if selected else "white"
            width = 3 if selected else 2
            swatch.setStyleSheet(
                f"QPushButton {{ background:{color}; border:{width}px solid {border}; border-radius:15px; }}"
                " QPushButton:hover { border:3px solid #27364c; }"
            )
            swatch.setProperty("selected", selected)
        custom = getattr(self, "_custom_accent_button", None)
        if custom is not None:
            preset = any(QColor(color).name().lower() == active for color, _ in self._accent_swatches)
            custom.setText("自定义" if preset else f"自定义 {active}")
            custom.setStyleSheet(
                f"QPushButton {{ border:1px solid {'#6988b5' if not preset else '#d4deeb'}; }}"
            )

    def _add_web_shortcut(self):
        name, url = self.web_name.text().strip(), self.web_url.text().strip()
        if name and url:
            self.web_list.addItem(f"{name}  ·  {url}")
            self.web_empty_hint.hide()
            self.web_name.clear(); self.web_url.clear()

    def _update_web_shortcut(self):
        item = self.web_list.currentItem()
        name, url = self.web_name.text().strip(), self.web_url.text().strip()
        if item and name and url:
            item.setText(f"{name}  ·  {url}")

    def _remove_web_shortcut(self):
        row = self.web_list.currentRow()
        if row >= 0:
            self.web_list.takeItem(row)
        self.web_empty_hint.setVisible(self.web_list.count() == 0)

    def _load_web_shortcut(self, item):
        if "  ·  " in item.text():
            name, url = item.text().split("  ·  ", 1)
            self.web_name.setText(name); self.web_url.setText(url)

    def _apply_ui_style(self, *_):
        config = dict(self.config, ui_style=self.ui_style.currentData(), theme=self.theme.currentData())
        active = smartisan.is_smartisan(config)
        self.setStyleSheet(smartisan.settings_stylesheet(smartisan.is_dark(config)) if active else self._classic_stylesheet)
        for control in (self.palette, self.opacity, self.radius, self.accent_palette, self.panel_rgb):
            control.setEnabled(not active)
            control.setToolTip("Smartisan 使用统一的配色与材质；切换到 Lume 经典可自定义" if active else "")
        self._update_theme_preview(self.palette.currentText())

    def _update_theme_preview(self, theme_name):
        if self.ui_style.currentData() == "smartisan":
            dark = smartisan.is_dark(dict(self.config, theme=self.theme.currentData()))
            p = smartisan.palette(dark)
            self.theme_preview.setStyleSheet(f"QFrame {{ background: {p['page']}; border: 1px solid {p['border']}; border-radius: 4px; }}")
            self.theme_preview_text.setText("Smartisan · " + ("深色" if dark else "浅色"))
            self.theme_preview_text.setStyleSheet(f"color: {p['accent']}; font-size: 11px;")
            return
        theme = get_theme(theme_name) or {}
        bg = theme.get("panel_bg_rgb", "247, 249, 252")
        accent = theme.get("accent_color", "#6988b5")
        text = theme.get("text_color", "#18202d")
        self.theme_preview.setStyleSheet(f"QFrame {{ background: rgb({bg}); border: 1px solid {accent}; border-radius: 8px; }}")
        self.theme_preview_text.setText(theme_name)
        self.theme_preview_text.setStyleSheet(f"color: {text}; font-size: 11px; font-weight:700;")

    def _slider_control(self, slider):
        box = QWidget(); row = QHBoxLayout(box); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(10)
        value = QLabel(str(slider.value())); value.setObjectName("settingsValue"); value.setMinimumWidth(36); value.setAlignment(Qt.AlignmentFlag.AlignRight)
        slider.valueChanged.connect(lambda v, label=value: label.setText(str(v)))
        row.addWidget(slider, 1); row.addWidget(value)
        return box
