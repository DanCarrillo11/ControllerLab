"""Task-based navigation and contextual controls for the desktop workspace."""
from copy import deepcopy
import math
from PySide6.QtWidgets import (QVBoxLayout, QScrollArea, QWidget,
    QTabWidget, QToolButton)

from .widgets import label, button, card

PAGE_COPY = {
    0: ("Device lab", "Check buttons, sticks and triggers in real time."),
    1: ("Device lab", "Check stick travel, center position and movement trails."),
    2: ("Device lab", "Watch each trigger's pressure and observed range."),
    3: ("Device lab", "Inspect the original inputs exposed by your controller or adapter."),
    4: ("Saved sessions", "Review measurements, compare sessions and export reports."),
    5: ("Guided test", "Follow one step at a time, then save your observations."),
    6: ("Emulation", "Choose the controller your game sees, then start when ready."),
    7: ("Settings", "Keep app behavior, controller preferences and help in one place."),
    8: ("Game profiles", "Choose a preset for each game. Your manual profile returns when it closes."),
}
NEW_PROFILE = "__new_profile__"
MANAGE_PROFILES = "__manage_profiles__"


class WorkspaceUX:
    def add_primary_navigation(self, layout, index, title):
        action = button(title)
        action.setCheckable(True)
        action.setObjectName("WorkspaceNav")
        action.setAccessibleName(title)
        self.primary_buttons[index] = action
        if index == 0:
            action.clicked.connect(lambda: self.navigate(self.last_diagnostic_page))
            action.setChecked(True)
        else:
            self.nav_group.addButton(action, index)
        layout.addWidget(action)
        return action

    def update_live_summary(self):
        self.live_sticks.set_sample(self.sample)
        buttons = self.sample.buttons.values() if self.sample.mapped else self.sample.raw_buttons
        count = sum(bool(value) for value in buttons)
        self.live_button_count.setText(str(count) + " held" if self.sample.connected else "—")
        self.live_activity_hint.setText("Inputs respond in real time" if self.sample.connected else "Waiting for live input")
        for side, (value_label, progress) in self.live_triggers.items():
            value = self.sample.axes.get(side + "trigger") if self.sample.connected else None
            available = isinstance(value, (int, float)) and math.isfinite(value)
            progress.setEnabled(available)
            if available:
                value = max(0, min(1, value))
                value_label.setText(f"{value * 100:.0f}%")
                progress.setValue(round(value * 1000))
                value_label.setToolTip("Current reported trigger position")
            else:
                value_label.setText("—")
                progress.setValue(0)
                value_label.setToolTip("No trigger reading is available from this input")
        if not self.sample.connected:
            self.event_label.setText("No live input")
            self.active_label.setText("Reconnect your controller to continue.")

    def update_navigation(self, index):
        title, description = PAGE_COPY[index]
        self.breadcrumb.setText(title)
        self.page_description.setText(description)
        self.primary_buttons[0].setChecked(index <= 3)
        if index <= 3:
            self.last_diagnostic_page = index
        self.diagnostic_navigation.setVisible(index <= 3)
        self.controller_hero.setVisible(index in (0, 1, 2, 3, 5, 6) and self.device is not None)
        self.record_button.setVisible(index <= 3 or self.session is not None)
        if index == 8 and hasattr(self, "desktop"):
            self.ensure_game_profile_page()
        if hasattr(self, "controller_settings_buttons"):
            for widget in self.controller_settings_buttons:
                widget.setEnabled(self.device is not None)
            self.controller_settings_hint.setText(self.device.name if self.device else "Connect a controller to change its settings.")

    def sync_profile_picker(self):
        self.profile_picker.blockSignals(True)
        self.profile_picker.clear()
        self.profile_picker.addItem("Default", "")
        if self.device:
            for key, name in self.store.profiles(self.device.guid):
                self.profile_picker.addItem(name, key)
            self.profile_picker.setCurrentIndex(max(0, self.profile_picker.findData(self.store.active_profile(self.device.guid))))
        self.profile_picker.insertSeparator(self.profile_picker.count())
        self.profile_picker.addItem("New profile…", NEW_PROFILE)
        self.profile_picker.addItem("Manage profiles…", MANAGE_PROFILES)
        self.profile_picker.setEnabled(self.device is not None)
        self.profile_picker.setToolTip("Active profile: " + self.store.profile_name(self.device.guid) if self.device else "Connect a controller to select a profile")
        self.profile_add.setEnabled(self.device is not None)
        self.controller_options.setEnabled(self.device is not None)
        self.profile_picker.blockSignals(False)

    def quick_profile_change(self):
        if not self.device or self.profile_picker.currentIndex() < 0:
            return
        selected = self.profile_picker.currentData()
        if selected in (NEW_PROFILE, MANAGE_PROFILES, None):
            self.sync_profile_picker()
            if selected == NEW_PROFILE:
                self.new_controller_profile()
            elif selected == MANAGE_PROFILES:
                self.open_profiles()
            return
        if selected == self.store.active_profile(self.device.guid):
            return
        try:
            self.store.select_profile(self.device.guid, selected)
            self.pause_game_profiles()
            self.reload_desktop_profile("Controller profile changed")
        except (ValueError, OSError) as exc:
            self.notice("Profile could not be selected: " + str(exc))
            self.sync_profile_picker()

    def current_profile_settings(self):
        if not self.device:
            raise ValueError("Connect a controller before creating a profile.")
        return dict(self.store.device(self.device.guid), mapping=deepcopy(self.mapping),
                    overlay=self.overlay_override, deadzone=self.deadzone_slider.value(),
                    emulation=self.emulation_settings())

    def create_profile_from_current(self, name):
        if not self.device:
            raise ValueError("Connect a controller before creating a profile.")
        guid = self.device.guid
        identifier = self.store.create_profile(guid, name, settings=self.current_profile_settings(), activate=True)
        self.pause_game_profiles()
        self.reload_desktop_profile("Created profile: " + self.store.profile_name(guid))
        self.sync_profile_picker()
        return identifier

    def make_new_profile_dialog(self):
        from .profiles import NewProfileDialog
        expected = (self.device.guid, self.device.instance_id) if self.device else None
        def create(name):
            current = (self.device.guid, self.device.instance_id) if self.device else None
            if expected is None or current != expected:
                raise ValueError("The controller changed. Reopen New profile for the selected controller.")
            return self.create_profile_from_current(name)
        return NewProfileDialog(create, self)

    def new_controller_profile(self):
        if self.device:
            self.make_new_profile_dialog().exec()

    def build_preferences_pages(self):
        from .desktop_dialogs import DesktopDialog
        self._games_signature = None
        self.games_layout = QVBoxLayout(self.games_page)
        self.games_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_layout = QVBoxLayout(self.settings_page)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setAccessibleName("Settings categories")
        self.settings_layout.addWidget(self.settings_tabs)
        self.desktop_form = DesktopDialog(self, embedded=True)
        general_page = QWidget()
        general_layout = QVBoxLayout(general_page)
        general_layout.setContentsMargins(0, 0, 0, 0)
        general_layout.setSpacing(8)
        general = QScrollArea()
        general.setWidgetResizable(True)
        general.setWidget(self.desktop_form)
        general_layout.addWidget(general, 1)
        self.desktop_form.layout().removeWidget(self.desktop_form.footer)
        general_layout.addWidget(self.desktop_form.footer)
        self.settings_tabs.addTab(general_page, "General")

        controller, body = card("Controller preferences")
        self.controller_settings_hint = label("", "Muted", True)
        body.addWidget(self.controller_settings_hint)
        body.addWidget(label("Profiles save input assignments, appearance and emulation settings together.", "Small", True))
        profiles = button("Manage controller profiles…", self.open_profiles)
        mapping = button("Map inputs…", self.map_inputs)
        appearance = QToolButton()
        appearance.setObjectName("ActionMenu")
        appearance.setText("Controller appearance")
        appearance.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        appearance.setMenu(self.overlay_menu)
        details = button("Device details…", self.device_details)
        self.controller_settings_buttons = (profiles, mapping, appearance, details)
        for widget in self.controller_settings_buttons:
            body.addWidget(widget)
        body.addStretch()
        self.settings_tabs.addTab(controller, "Controller")

        help_page, body = card("Help & connection")
        body.addWidget(label("Start with setup, or review what your connected controller exposes.", "Muted", True))
        for title, slot in (("Setup assistant…", self.open_setup),
                            ("Compatibility and diagnostics…", self.show_compatibility),
                            ("Copy diagnostics", self.copy_diagnostics),
                            ("Help and troubleshooting…", self.show_help),
                            ("About Controller Lab…", self.about)):
            body.addWidget(button(title, slot))
        body.addStretch()
        self.settings_tabs.addTab(help_page, "Help")
        self.update_navigation(self.pages.currentIndex())

    def ensure_game_profile_page(self):
        from .desktop_dialogs import GameProfilesDialog
        guid = self.device.guid if self.device else None
        signature = (guid, tuple(self.store.profiles(guid)) if guid else ())
        if self._games_signature == signature:
            return
        if hasattr(self, "games_form"):
            self.games_layout.removeWidget(self.games_form)
            self.games_form.deleteLater()
        self.games_form = GameProfilesDialog(self, embedded=True)
        self.games_layout.addWidget(self.games_form)
        self._games_signature = signature

    def open_connection_setup(self):
        self.stop_emulation()
        dialog = self.make_setup_dialog()
        if self.device and self.sample.mapped:
            dialog.pages.setCurrentIndex(2)
            dialog.refresh()
        dialog.exec()
