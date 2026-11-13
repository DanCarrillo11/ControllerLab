"""Compact English desktop workspace for live controller diagnostics."""
from collections import deque
from datetime import datetime
import json
import math
from pathlib import Path
import time

from PySide6.QtCore import Qt, QTimer, QSize, QEvent
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QPushButton, QToolButton, QMenu, QComboBox,
    QListWidget, QListWidgetItem, QStackedWidget, QButtonGroup, QProgressBar,
    QSlider, QTextEdit, QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QScrollArea)

from . import VERSION
from .backend import SDLBackend, DemoBackend
from .mapping import MappingDialog
from .model import FAMILIES, Device, Sample, Session, StickStats, apply_mapping, button_names, rest_summary, deadzone
from .storage import Store, atomic_write, report_csv, report_text
from .visuals import ControllerView, StickPlot, Trace

from .design import STYLE, apply_palette, DeviceDelegate, ElidedLabel, ui_icon
from .widgets import label, button, card, StateBadge
from .features import Workbench
from .emulation import Emulation
from .desktop import DesktopIntegration
from .workspace import WorkspaceUX
from .controller_art import controller_icon
from .theme import ACCENT_TEXT, SECONDARY_BLUE
from .motion import AnimatedStack, AnimatedProgress
from .dashboard import LiveSticks



def app_icon(size=64):
    path = Path(__file__).resolve().parents[1] / "assets" / "app.png"
    icon = QIcon(str(path))
    if icon.isNull() or icon.pixmap(size, size).isNull():
        raise OSError("The application icon is missing or unreadable: " + str(path))
    return icon


class Window(WorkspaceUX, DesktopIntegration, Workbench, QMainWindow):
    def __init__(self, backend, data_dir, demo=False):
        super().__init__()
        self.backend, self.demo, self.store = backend, demo, Store(data_dir)
        self.emulation, self.guided = Emulation(), None
        self.vibration_evidence, self.feedback_owned = None, False
        self.own_outputs, self.emulation_baseline = set(), set()
        self.devices, self.device, self.sample = [], None, Sample(connected=False)
        self.mapping, self.overlay_override, self.family = {}, "auto", "dualsense"
        self.session, self.rest_start, self.rest_points = None, None, {"left": [], "right": []}
        self.recording_profile = None
        self.rest_results = {}
        self.left_stats, self.right_stats = StickStats(), StickStats()
        self.previous_buttons, self.last_event = {}, "Press any button to begin"
        self.left_trigger_range, self.right_trigger_range = [1, 0], [1, 0]
        self.last_draw, self.poll_times = 0, deque(maxlen=120)
        self.setWindowTitle(f"Controller Lab · {VERSION}" + (" · DEMO" if demo else ""))
        self.setWindowIcon(app_icon())
        self.resize(1280, 840)
        self.setMinimumSize(1080, 730)
        apply_palette(QApplication.instance())
        self.setStyleSheet(STYLE)
        self.build()
        self.select_device(-1)
        self.refresh_devices()
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.refresh_devices)
        self.scan_timer.start(1000)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(8)
        self.init_desktop()
        if self.store.warning:
            self.notice(self.store.warning)

    def build(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        app_header = QFrame()
        app_header.setObjectName("AppHeader")
        app_header.setFixedHeight(76)
        toolbar = QHBoxLayout(app_header)
        toolbar.setContentsMargins(24, 12, 24, 12)
        toolbar.setSpacing(12)
        mark = label()
        mark.setFixedSize(40, 40)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setPixmap(app_icon().pixmap(34, 34))
        toolbar.addWidget(mark)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(label("Controller Lab", "Brand"))
        brand.addWidget(label("Controller testing and emulation", "Muted"))
        toolbar.addLayout(brand)
        toolbar.addStretch()
        self.badge = StateBadge("DEMO · Simulated input" if self.demo else "Waiting for a controller")
        toolbar.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)
        shell.addWidget(app_header)

        body = QWidget()
        outer = QHBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        shell.addWidget(body, 1)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(230)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(18, 20, 18, 16)
        left.setSpacing(8)
        left.addWidget(label("Workspace", "Eyebrow"))
        devices = QHBoxLayout()
        devices.addWidget(label("Controllers", "LibraryTitle"))
        devices.addStretch()
        self.device_count = label("0", "Count")
        devices.addWidget(self.device_count)
        left.addLayout(devices)
        self.device_list = QListWidget()
        self.device_list.setObjectName("Devices")
        self.device_list.setFixedHeight(140)
        self.device_list.setAccessibleName("Connected controllers")
        self.device_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.device_list.setItemDelegate(DeviceDelegate(controller_icon, self.device_list))
        self.device_list.currentRowChanged.connect(self.select_device)
        left.addWidget(self.device_list)
        divider = QFrame()
        divider.setObjectName("Rule")
        divider.setFixedHeight(1)
        left.addWidget(divider)
        left.addSpacing(6)
        left.addWidget(label("Test & play", "Eyebrow"))
        self.nav_group = QButtonGroup(self)
        self.primary_buttons = {}
        self.last_diagnostic_page = 0
        for index, title in ((0, "Device lab"), (5, "Guided test"), (6, "Emulation")):
            self.add_primary_navigation(left, index, title)
        left.addSpacing(14)
        left.addWidget(label("Your workspace", "Eyebrow"))
        self.sessions_link = self.add_primary_navigation(left, 4, "Saved sessions")
        self.add_primary_navigation(left, 8, "Game profiles")
        left.addStretch()
        left.addWidget(label(f"{VERSION} · Windows", "Small"))
        outer.addWidget(sidebar)

        self.settings_button = self.add_primary_navigation(toolbar, 7, "Settings")
        self.settings_button.setObjectName("HeaderAction")
        more = QToolButton()
        more.setObjectName("Settings")
        more.setText("Help")
        more.setAccessibleName("Help and application actions")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        help_menu = QMenu(more)
        help_menu.addAction("Setup assistant…", self.open_setup)
        help_menu.addAction("Help and troubleshooting…", self.show_help)
        help_menu.addAction("About Controller Lab…", self.about)
        help_menu.addSeparator()
        self.minimize_tray_action = help_menu.addAction("Minimize to tray", self.minimize_to_tray)
        help_menu.addAction("Quit Controller Lab", self.request_quit)
        more.setMenu(help_menu)
        toolbar.addWidget(more)

        right = QVBoxLayout()
        right.setContentsMargins(24, 18, 24, 12)
        right.setSpacing(12)
        page_header = QHBoxLayout()
        page_header.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        self.breadcrumb = label("Device lab", "Title")
        titles.addWidget(self.breadcrumb)
        self.page_description = label("Check buttons, sticks and triggers in real time.", "Muted", True)
        titles.addWidget(self.page_description)
        page_header.addLayout(titles, 1)
        self.record_button = button("Record session", self.toggle_recording, True)
        self.record_button.setIcon(ui_icon("record", "#ffffff"))
        page_header.addWidget(self.record_button)
        self.global_stop = button("Stop emulation", self.emergency_stop)
        self.global_stop.setObjectName("StopAction")
        self.global_stop.hide()
        page_header.addWidget(self.global_stop)
        right.addLayout(page_header)

        self.controller_options = QToolButton()
        self.controller_options.setText("•••")
        self.controller_options.setObjectName("ControllerMenu")
        self.controller_options.setFixedSize(34, 30)
        self.controller_options.setAccessibleName("Controller options")
        self.controller_options.setToolTip("Controller options: profiles, mapping and appearance")
        self.controller_options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.controller_options)
        self.profiles_action = menu.addAction("Manage profiles…", self.open_profiles)
        self.mapping_action = menu.addAction("Map inputs…", self.map_inputs)
        menu.addSeparator()
        overlays = menu.addMenu("Controller overlay")
        self.overlay_menu = overlays
        self.overlay_group = QActionGroup(self)
        for key, name in (("auto", "Detect automatically"), *FAMILIES.items()):
            action = QAction(name, self, checkable=True)
            action.setData(key)
            self.overlay_group.addAction(action)
            overlays.addAction(action)
        self.overlay_group.triggered.connect(self.set_overlay)
        self.details_action = menu.addAction("Device details…", self.device_details)
        menu.addAction("Compatibility and diagnostics…", self.show_compatibility)
        self.controller_options.setMenu(menu)

        self.workspace = AnimatedStack()
        empty = QWidget()
        e = QVBoxLayout(empty)
        e.setContentsMargins(0, 0, 0, 0)
        e.addStretch()
        welcome, w = card()
        w.setContentsMargins(36, 32, 36, 32)
        w.setSpacing(16)
        empty_mark = label()
        empty_mark.setFixedSize(66, 66)
        empty_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_mark.setPixmap(app_icon().pixmap(42, 42))
        w.addWidget(empty_mark, alignment=Qt.AlignmentFlag.AlignLeft)
        w.addWidget(label("Connect a controller", "WelcomeTitle"))
        w.addWidget(label("Connect via USB or pair your controller in Windows to see its live inputs.", "Muted", True))
        row = QHBoxLayout()
        row.addWidget(button("Set up your controller", self.open_setup, True))
        row.addWidget(button("View saved sessions", lambda: self.navigate(4)))
        row.addStretch()
        w.addLayout(row)
        e.addWidget(welcome)
        e.addStretch()
        self.workspace.addWidget(empty)

        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(12)
        self.controller_hero = QFrame()
        self.controller_hero.setObjectName("Card")
        hero_row = QHBoxLayout(self.controller_hero)
        hero_row.setContentsMargins(16, 12, 16, 12)
        hero_row.setSpacing(16)
        device_row = QHBoxLayout()
        device_row.setSpacing(12)
        self.controller_avatar = label("", "Avatar")
        self.controller_avatar.setFixedSize(58, 48)
        self.controller_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        device_row.addWidget(self.controller_avatar)
        copy = QVBoxLayout()
        copy.setSpacing(4)
        copy.addWidget(label("Connected controller", "Eyebrow"))
        self.controller_title = ElidedLabel("No controller connected", "SectionTitle")
        self.controller_title.setMinimumHeight(20)
        self.side_mapping = ElidedLabel("", "Small")
        self.side_mapping.setMinimumHeight(16)
        copy.addWidget(self.controller_title)
        copy.addWidget(self.side_mapping)
        device_row.addLayout(copy, 1)
        device_row.addWidget(self.controller_options)
        hero_row.addLayout(device_row, 1)
        profile_card = QWidget()
        profile_card.setFixedWidth(184)
        profile = QVBoxLayout(profile_card)
        profile.setContentsMargins(0, 0, 0, 0)
        profile.setSpacing(5)
        profile_heading = QHBoxLayout()
        profile_heading.addWidget(label("Active profile", "Eyebrow"))
        profile_heading.addStretch()
        self.profile_add = QToolButton()
        self.profile_add.setText("+")
        self.profile_add.setObjectName("ProfileAdd")
        self.profile_add.setFixedSize(22, 20)
        self.profile_add.setAccessibleName("Create a new controller profile")
        self.profile_add.setToolTip("New profile: copy the current configuration with a new name")
        self.profile_add.clicked.connect(self.new_controller_profile)
        profile_heading.addWidget(self.profile_add)
        profile.addLayout(profile_heading)
        self.profile_picker = QComboBox()
        self.profile_picker.setAccessibleName("Active controller profile")
        self.profile_picker.setMinimumWidth(0)
        self.profile_picker.currentIndexChanged.connect(self.quick_profile_change)
        profile.addWidget(self.profile_picker)
        hero_row.addWidget(profile_card)
        battery = QWidget()
        battery.setFixedWidth(120)
        power = QVBoxLayout(battery)
        power.setContentsMargins(8, 0, 0, 0)
        power.setSpacing(5)
        power.addWidget(label("Power", "Eyebrow"))
        self.power_label = label("—", "HeroValue", True)
        self.power_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.power_label.setToolTip("Power / battery, when reported by the controller")
        power.addWidget(self.power_label)
        hero_row.addWidget(battery)
        self.side_family = label()
        self.input_label = label()
        self.mapping_note = label()
        for hidden in (self.side_family, self.input_label, self.mapping_note):
            hidden.hide()
        main.addWidget(self.controller_hero)
        self.diagnostic_navigation = QWidget()
        self.diagnostic_navigation.setObjectName("DiagnosticNavigation")
        nav = QHBoxLayout(self.diagnostic_navigation)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(6)
        for i, text in enumerate(("Overview", "Sticks", "Triggers", "Raw inputs")):
            b = button(text)
            b.setObjectName("Nav")
            b.setCheckable(True)
            self.nav_group.addButton(b, i)
            nav.addWidget(b)
        self.nav_group.idClicked.connect(self.navigate)
        self.nav_group.button(0).setChecked(True)
        main.addWidget(self.diagnostic_navigation, 0, Qt.AlignmentFlag.AlignLeft)
        self.pages = AnimatedStack()
        self.build_live()
        self.build_sticks()
        self.build_triggers()
        self.build_raw()
        self.build_sessions()
        self.build_guided_page()
        self.build_emulation_page()
        self.settings_page, self.games_page = QWidget(), QWidget()
        self.pages.addWidget(self.settings_page)
        self.pages.addWidget(self.games_page)
        main.addWidget(self.pages, 1)
        self.status = label("Ready", "StatusLine", True)
        self.status.setMinimumHeight(20)
        main.addWidget(self.status)
        self.workspace.addWidget(content)
        right.addWidget(self.workspace, 1)
        outer.addLayout(right, 1)

    def build_live(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        diagram, d = card()
        top = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(4)
        self.diagram_title = label("Live input", "SectionTitle")
        self.diagram_hint = ElidedLabel("Buttons light up as you press them.", "Muted")
        self.diagram_hint.setMinimumHeight(18)
        title.addWidget(self.diagram_title)
        title.addWidget(self.diagram_hint)
        top.addLayout(title, 1)
        self.rumble_toggle = button("Vibration")
        self.rumble_toggle.setObjectName("DrawerToggle")
        self.rumble_toggle.setCheckable(True)
        self.rumble_toggle.setIcon(ui_icon("vibration"))
        self.rumble_toggle.setAccessibleName("Show or hide vibration controls")
        top.addWidget(self.rumble_toggle)
        d.addLayout(top)
        self.view = ControllerView()
        self.view.setMinimumHeight(170)
        d.addWidget(self.view, 1)
        self.event_label = ElidedLabel("Press any button to begin", "Activity")
        self.event_label.setMinimumHeight(20)
        self.active_label = ElidedLabel("No buttons held", "Small")
        self.active_label.setMinimumHeight(18)
        d.addWidget(self.event_label)
        d.addWidget(self.active_label)
        layout.addWidget(diagram, 1)

        self.live_side = AnimatedStack()
        self.live_side.setFixedWidth(228)
        telemetry = QWidget()
        tiles = QVBoxLayout(telemetry)
        tiles.setContentsMargins(0, 0, 0, 0)
        tiles.setSpacing(10)
        activity, activity_body = card()
        activity_body.setContentsMargins(16, 13, 16, 13)
        activity_body.setSpacing(4)
        activity_body.addWidget(label("BUTTON ACTIVITY", "Eyebrow"))
        self.live_button_count = label("—", "DashboardValue")
        activity_body.addWidget(self.live_button_count)
        self.live_activity_hint = label("Waiting for input", "Small")
        activity_body.addWidget(self.live_activity_hint)
        tiles.addWidget(activity, 1)
        triggers, trigger_body = card()
        trigger_body.setContentsMargins(16, 13, 16, 13)
        trigger_body.setSpacing(9)
        trigger_body.addWidget(label("TRIGGER PRESSURE", "Eyebrow"))
        readings = QHBoxLayout()
        readings.setSpacing(12)
        self.live_triggers = {}
        for side in ("left", "right"):
            column = QVBoxLayout()
            column.setSpacing(6)
            column.addWidget(label(side.title(), "Small"))
            value = label("—", "MetricValue")
            value.setProperty("side", side)
            column.addWidget(value)
            progress = AnimatedProgress()
            progress.setProperty("side", side)
            progress.setRange(0, 1000)
            column.addWidget(progress)
            self.live_triggers[side] = (value, progress)
            readings.addLayout(column)
        trigger_body.addLayout(readings)
        tiles.addWidget(triggers, 1)
        sticks, sticks_body = card()
        sticks_body.setContentsMargins(16, 12, 16, 12)
        sticks_body.setSpacing(6)
        sticks_body.addWidget(label("STICK POSITION", "Eyebrow"))
        self.live_sticks = LiveSticks()
        sticks_body.addWidget(self.live_sticks, 1)
        tiles.addWidget(sticks, 1)
        self.live_side.addWidget(telemetry)
        self.rumble_panel, v = card("Vibration")
        self.rumble_strength = QSlider(Qt.Orientation.Horizontal)
        self.rumble_strength.setRange(0, 100)
        self.rumble_strength.setValue(45)
        self.strength_label = label("Strength · 45%", "Muted")
        self.rumble_strength.valueChanged.connect(lambda value: self.strength_label.setText(f"Strength · {value}%"))
        v.addWidget(label("Choose a motor to play a short test.", "Muted", True))
        v.addSpacing(4)
        v.addWidget(self.strength_label)
        v.addWidget(self.rumble_strength)
        self.rumble_buttons = []
        motors = QHBoxLayout()
        motors.setSpacing(5)
        for text, low, high in (("Low", 1, 0), ("High", 0, 1), ("Both", 1, 1)):
            action = button(text, lambda checked=False, l=low, h=high: self.rumble(l, h))
            action.setStyleSheet("padding: 8px 9px;")
            action.setToolTip("Test both motors for 600 ms" if text == "Both" else f"Test the {text.lower()}-frequency motor for 600 ms")
            self.rumble_buttons.append(action)
            motors.addWidget(action)
        v.addLayout(motors)
        v.addWidget(button("Stop vibration", self.stop_rumble))
        v.addStretch()
        v.addWidget(label("Standard rumble · 600 ms per test", "Small", True))
        v.addWidget(label("Advanced haptics and adaptive triggers are not included.", "Small", True))
        self.live_side.addWidget(self.rumble_panel)
        self.rumble_toggle.toggled.connect(lambda checked: self.live_side.setCurrentIndex(1 if checked else 0))
        layout.addWidget(self.live_side)
        self.pages.addWidget(page)

    def build_sticks(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        plots = QHBoxLayout()
        plots.setSpacing(14)
        self.stick_widgets = {}
        for side in ("left", "right"):
            frame, f = card(side.title() + " stick")
            plot = StickPlot()
            plot.setMinimumSize(160, 145)
            value = label("X  +0.000   Y  +0.000", "Activity")
            metric = label("Move the stick to trace its range.", "Small", True)
            f.addWidget(plot, 1)
            f.addWidget(value)
            f.addWidget(metric)
            plots.addWidget(frame, 1)
            self.stick_widgets[side] = (plot, value, metric)
        layout.addLayout(plots, 1)
        tests, t = card()
        row = QHBoxLayout()
        self.rest_button = button("Measure center · 5s", self.start_rest)
        row.addWidget(self.rest_button)
        row.addWidget(button("Reset trace", self.reset_measurements))
        row.addStretch()
        self.deadzone_slider = QSlider(Qt.Orientation.Horizontal)
        self.deadzone_slider.setRange(0, 30)
        self.deadzone_slider.setValue(8)
        self.deadzone_slider.setMaximumWidth(160)
        self.deadzone_slider.setMinimumWidth(80)
        self.deadzone_slider.valueChanged.connect(self.set_deadzone)
        self.deadzone_label = label("Deadzone preview · 8%", "Small")
        row.addWidget(self.deadzone_label)
        row.addWidget(self.deadzone_slider, 1)
        t.addLayout(row)
        self.rest_progress = AnimatedProgress()
        self.rest_progress.setTextVisible(False)
        self.rest_progress.setRange(0, 5000)
        self.rest_progress.hide()
        t.addWidget(self.rest_progress)
        self.rest_label = label("Release both sticks and keep the controller still to measure its center.", "Muted", True)
        t.addWidget(self.rest_label)
        t.addWidget(label("Violet · Raw input     Mint · Deadzone preview     Rotate the outer edge to measure coverage.", "Small", True))
        layout.addWidget(tests)
        self.pages.addWidget(page)

    def build_triggers(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        plots = QHBoxLayout()
        plots.setSpacing(14)
        self.trigger_widgets = {}
        for side in ("left", "right"):
            frame, f = card(side.title() + " trigger")
            value = label("0.0%", "Value")
            range_label = label("Observed range · —", "Small", True)
            f.addWidget(value)
            progress = AnimatedProgress()
            progress.setRange(0, 1000)
            progress.setTextVisible(False)
            progress.setProperty("side", side)
            value.setProperty("side", side)
            trace = Trace(SECONDARY_BLUE if side == "right" else ACCENT_TEXT)
            trace.setMinimumHeight(90)
            f.addWidget(progress)
            f.addWidget(trace, 1)
            f.addWidget(range_label)
            plots.addWidget(frame, 1)
            self.trigger_widgets[side] = (value, range_label, progress, trace)
        layout.addLayout(plots, 1)
        layout.addWidget(label("Press and release each trigger slowly. Traces show recent input observations.", "Small", True))
        self.pages.addWidget(page)

    def build_raw(self):
        frame, f = card("Raw inputs")
        f.addWidget(label("The device's original axis, button and hat indices. Use these values when assigning an unrecognized controller or adapter.", "Muted", True))
        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setAccessibleName("Raw controller inputs")
        f.addWidget(self.raw_text, 1)
        f.addWidget(button("Map inputs…", self.map_inputs))
        self.pages.addWidget(frame)

    def build_sessions(self):
        self.build_sessions_page()

    def notice(self, text):
        self.status.setText(text)

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        self.nav_group.button(index).setChecked(True)
        self.update_navigation(index)
        self.workspace.setCurrentIndex(1 if self.device or index in (4, 6, 7, 8) else 0)

    def refresh_devices(self):
        try:
            devices = self.filter_virtual_outputs(self.backend.refresh())
        except Exception as exc:
            self.notice(f"Could not scan controllers: {exc}")
            return
        if devices == self.devices:
            return
        previous = self.device.instance_id if self.device else None
        self.devices = devices
        self.device_count.setText(str(len(devices)))
        self.device_list.setFixedHeight(max(78, min(166, len(devices) * 68 + 6)))
        self.device_list.blockSignals(True)
        self.device_list.clear()
        for d in devices:
            item = QListWidgetItem(d.name)
            item.setData(Qt.ItemDataRole.UserRole, d)
            item.setToolTip(d.name + "\n" + FAMILIES[d.family])
            item.setSizeHint(QSize(200, 68))
            self.device_list.addItem(item)
        target = next((i for i, d in enumerate(devices) if d.instance_id == previous), 0 if devices else -1)
        self.device_list.setCurrentRow(target)
        self.device_list.blockSignals(False)
        self.select_device(target)

    def select_device(self, index):
        new = self.devices[index] if 0 <= index < len(self.devices) else None
        if self.device and new and self.device.instance_id == new.instance_id:
            return
        self.desktop_device_changing()
        self.stop_emulation()
        self.cancel_guided()
        self.vibration_evidence = None
        if self.session:
            self.finish_recording("Controller changed or disconnected")
        if self.device:
            self.backend.stop(self.device.instance_id)
        self.cancel_rest()
        self.device, self.sample = new, Sample(connected=False)
        self.update_live_summary()
        self.previous_buttons, self.last_event = {}, "Press any button to begin"
        self.reset_measurements()
        self.record_button.setEnabled(new is not None)
        self.rumble_toggle.setEnabled(new is not None)
        self.rumble_toggle.setChecked(False)
        self.mapping_action.setEnabled(new is not None)
        self.details_action.setEnabled(new is not None)
        self.profiles_action.setEnabled(new is not None)
        self.overlay_menu.setEnabled(new is not None)
        self.workspace.setCurrentIndex(1 if new or self.pages.currentIndex() in (4, 6, 7, 8) else 0)
        self.sync_profile_picker()
        self.update_navigation(self.pages.currentIndex())
        if not new:
            self.controller_avatar.clear()
            self.controller_avatar.setToolTip("")
            self.controller_title.setText("No controller connected")
            self.side_family.setText("Saved sessions are available below.")
            self.side_mapping.clear()
            self.input_label.setText("No live inputs")
            self.power_label.setText("—")
            self.mapping_note.setText("No controller connected")
            self.badge.setText("Waiting for a controller")
            self.view.set_input(self.family, None)
            self.update_guided()
            self.sync_emulation_ui()
            return
        preferences = self.store.device(new.guid)
        self.load_emulation_settings(preferences.get("emulation", {}))
        custom = preferences.get("mapping", {})
        self.mapping = custom if isinstance(custom, dict) else {}
        if not all(isinstance(self.mapping.get(key, {}), dict) for key in ("axes", "buttons")):
            self.mapping = {}
        override = preferences.get("overlay", "auto")
        self.overlay_override = override if override in FAMILIES else "auto"
        try:
            dz = max(0, min(30, int(preferences.get("deadzone", 8))))
        except (TypeError, ValueError):
            dz = 8
        self.deadzone_slider.blockSignals(True)
        self.deadzone_slider.setValue(dz)
        self.deadzone_slider.blockSignals(False)
        self.update_deadzone()
        self.apply_identity()
        self.badge.setText("DEMO · Simulated input" if self.demo else "Connected · Live input")
        for b in self.rumble_buttons:
            b.setEnabled(not self.demo)
        self.notice("Ready. All measurements use the original input values.")
        self.tick()

    def apply_identity(self):
        if not self.device:
            return
        self.update_output_route()
        self.controller_avatar.setPixmap(controller_icon(self.device.family).pixmap(48, 36))
        self.controller_avatar.setToolTip(FAMILIES.get(self.device.family, FAMILIES["generic"]))
        self.family = self.device.family if self.overlay_override == "auto" else self.overlay_override
        self.side_family.setText(FAMILIES[self.family])
        mapping = "Custom input assignments" if self.mapping else "Automatic input mapping" if self.device.mapped else "Raw inputs · mapping needed"
        self.side_mapping.setText(mapping)
        self.side_mapping.setToolTip(self.side_mapping.text())
        self.mapping_note.setText("Detected automatically" if self.overlay_override == "auto" else "Manual overlay")
        self.diagram_title.setText("Live input")
        self.diagram_hint.setText("Buttons light up as you press them." if self.device.mapped or self.mapping
                                  else "Raw inputs are available. Use Map inputs to animate this diagram.")
        self.diagram_hint.setToolTip(self.diagram_hint.text())
        for action in self.overlay_group.actions():
            action.setChecked(action.data() == self.overlay_override)
        self.controller_title.setText(self.device.name)
        self.controller_title.setToolTip(self.device.name)
        self.view.set_input(self.family, self.sample)
        self.sync_profile_picker()

    def save_preference(self, **kwargs):
        if self.device:
            try:
                self.store.update(self.device.guid, **kwargs)
            except OSError as exc:
                self.notice(f"Settings could not be saved: {exc}")

    def set_overlay(self, action):
        self.overlay_override = action.data()
        self.save_preference(overlay=self.overlay_override)
        self.apply_identity()
        self.draw_sample()

    def map_inputs(self):
        if not self.device:
            return
        self.stop_emulation()
        self.cancel_guided()
        target_id = self.device.instance_id
        dialog = MappingDialog(self.device, self.family, self.mapping, self,
            lambda: self.sample if self.device and self.device.instance_id == target_id else None)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if not self.device or self.device.instance_id != target_id:
                self.notice("The controller changed. Reopen Map inputs for the current device.")
                return
            if self.session:
                self.finish_recording("Input assignments changed")
            self.cancel_rest()
            self.mapping = dialog.result_mapping or {}
            self.save_preference(mapping=self.mapping)
            self.reset_measurements()
            self.previous_buttons = {}
            self.apply_identity()
            self.notice("Input assignments updated for this app.")

    def tick(self):
        if not self.device:
            return
        try:
            sample = self.backend.poll(self.device.instance_id)
        except Exception as exc:
            self.notice(f"Input could not be read: {exc}")
            sample = None
        if sample is None:
            self.stop_emulation()
            self.cancel_guided()
            if self.session:
                self.finish_recording("Controller disconnected")
            self.cancel_rest()
            self.sample = Sample(connected=False)
            self.update_live_summary()
            self.view.set_input(self.family, None)
            self.record_button.setEnabled(False)
            self.rumble_toggle.setEnabled(False)
            self.rumble_toggle.setChecked(False)
            self.power_label.setText("—")
            self.input_label.setText("No live inputs")
            self.badge.setText("Connection lost · Scanning…")
            self.notice("Controller disconnected. Waiting for it to reconnect.")
            return
        self.sample = apply_mapping(sample, self.mapping)
        sample = self.sample
        self.badge.setText("DEMO · Simulated input" if self.demo else "Connected · Live input")
        self.record_button.setEnabled(self.guided is None)
        self.rumble_toggle.setEnabled(not self.emulation.running)
        self.emu_start.setEnabled(not self.emulation.running and not self.demo and sample.mapped)
        self.update_output(sample)
        if self.guided:
            self.guided.add(sample)
        for key, value in sample.buttons.items():
            if value and not self.previous_buttons.get(key):
                self.last_event = "Last press · " + button_names(self.family).get(key, key)
        if not sample.mapped:
            for i, value in enumerate(sample.raw_buttons):
                if value and not self.previous_buttons.get(f"raw{i}"):
                    self.last_event = f"Last press · Raw button {i}"
        self.previous_buttons = sample.buttons.copy() if sample.mapped else {f"raw{i}": v for i, v in enumerate(sample.raw_buttons)}
        for side, stats in (("left", self.left_stats), ("right", self.right_stats)):
            if side + "x" in sample.axes and side + "y" in sample.axes:
                stats.add(sample.axes[side + "x"], sample.axes[side + "y"])
        for side, ranges in (("left", self.left_trigger_range), ("right", self.right_trigger_range)):
            if side + "trigger" in sample.axes:
                v = sample.axes[side + "trigger"]
                ranges[0], ranges[1] = min(ranges[0], v), max(ranges[1], v)
        if self.rest_start is not None:
            elapsed = sample.time - self.rest_start
            for side in ("left", "right"):
                if side + "x" in sample.axes and side + "y" in sample.axes:
                    self.rest_points[side].append((sample.axes[side + "x"], sample.axes[side + "y"]))
            self.rest_progress.setValue(min(5000, int(elapsed * 1000)))
            if elapsed >= 5:
                self.complete_rest()
        if self.session:
            self.session.add(sample)
            seconds = sample.time - self.session.start
            self.record_button.setText(f"Stop recording · {seconds:.0f}s")
            if seconds >= 120:
                self.finish_recording("Two-minute recording limit reached")
        if sample.time - self.last_draw >= 1 / 30:
            self.last_draw = sample.time
            self.draw_sample()

    def draw_sample(self):
        self.update_guided()
        s = self.sample
        self.view.set_input(self.family, s)
        self.event_label.setText(self.last_event)
        names = button_names(self.family)
        held = [names.get(k, k) for k, v in s.buttons.items() if v]
        if not s.mapped:
            held = [f"Button {i}" for i, v in enumerate(s.raw_buttons) if v]
        self.active_label.setText("Held · " + "  /  ".join(held) if held else "No buttons held")
        self.active_label.setToolTip(self.active_label.text())
        self.update_live_summary()
        self.power_label.setText({"full": "Full", "medium": "Medium", "low": "Low", "empty": "Empty",
                                  "wired": "Wired power"}.get(s.power, "Not reported"))
        self.input_label.setText(f"{len(s.raw_axes)} axes  ·  {len(s.raw_buttons)} buttons\n{len(s.hats)} directional hats")
        for side, stats in (("left", self.left_stats), ("right", self.right_stats)):
            plot, value, metric = self.stick_widgets[side]
            active = side + "x" in s.axes and side + "y" in s.axes
            x, y = s.axes.get(side + "x", 0), s.axes.get(side + "y", 0)
            plot.set_value(x, y, active)
            value.setText(f"X  {x:+.3f}     Y  {y:+.3f}" if active else "Not mapped")
            summary = stats.summary()
            deviation = summary["radial_deviation"]
            metric.setText((f"Circle coverage · {summary['coverage'] * 100:.0f}%\n"
                            + (f"Radial deviation · {deviation * 100:.1f}%" if deviation is not None else "Rotate a full circle to measure deviation."))
                           if active else "Assign both axes in Map inputs to test this stick.")
        for side, observed in (("left", self.left_trigger_range), ("right", self.right_trigger_range)):
            value, range_label, progress, trace = self.trigger_widgets[side]
            v = s.axes.get(side + "trigger")
            value.setText(f"{v * 100:.1f}%" if v is not None else "Not mapped")
            progress.setValue(int((v or 0) * 1000))
            range_label.setText(f"Observed · {observed[0] * 100:.1f}% — {observed[1] * 100:.1f}%" if observed[0] <= observed[1] else "Observed range · —")
            if v is not None:
                trace.values.append(v)
            trace.update()
        if self.pages.currentIndex() == 3:
            text = "AXES\n" + "\n".join(f"  Axis {i:2}     {v:+.5f}" for i, v in enumerate(s.raw_axes))
            text += "\n\nBUTTONS\n" + "  ".join(f"{i:02}:{'ON ' if v else 'off'}" for i, v in enumerate(s.raw_buttons))
            text += "\n\nDIRECTIONAL HATS\n" + ("\n".join(f"  Hat {i}: {v}" for i, v in enumerate(s.hats)) or "  None")
            if text != self.raw_text.toPlainText():
                pos = self.raw_text.verticalScrollBar().value()
                self.raw_text.setPlainText(text)
                self.raw_text.verticalScrollBar().setValue(pos)

    def rumble(self, low, high):
        if self.device and self.sample.connected and not self.demo:
            strength = self.rumble_strength.value() / 100
            ok = self.backend.rumble(self.device.instance_id, low * strength, high * strength, 600)
            self.vibration_evidence = "Command accepted; physical response unverified" if ok else "Command unavailable on this connection"
            self.notice("Playing a 600 ms vibration test." if ok else "Vibration is not available through this controller or connection.")
            return ok
        return False

    def stop_rumble(self):
        if self.device:
            self.backend.stop(self.device.instance_id)
            self.notice("Vibration stopped.")

    def set_deadzone(self, value):
        self.update_deadzone()
        self.save_preference(deadzone=value)

    def update_deadzone(self):
        value = self.deadzone_slider.value()
        self.deadzone_label.setText(f"Deadzone preview · {value}%")
        for plot, _, _ in self.stick_widgets.values():
            plot.radius = value / 100
            plot.update()

    def reset_measurements(self):
        if self.rest_start is not None:
            self.cancel_rest()
        self.left_stats, self.right_stats = StickStats(), StickStats()
        self.left_trigger_range, self.right_trigger_range = [1, 0], [1, 0]
        self.rest_results = {}
        for plot, _, _ in self.stick_widgets.values():
            plot.points.clear()
        for _, _, _, trace in self.trigger_widgets.values():
            trace.values.clear()
        self.rest_label.setText("For a center test, release both sticks and leave the controller still.")

    def start_rest(self):
        if not self.sample.connected or not any(side + "x" in self.sample.axes and side + "y" in self.sample.axes for side in ("left", "right")):
            self.notice("Map both axes of at least one stick before measuring its center.")
            return
        self.rest_start = time.monotonic()
        self.rest_points, self.rest_results = {"left": [], "right": []}, {}
        self.rest_label.setText("Measuring… Keep both sticks released and the controller still.")
        self.rest_progress.setValue(0)
        self.rest_progress.show()
        self.rest_button.setEnabled(False)

    def cancel_rest(self):
        running = self.rest_start is not None
        self.rest_start = None
        self.rest_progress.hide()
        self.rest_button.setEnabled(True)
        if running:
            self.rest_label.setText("Center measurement canceled because the controller or mapping changed.")

    def complete_rest(self):
        self.rest_start = None
        self.rest_progress.hide()
        self.rest_button.setEnabled(True)
        self.rest_results = {side: rest_summary(points) for side, points in self.rest_points.items() if points}
        self.rest_label.setText("\n".join(f"{side.title()} · Mean offset {r['mean_radius'] * 100:.2f}% · Peak {r['max_radius'] * 100:.2f}% · Jitter {r['jitter'] * 100:.2f}%"
                                         for side, r in self.rest_results.items()))
        self.notice("Center measurement complete. Results describe observed input, not a pass/fail hardware diagnosis.")

    def toggle_recording(self):
        if self.session:
            self.finish_recording("Stopped by user")
        elif self.device and self.sample.connected:
            self.session = Session(self.device, self.sample.time)
            self.recording_profile = (self.store.active_profile(self.device.guid), self.store.profile_name(self.device.guid))
            self.record_button.setText("Stop recording · 0s")
            self.update_navigation(self.pages.currentIndex())
            self.notice("Recording for up to two minutes. Test buttons, sticks and triggers, then stop to save.")

    def finish_recording(self, reason):
        session, self.session = self.session, None
        recorded_profile, self.recording_profile = self.recording_profile, None
        self.record_button.setText("Record session")
        self.update_navigation(self.pages.currentIndex())
        if not session or not session.samples:
            self.notice("Recording ended without input samples.")
            return
        report = self.decorate_report(session.report())
        if recorded_profile is not None:
            report.update(profile_id=recorded_profile[0], profile_name=recorded_profile[1])
        report["completion_reason"] = reason
        report["demo"] = self.demo
        report["overlay"] = self.family
        report["mapping_source"] = "Custom app-local assignments" if self.mapping else "SDL automatic mapping" if session.device.mapped else "Raw inputs only"
        report["input_mapping"] = self.mapping or None
        report["rest_measurements"] = self.rest_results.copy()
        try:
            self.store.save_report(report)
            self.refresh_history()
            self.notice("Session saved locally. Open Sessions to view or export it.")
        except OSError as exc:
            self.notice(f"Session could not be saved: {exc}")

    def refresh_history(self):
        self.refresh_sessions()

    def show_report(self, index):
        self.display_session(index)

    def export_report(self, format):
        self.export_session(format)

    def device_details(self):
        if self.device:
            from dataclasses import asdict
            details = asdict(self.device)
            details["active_overlay"] = self.family
            details["power_status"] = self.sample.power
            dialog = QDialog(self)
            dialog.setWindowTitle("Device details")
            dialog.resize(610, 420)
            layout = QVBoxLayout(dialog)
            text = QTextEdit()
            text.setReadOnly(True)
            text.setPlainText(json.dumps(details, indent=2))
            layout.addWidget(text)
            close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close.rejected.connect(dialog.reject)
            layout.addWidget(close)
            dialog.exec()

    def about(self):
        QMessageBox.information(self, "About Controller Lab", f"Controller Lab {VERSION}\n\nLocal gamepad diagnostics for Windows.\nBuilt with Python, PySide6 and SDL2 through pygame-ce.\n\nVector overlays are adapted from DualSense Tester, the VSCView Gamepad Asset Pack and community controller artwork. Credits are in assets/overlays/CREDITS.md.\nWii and GameCube require a device/adapter exposed to Windows; direct pairing and adapter drivers are not included.")

    def closeEvent(self, event):
        if self.should_hide_on_close():
            event.ignore()
            self.minimize_to_tray()
            return
        self.shutdown()
        super().closeEvent(event)

    def shutdown(self):
        if getattr(self, "_shutdown_done", False):
            return
        self._shutdown_done = True
        self.stop_emulation()
        self.cancel_guided()
        self.timer.stop()
        self.scan_timer.stop()
        if self.session:
            self.finish_recording("Application closed")
        self.shutdown_desktop()
        self.backend.close()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            QTimer.singleShot(0, self.handle_minimized)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_initial_focus_set", False):
            self.primary_buttons[0].setFocus(Qt.FocusReason.OtherFocusReason)
            self._initial_focus_set = True
        if QApplication.platformName() == "windows":
            try:
                import ctypes
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(int(self.winId())), 20,
                                                          ctypes.byref(value), ctypes.sizeof(value))
            except (AttributeError, OSError):
                pass
