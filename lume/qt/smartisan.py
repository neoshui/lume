"""Qt adaptation of smartisan-ui tokens; dark colors are a Lume extension.

Design: Smartisan OS UI Kit (Unofficial), Paix Chan, CC BY 4.0.
Reference: lemonteaau/smartisan-ui-skill (code and documentation: MIT).
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication


def is_smartisan(config):
    return config.get("ui_style", "smartisan") == "smartisan"


def is_dark(config):
    return config.get("theme") == "dark" or (
        config.get("theme", "auto") == "auto"
        and QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark
    )


def palette(dark=False):
    if dark:
        return dict(page="#252525", surface="#303030", well="#202020", text="#dedede",
                    label="#c4c4c4", muted="#a0a0a0", border="#484848", line="#3a3a3a",
                    top="#3a3a3a", bottom="#333333", pressed_top="#292929", pressed_bottom="#303030",
                    accent="#5b87eb", accent_bottom="#5883eb", accent_border="#3f68e2",
                    selection="#303d59", hover="#383838", chip="#343434", chip_border="#555555")
    return dict(page="#f5f5f5", surface="#ffffff", well="#f0f0f0", text="#333333",
                label="#636363", muted="#7f7f7f", border="#e2e2e2", line="#f2f2f2",
                top="#ffffff", bottom="#fcfcfc", pressed_top="#e9e9e9", pressed_bottom="#ececec",
                accent="#5b87eb", accent_bottom="#5883eb", accent_border="#3f68e2",
                selection="#e7edfb", hover="#f0f0f0", chip="#fafafa", chip_border="#cecece")


def gradient(top, bottom):
    return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {top}, stop:1 {bottom})"


def icon(name):
    return QIcon(str(Path(__file__).resolve().parents[1] / "resources" / "smartisan" / f"{name}.svg"))


def button_style(dark=False, checked=False):
    p = palette(dark)
    bg = gradient(p['accent'], p['accent_bottom']) if checked else gradient(p['top'], p['bottom'])
    color = '#ffffff' if checked else p['label']
    border = p['accent_border'] if checked else p['chip_border']
    pressed = '#4772e6' if checked else gradient(p['pressed_top'], p['pressed_bottom'])
    return f"""
        QPushButton {{ background: {bg}; color: {color}; border: 1px solid {border};
            border-radius: 4px; padding: 0; font-size: 12px; font-weight: 500; }}
        QPushButton:hover {{ border-color: {p['accent']}; }}
        QPushButton:pressed {{ background: {pressed}; }}
        QPushButton:focus {{ border-color: {p['accent']}; }}
        QPushButton:disabled {{ color: {p['muted']}; border-color: {p['border']}; }}
    """, color


def common_stylesheet(dark=False):
    p = palette(dark)
    check_icon = (Path(__file__).resolve().parents[1] / "resources" / "smartisan" / "check-white.svg").as_posix()
    chevron_icon = (Path(__file__).resolve().parents[1] / "resources" / "smartisan" / "chevron-down.svg").as_posix()
    chevron_up_icon = (Path(__file__).resolve().parents[1] / "resources" / "smartisan" / "chevron-up.svg").as_posix()
    surface = gradient(p['top'], p['bottom'])
    pressed = gradient(p['pressed_top'], p['pressed_bottom'])
    return f"""
        QWidget {{ color: {p['text']}; font-size: 13px; }}
        QLabel {{ background: transparent; border: 0; }}
        QPushButton {{ background: {surface}; color: {p['label']}; border: 1px solid {p['border']};
            border-radius: 4px; padding: 5px 12px; min-height: 20px; }}
        QPushButton:hover {{ border-color: {p['chip_border']}; }}
        QPushButton:pressed {{ background: {pressed}; border-color: {p['chip_border']}; }}
        QPushButton:disabled {{ color: {p['muted']}; border-color: {p['line']}; }}
        QPushButton:focus {{ border-color: {p['accent']}; }}
        QLineEdit, QComboBox, QSpinBox, QKeySequenceEdit {{ background: {p['surface']}; color: {p['text']};
            border: 1px solid {p['border']}; border-top-color: {p['chip_border']};
            border-radius: 6px; padding: 5px 10px; min-height: 22px;
            selection-background-color: {p['accent']}; selection-color: white; }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QKeySequenceEdit:focus {{ border-color: {p['accent']}; }}
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {p['muted']}; background: {p['page']}; }}
        QComboBox::drop-down {{ width: 24px; border: 0; }}
        QComboBox::down-arrow {{ image: url("{chevron_icon}"); width: 10px; height: 10px; border: 0; }}
        QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: 0; background: transparent; }}
        QSpinBox::up-arrow {{ image: url("{chevron_up_icon}"); width: 8px; height: 8px; }}
        QSpinBox::down-arrow {{ image: url("{chevron_icon}"); width: 8px; height: 8px; }}
        QComboBox QAbstractItemView {{ background: {p['surface']}; color: {p['text']};
            selection-background-color: {p['selection']}; selection-color: {p['text']}; }}
        QScrollArea {{ background: transparent; border: 0; }}
        QScrollBar:vertical {{ background: transparent; width: 6px; margin: 3px 0; }}
        QScrollBar::handle:vertical {{ background: {p['chip_border']}; min-height: 32px; border-radius: 3px; }}
        QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; height: 0; }}
        QScrollBar:horizontal {{ background: transparent; height: 6px; }}
        QScrollBar::handle:horizontal {{ background: {p['chip_border']}; border-radius: 3px; min-width: 30px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; background: transparent; }}
        QSlider::groove:horizontal {{ height: 5px; background: {p['well']}; border: 1px solid {p['border']}; border-radius: 3px; }}
        QSlider::sub-page:horizontal {{ background: {gradient(p['accent'], p['accent_bottom'])}; border-radius: 3px; }}
        QSlider::handle:horizontal {{ width: 18px; height: 18px; margin: -7px 0;
            background: {surface}; border: 1px solid {p['chip_border']}; border-radius: 9px; }}
        QSlider::handle:horizontal:pressed {{ background: {pressed}; }}
        QCheckBox {{ color: {p['label']}; spacing: 8px; }}
        QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 3px;
            background: {surface}; border: 1px solid {p['chip_border']}; }}
        QCheckBox::indicator:checked {{ background: {p['accent']}; border: 1px solid {p['accent_border']};
            image: url("{check_icon}"); }}
        QCheckBox::indicator:disabled {{ background: {p['well']}; border-color: {p['border']}; }}
        QMenu {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border']};
            border-radius: 6px; padding: 6px; }}
        QMenu::item {{ padding: 7px 18px; border-radius: 4px; }}
        QMenu::item:selected {{ background: {p['selection']}; }}
        QMenu::separator {{ height: 1px; background: {p['line']}; margin: 3px 6px; }}
        QToolTip {{ background: {p['surface']}; color: {p['label']}; border: 1px solid {p['border']}; padding: 5px 8px; }}
        QMessageBox {{ background: {p['page']}; }}
    """


def launcher_stylesheet(dark=False, font_size=15):
    p = palette(dark)
    return common_stylesheet(dark) + f"""
        QFrame#panel {{ background: {gradient(p['surface'], p['page'])};
            border: 1px solid {p['border']}; border-radius: 10px; }}
        QLineEdit#searchEntry {{ background: {gradient(p['well'], p['page'])};
            border: 1px solid {p['border']}; border-top-color: {p['chip_border']};
            border-radius: 6px; padding: 10px 14px; font-size: {font_size}px; }}
        QLineEdit#searchEntry:focus {{ border-color: {p['accent']}; }}
        QListWidget#resultList {{ background: {p['surface']}; border: 1px solid {p['line']};
            border-radius: 8px; outline: 0; padding: 3px; }}
        QListWidget#resultList::item {{ border: 0; padding: 0; margin: 2px 0; background: transparent; }}
        QListWidget#resultList::item:selected {{ color: {p['text']}; background: transparent; }}
        QWidget#resultRow, QWidget#resultRow:hover, QWidget#resultRow[selected="true"] {{ background: transparent; border: 0; }}
        QLabel#resultIcon {{ background: transparent; border: 0; }}
        QLabel#resultName {{ color: {p['text']}; font-size: 14px; font-weight: 400; }}
        QLabel#resultDescription {{ color: {p['muted']}; font-size: 12px; }}
        QLabel#categoryHeader {{ color: {p['muted']}; font-size: 12px; font-weight: 600; padding: 6px 12px; }}
        QWidget#clipboardArea {{ background: {p['well']}; border: 1px solid {p['border']}; border-radius: 10px; }}
        QWidget#clipboardArea QScrollArea, QWidget#clipboardArea QScrollArea > QWidget > QWidget {{ background: transparent; border: 0; }}
        QFrame#clipboardHeaderBar, QFrame#privateModeCard {{ background: transparent; border: 0; }}
        QLabel#clipboardTitle {{ color: {p['label']}; font-size: 13px; font-weight: 600; }}
        QLabel#statusLabel {{ color: {p['muted']}; font-size: 11px; padding-top: 3px; }}
        QPushButton#clipboardChip {{ background: {gradient(p['chip'], p['bottom'])};
            border: 1px solid {p['chip_border']}; color: {p['label']};
            border-radius: 12px; padding: 3px 10px; font-size: 12px; font-weight: 500; min-height: 22px; }}
        QPushButton#clipboardChip:hover {{ border-color: {p['accent']}; }}
        QPushButton#clipboardChip:pressed {{ background: {gradient(p['pressed_top'], p['pressed_bottom'])}; }}
        QPushButton#clipboardImage {{ background: {p['surface']}; border: 1px solid {p['chip_border']}; border-radius: 6px; padding: 3px; }}
        QPushButton#clipboardImage:hover {{ border-color: {p['accent']}; }}
        QPushButton#clipboardImage:pressed {{ background: {p['hover']}; }}
        QPushButton#clearClipboard {{ padding: 4px 10px; font-size: 12px; }}
        QPushButton#settings {{ border-radius: 6px; padding: 6px; }}
        QSplitter::handle {{ background: transparent; height: 12px; }}
    """


def settings_stylesheet(dark=False):
    p = palette(dark)
    return common_stylesheet(dark) + f"""
        QDialog {{ background: {p['page']}; }}
        QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{ background: {p['page']}; border: 0; }}
        QLabel#settingsTitle {{ color: {p['label']}; font-size: 18px; font-weight: 600; }}
        QLabel#settingsHint, QLabel#cardHint {{ color: {p['muted']}; font-size: 12px; }}
        QFrame#settingsCard {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 10px; }}
        QLabel#cardTitle {{ color: {p['label']}; font-size: 14px; font-weight: 600; }}
        QLabel#settingsValue {{ color: {p['muted']}; font-size: 12px; font-weight: 500; }}
        QTabWidget::tab-bar {{ alignment: center; }}
        QTabWidget::pane {{ border: 0; background: transparent; margin-top: 8px; }}
        QTabBar::tab {{ background: {gradient(p['top'], p['page'])}; color: {p['muted']};
            border: 1px solid {p['border']}; border-radius: 0; padding: 7px 20px; min-width: 54px; margin: 0; }}
        QTabBar::tab:first {{ border-top-left-radius: 6px; border-bottom-left-radius: 6px; }}
        QTabBar::tab:last {{ border-top-right-radius: 6px; border-bottom-right-radius: 6px; }}
        QTabBar::tab:selected {{ background: {gradient('#b4b4b4' if not dark else '#626262', '#a9a9a9' if not dark else '#565656')};
            color: white; border-color: {p['chip_border']}; font-weight: 600; }}
        QTabBar::tab:hover:!selected {{ background: {p['hover']}; }}
        QPushButton#primary {{ background: {gradient(p['accent'], p['accent_bottom'])}; color: white;
            border: 1px solid {p['accent_border']}; border-radius: 6px; font-weight: 600; padding: 6px 18px; }}
        QPushButton#primary:pressed {{ background: #4772e6; border-color: #2f54d7; }}
        QComboBox {{ min-width: 140px; max-width: 220px; padding-right: 24px; }}
        QLineEdit, QSpinBox {{ max-width: 260px; }}
        QListWidget {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 3px; }}
        QListWidget::item {{ color: {p['text']}; border-bottom: 1px solid {p['line']}; padding: 7px 10px; }}
        QListWidget::item:selected {{ background: {p['accent']}; color: white; }}
    """
