"""Dark Windows workspace shared with the companion desktop applications."""
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

CANVAS = "#171719"
SIDEBAR = "#1d1d1f"
SURFACE = "#242426"
ELEVATED = "#303034"
BORDER = "#3a3a3f"
INK = "#f5f5f7"
SECONDARY = "#b6b6be"
MUTED = "#9999a5"
ACCENT = "#087beb"
ACCENT_TEXT = "#93c5ff"
SECONDARY_BLUE = "#62aaff"
SELECTION = "#193856"
UI_FONT = "Segoe UI"
MONO_FONT = "Consolas"
FONT_ROOT = Path(__file__).resolve().parents[1] / "assets" / "fonts"


def load_fonts(app):
    """Use Windows fonts and keep the bundled fonts available as fallbacks."""
    if app.property("controller_lab_fonts_loaded"):
        return
    for name in ("PlusJakartaSans-Variable.ttf", "JetBrainsMono-Variable.ttf"):
        if QFontDatabase.addApplicationFont(str(FONT_ROOT / name)) < 0:
            raise OSError("The bundled interface font could not be loaded: " + name)
    app.setFont(QFont(UI_FONT, 10))
    app.setProperty("controller_lab_fonts_loaded", True)


STYLE = """
QWidget { color: #f5f5f7; font-family: 'Segoe UI', 'Plus Jakarta Sans'; font-size: 13px; }
QMainWindow, QDialog, QMessageBox { background: #171719; }
QDialog#EmbeddedPage { background: transparent; }
QWidget#Root { background: #171719; }
QWidget#Sidebar { background: #1d1d1f; border-right: 1px solid #3a3a3f; }
QFrame#AppHeader { background: #242426; border-bottom: 1px solid #3a3a3f; }
QPushButton#HeaderAction:checked { background: #193856; color: #93c5ff; }
QFrame#Card { background: #242426; border: 1px solid #3a3a3f; border-radius: 16px; }
QWidget#FormBody { background: #242426; }
QLabel { background: transparent; border: none; }
QLabel#Brand { font-size: 22px; font-weight: 600; }
QLabel#WelcomeTitle { font-size: 27px; font-weight: 600; }
QLabel#DashboardValue { font-size: 29px; font-weight: 700; letter-spacing: -0.7px; color: #93c5ff; }
QToolButton#ControllerMenu { color: #93c5ff; background: #193856; border: 1px solid #36516b; border-radius: 9px; padding: 0; font-size: 16px; }
QToolButton#ControllerMenu:hover { color: white; background: #25486a; }
QToolButton#ControllerMenu::menu-indicator { image: none; width: 0; height: 0; }
QLabel#Title, QLabel#LibraryTitle { font-size: 25px; font-weight: 600; }
QLabel#HeroTitle { font-size: 22px; font-weight: 700; }
QLabel#SectionTitle { font-size: 16px; font-weight: 600; }
QLabel#Activity { font-size: 12px; font-weight: 600; }
QLabel#Value { font-family: 'Consolas', 'JetBrains Mono'; font-size: 30px; color: #93c5ff; }
QLabel#Value[side="right"] { color: #93c5ff; }
QLabel#HeroValue { font-size: 14px; font-weight: 600; color: #f5f5f7; }
QLabel#Muted { color: #b6b6be; font-size: 12px; }
QLabel#Small, QLabel#HeaderStatus, QLabel#Breadcrumb { color: #acacb7; font-size: 11px; }
QLabel#Eyebrow { color: #acacb7; font-size: 11px; font-weight: 600; }
QLabel#Count { color: #93c5ff; background: #193856; border: 1px solid #3a3a3f; border-radius: 8px; padding: 3px 8px; font-family: 'Consolas', 'JetBrains Mono'; font-size: 10px; }
QLabel#Avatar { background: #193856; border: 1px solid #36516b; border-radius: 9px; }
QFrame#Rule { background: #3a3a3f; border: none; max-height: 1px; }
QPushButton, QToolButton#Settings, QToolButton#ActionMenu { background: #303034; border: 1px solid #3a3a3f; border-radius: 10px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover, QToolButton#Settings:hover, QToolButton#ActionMenu:hover { background: #353538; border-color: #55555d; }
QPushButton:pressed, QToolButton#Settings:pressed, QToolButton#ActionMenu:pressed { background: #303034; }
QPushButton:focus, QToolButton#Settings:focus, QToolButton#ActionMenu:focus { border-color: #93c5ff; }
QPushButton:disabled, QToolButton:disabled { color: #767682; background: #28282c; border-color: #28282c; }
QPushButton#Primary { background: #087beb; color: #ffffff; border-color: #087beb; }
QPushButton#Primary:hover { background: #1989f8; border-color: #1989f8; }
QPushButton#Primary:pressed { background: #0869c9; }
QPushButton#Primary:disabled { background: #28282c; color: #767682; border-color: #28282c; }
QPushButton#Nav { background: #242426; border: 1px solid transparent; padding: 7px 16px; color: #b6b6be; border-radius: 9px; font-size: 11px; }
QPushButton#Nav:hover { background: #353538; color: #f5f5f7; }
QPushButton#Nav:checked { background: #193856; border-color: #193856; color: #93c5ff; }
QPushButton#Nav:focus { border-color: #93c5ff; }
QPushButton#DrawerToggle:checked { background: #193856; border-color: #087beb; color: #93c5ff; }
QPushButton#SidebarLink { text-align: left; background: transparent; border-color: transparent; color: #b6b6be; }
QPushButton#SidebarLink:hover { background: #353538; color: #f5f5f7; }
QPushButton#WorkspaceNav { text-align: left; background: transparent; border: 1px solid transparent; border-radius: 9px; padding: 10px 12px; color: #b6b6be; }
QPushButton#WorkspaceNav:hover { background: #303034; color: #f5f5f7; }
QPushButton#WorkspaceNav:checked { background: #193856; color: #93c5ff; }
QPushButton#WorkspaceNav:focus { border-color: #93c5ff; }
QPushButton#Disclosure { text-align: left; color: #93c5ff; background: transparent; padding: 10px 0; border: none; }
QPushButton#Disclosure:hover { color: #c4e0ff; }
QPushButton#StopAction { color: #ffb4af; background: #382527; border-color: #794749; }
QPushButton#StopAction:hover { background: #492b2e; border-color: #ff9991; }
QToolButton#ProfileAdd { color: #93c5ff; background: #193856; border: 1px solid #36516b; border-radius: 7px; font-size: 15px; font-weight: 600; padding: 0; }
QToolButton#ProfileAdd:hover { color: white; background: #087beb; }
QToolButton#ProfileAdd:focus { border-color: #93c5ff; }
QToolButton#ProfileAdd:disabled { color: #767682; background: #28282c; border-color: #28282c; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: #242426; color: #b6b6be; padding: 9px 18px; margin: 3px 5px 9px 0; border: 1px solid #3a3a3f; border-radius: 9px; }
QTabBar::tab:selected { color: #93c5ff; background: #193856; border-color: #36516b; }
QTabBar::tab:hover { background: #353538; }
QToolButton::menu-indicator { image: none; width: 0; height: 0; }
QComboBox { background: #303034; border: 1px solid #3a3a3f; border-radius: 12px; padding: 8px 25px 8px 11px; }
QComboBox:hover { border-color: #55555d; }
QLineEdit, QSpinBox, QDoubleSpinBox, QKeySequenceEdit { background: #303034; border: 1px solid #3a3a3f; border-radius: 12px; padding: 8px 10px; selection-background-color: #087beb; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QKeySequenceEdit:focus { border-color: #93c5ff; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { color: #f5f5f7; background: #303034; selection-background-color: #193856; selection-color: #f5f5f7; padding: 5px; border: 1px solid #3a3a3f; border-radius: 8px; outline: 0; }
QListWidget { background: transparent; border: none; outline: 0; }
QListWidget::item { color: #b6b6be; padding: 10px 8px; margin: 2px 0; border-radius: 12px; }
QListWidget::item:selected { background: #193856; color: #93c5ff; }
QListWidget::item:hover { background: #303034; }
QListWidget#Devices::item { padding: 0; margin: 0; background: transparent; }
QProgressBar { border: none; background: #3a3a3f; border-radius: 3px; min-height: 5px; max-height: 5px; }
QProgressBar::chunk { background: #087beb; border-radius: 3px; }
QProgressBar[side="right"]::chunk { background: #62aaff; }
QSlider::groove:horizontal { background: #3a3a3f; height: 5px; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #087beb; border-radius: 2px; }
QSlider::handle:horizontal { background: #e0edff; border: 2px solid #087beb; width: 12px; margin: -6px 0; border-radius: 8px; }
QTextEdit { color: #f5f5f7; background: #1d1d1f; border: 1px solid #3a3a3f; border-radius: 10px; padding: 12px; font-family: 'Consolas', 'JetBrains Mono'; font-size: 11px; }
QTextBrowser#HelpPane { background: transparent; border: none; padding: 0; color: #b6b6be; font-family: 'Segoe UI', 'Plus Jakarta Sans'; font-size: 12px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 6px 0; }
QScrollBar::handle:vertical { background: #55555d; min-height: 30px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: #767682; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QMenu { color: #f5f5f7; background: #242426; border: 1px solid #3a3a3f; border-radius: 10px; padding: 7px; }
QMenu::item { padding: 9px 28px 9px 12px; border-radius: 8px; }
QMenu::item:selected { color: #93c5ff; background: #193856; }
QMenu::item:disabled { color: #767682; }
QMenu::separator { height: 1px; background: #3a3a3f; margin: 6px; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px; background: #303034; border: 1px solid #767682; }
QCheckBox::indicator:checked { background: #087beb; border-color: #93c5ff; image: url("__UI_ICONS__/check.svg"); }
QCheckBox::indicator:focus, QCheckBox::indicator:hover { border-color: #93c5ff; }
QCheckBox::indicator:disabled { background: #28282c; border-color: #3a3a3f; }
QToolTip { color: #f5f5f7; background: #28282c; border: 1px solid #36516b; padding: 8px; }
QWidget#DiagnosticNavigation { background: transparent; }
QLabel#StatusLine { color: #9999a5; font-size: 10px; padding: 3px 4px; }
QLabel#MetricValue { color: #93c5ff; font-family: 'Consolas', 'JetBrains Mono'; font-size: 23px; font-weight: 600; }
QLabel#MetricValue[side="right"] { color: #93c5ff; }
QFrame#Readout { background: #242426; border: 1px solid #3a3a3f; border-radius: 10px; }
QLabel#StatusChip { color: #b6b6be; background: #303034; border: 1px solid #3a3a3f; border-radius: 9px; padding: 7px 11px; font-size: 10px; font-weight: 600; }
QLabel#StatusChip[tone="ready"] { color: #86e8c3; background: #142b28; border-color: #285149; }
QLabel#StatusChip[tone="demo"] { color: #e8cf98; background: #2b251d; border-color: #53452c; }
QLabel#StatusChip[tone="error"] { color: #ffb4af; background: #382527; border-color: #794749; }
QLabel#StatusChip[variant="output"] { font-size: 13px; padding: 11px; }
QToolButton#Settings, QToolButton#ActionMenu { padding-right: 28px; }
QToolButton#Settings::menu-indicator, QToolButton#ActionMenu::menu-indicator { image: url("__UI_ICONS__/chevron-down.svg"); width: 11px; height: 11px; subcontrol-position: right center; subcontrol-origin: padding; right: 9px; }
QComboBox::down-arrow { image: url("__UI_ICONS__/chevron-down.svg"); width: 12px; height: 12px; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url("__UI_ICONS__/chevron-up.svg"); width: 9px; height: 9px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url("__UI_ICONS__/chevron-down.svg"); width: 9px; height: 9px; }
QSpinBox::up-button, QDoubleSpinBox::up-button { width: 21px; border-left: 1px solid #3a3a3f; border-top-right-radius: 9px; }
QSpinBox::down-button, QDoubleSpinBox::down-button { width: 21px; border-left: 1px solid #3a3a3f; border-bottom-right-radius: 9px; }
"""
STYLE = STYLE.replace("__UI_ICONS__", (Path(__file__).resolve().parents[1] / "assets" / "ui").as_posix())
