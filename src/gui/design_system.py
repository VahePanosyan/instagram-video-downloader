"""Modern design system tokens and dynamic dual-theme QSS stylesheets."""

from typing import Type


class ThemeTokens:
    """Base design tokens and brand constants."""
    # Brand Accents
    IG_PURPLE = "#833AB4"
    IG_PINK = "#E1306C"
    IG_ORANGE = "#FD1D1D"
    IG_YELLOW = "#FCB045"
    IG_CYAN = "#00F2FE"
    YT_RED = "#FF0000"

    # Status Indicators
    STATUS_SUCCESS = "#10B981"
    STATUS_WARNING = "#F59E0B"
    STATUS_ERROR = "#EF4444"
    STATUS_INFO = "#3B82F6"


class DarkThemeTokens(ThemeTokens):
    """Dark theme palette (Deep Obsidian & Slate)."""
    NAME = "dark"
    BG_WINDOW = "#0B0F19"
    SURFACE_BASE = "#111827"
    SURFACE_DARK = "#161E2E"
    SURFACE_CARD = "#1E293B"
    SURFACE_HOVER = "#243247"
    SURFACE_INPUT = "#0F172A"

    BORDER_COLOR = "#334155"
    BORDER_DEFAULT = "#334155"
    BORDER_FOCUS = "#E1306C"

    TEXT_PRIMARY = "#F8FAFC"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTED = "#64748B"
    TEXT_ACCENT = "#E1306C"
    ACCENT_HOVER = "#F72585"

    CONSOLE_BG = "#0B0F19"
    CONSOLE_BORDER = "#1E293B"

    # Compatibility aliases for DesignTokens
    BG_DARK = BG_WINDOW


class LightThemeTokens(ThemeTokens):
    """Light theme palette (Crisp Slate & Off-White)."""
    NAME = "light"
    BG_WINDOW = "#F1F5F9"
    SURFACE_BASE = "#FFFFFF"
    SURFACE_DARK = "#FFFFFF"
    SURFACE_CARD = "#F8FAFC"
    SURFACE_HOVER = "#E2E8F0"
    SURFACE_INPUT = "#FFFFFF"

    BORDER_COLOR = "#CBD5E1"
    BORDER_DEFAULT = "#CBD5E1"
    BORDER_FOCUS = "#E1306C"

    TEXT_PRIMARY = "#0F172A"
    TEXT_SECONDARY = "#475569"
    TEXT_MUTED = "#64748B"
    TEXT_ACCENT = "#D81B60"
    ACCENT_HOVER = "#BE185D"

    CONSOLE_BG = "#FFFFFF"
    CONSOLE_BORDER = "#CBD5E1"

    # Compatibility aliases for DesignTokens
    BG_DARK = BG_WINDOW


# Backward-compatible alias for existing imports
DesignTokens = DarkThemeTokens


def build_stylesheet(tokens: Type[ThemeTokens] = DarkThemeTokens) -> str:
    """Builds a comprehensive QSS stylesheet for the given theme tokens."""
    is_dark = getattr(tokens, "NAME", "dark") == "dark"
    table_alt_bg = tokens.SURFACE_CARD if is_dark else "#F8FAFC"
    btn_sec_pressed = "#1E293B" if is_dark else "#E2E8F0"
    input_focus_bg = "#111827" if is_dark else "#FFFFFF"
    header_section_bg = tokens.SURFACE_CARD if is_dark else "#E2E8F0"

    return f"""
QMainWindow {{
    background-color: {tokens.BG_WINDOW};
    color: {tokens.TEXT_PRIMARY};
}}

QWidget {{
    background-color: transparent;
    color: {tokens.TEXT_PRIMARY};
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}}

/* Main Tabs Navigation */
QTabWidget::pane {{
    border: 1px solid {tokens.BORDER_COLOR};
    border-radius: 12px;
    background-color: {tokens.SURFACE_DARK};
    top: -1px;
}}

QTabBar::tab {{
    background: {tokens.BG_WINDOW};
    color: {tokens.TEXT_SECONDARY};
    padding: 10px 22px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
    font-size: 13px;
}}

QTabBar::tab:selected {{
    background: {tokens.SURFACE_DARK};
    color: {tokens.TEXT_PRIMARY};
    border-bottom: 2px solid {tokens.IG_PINK};
}}

QTabBar::tab:hover:!selected {{
    background: {tokens.SURFACE_CARD};
    color: {tokens.TEXT_PRIMARY};
}}

/* Cards & Frames */
QFrame#cardFrame {{
    background-color: {tokens.SURFACE_DARK};
    border: 1px solid {tokens.BORDER_COLOR};
    border-radius: 12px;
    padding: 16px;
}}

QFrame#previewCard {{
    background-color: {tokens.SURFACE_INPUT};
    border: 1px solid {tokens.BORDER_COLOR};
    border-radius: 10px;
}}

QFrame#logPanelFrame {{
    background-color: {tokens.SURFACE_DARK};
    border-top: 1px solid {tokens.BORDER_COLOR};
}}

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {tokens.SURFACE_INPUT};
    border: 1px solid {tokens.BORDER_COLOR};
    border-radius: 8px;
    padding: 8px 12px;
    color: {tokens.TEXT_PRIMARY};
    selection-background-color: {tokens.IG_PINK};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {tokens.IG_PINK};
    background-color: {input_focus_bg};
}}

/* Dropdowns / ComboBoxes */
QComboBox {{
    background-color: {tokens.SURFACE_INPUT};
    border: 1px solid {tokens.BORDER_COLOR};
    border-radius: 8px;
    padding: 6px 12px;
    color: {tokens.TEXT_PRIMARY};
    min-width: 130px;
}}

QComboBox:hover {{
    border-color: {tokens.IG_PINK};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {tokens.SURFACE_CARD};
    border: 1px solid {tokens.BORDER_COLOR};
    selection-background-color: {tokens.IG_PINK};
    color: {tokens.TEXT_PRIMARY};
    border-radius: 6px;
    padding: 4px;
}}

/* Spinboxes */
QSpinBox {{
    background-color: {tokens.SURFACE_INPUT};
    border: 1px solid {tokens.BORDER_COLOR};
    border-radius: 8px;
    padding: 6px 10px;
    color: {tokens.TEXT_PRIMARY};
}}

/* Radio Buttons & Checkboxes */
QRadioButton, QCheckBox {{
    color: {tokens.TEXT_PRIMARY};
    spacing: 8px;
    font-weight: 500;
}}

QRadioButton::indicator, QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {tokens.BORDER_COLOR};
    background: {tokens.SURFACE_INPUT};
}}

QRadioButton::indicator {{
    border-radius: 9px;
}}

QCheckBox::indicator {{
    border-radius: 4px;
}}

QRadioButton::indicator:hover, QCheckBox::indicator:hover {{
    border-color: {tokens.IG_PINK};
}}

QRadioButton::indicator:checked {{
    background-color: {tokens.IG_PINK};
    border: 3px solid {tokens.SURFACE_DARK};
}}

QCheckBox::indicator:checked {{
    background-color: {tokens.IG_PINK};
    border-color: {tokens.IG_PINK};
}}

/* Primary Gradient Action Button */
QPushButton#primaryButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {tokens.IG_PURPLE}, stop:0.5 {tokens.IG_PINK}, stop:1 {tokens.IG_ORANGE});
    color: #FFFFFF;
    font-weight: 700;
    font-size: 13px;
    border-radius: 8px;
    padding: 9px 20px;
    border: none;
}}

QPushButton#primaryButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9D4EDD, stop:0.5 #F72585, stop:1 #FF5A5F);
}}

QPushButton#primaryButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6B21A8, stop:0.5 #BE185D, stop:1 #DC2626);
}}

QPushButton#primaryButton:disabled {{
    background: #475569;
    color: #94A3B8;
}}

/* Secondary Neutral Button */
QPushButton#secondaryButton {{
    background-color: {tokens.SURFACE_CARD};
    color: {tokens.TEXT_PRIMARY};
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 16px;
    border: 1px solid {tokens.BORDER_COLOR};
}}

QPushButton#secondaryButton:hover {{
    background-color: {tokens.SURFACE_HOVER};
    border-color: {tokens.IG_PINK};
}}

QPushButton#secondaryButton:pressed {{
    background-color: {btn_sec_pressed};
}}

/* Danger Button */
QPushButton#dangerButton {{
    background-color: rgba(239, 68, 68, 0.15);
    color: #EF4444;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 16px;
    border: 1px solid rgba(239, 68, 68, 0.4);
}}

QPushButton#dangerButton:hover {{
    background-color: rgba(239, 68, 68, 0.25);
    border-color: #EF4444;
}}

/* Progress Bar */
QProgressBar {{
    background-color: {tokens.SURFACE_INPUT};
    border: 1px solid {tokens.BORDER_COLOR};
    border-radius: 6px;
    text-align: center;
    color: {tokens.TEXT_PRIMARY};
    font-weight: bold;
    height: 18px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {tokens.IG_PURPLE}, stop:1 {tokens.IG_PINK});
    border-radius: 5px;
}}

/* Tables */
QTableWidget {{
    background-color: {tokens.SURFACE_INPUT};
    border: 1px solid {tokens.BORDER_COLOR};
    border-radius: 8px;
    gridline-color: {tokens.BORDER_COLOR};
    color: {tokens.TEXT_PRIMARY};
    selection-background-color: rgba(225, 48, 108, 0.25);
    selection-color: {tokens.TEXT_PRIMARY};
    alternate-background-color: {table_alt_bg};
}}

QHeaderView::section {{
    background-color: {header_section_bg};
    color: {tokens.TEXT_SECONDARY};
    font-weight: 600;
    padding: 8px;
    border: none;
    border-bottom: 1px solid {tokens.BORDER_COLOR};
}}

/* Monospace Log Viewer */
QPlainTextEdit#logView {{
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    background-color: {tokens.CONSOLE_BG};
    color: {tokens.TEXT_PRIMARY};
    border: 1px solid {tokens.CONSOLE_BORDER};
    border-radius: 6px;
    padding: 6px 8px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {tokens.BG_WINDOW};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {tokens.BORDER_COLOR};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {tokens.IG_PINK};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {tokens.BG_WINDOW};
    height: 8px;
    margin: 0;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {tokens.BORDER_COLOR};
    min-width: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {tokens.IG_PINK};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* Status Bar */
QStatusBar {{
    background-color: {tokens.BG_WINDOW};
    border-top: 1px solid {tokens.BORDER_COLOR};
    color: {tokens.TEXT_MUTED};
    font-size: 11px;
}}

/* Tooltips */
QToolTip {{
    background-color: {tokens.SURFACE_CARD};
    color: {tokens.TEXT_PRIMARY};
    border: 1px solid {tokens.BORDER_COLOR};
    border-radius: 6px;
    padding: 4px 8px;
}}
"""


DARK_STYLESHEET = build_stylesheet(DarkThemeTokens)
LIGHT_STYLESHEET = build_stylesheet(LightThemeTokens)
MAIN_STYLESHEET = DARK_STYLESHEET


def get_stylesheet(dark: bool = True) -> str:
    """Returns the QSS stylesheet for the requested theme."""
    return DARK_STYLESHEET if dark else LIGHT_STYLESHEET
