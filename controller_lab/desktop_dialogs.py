"""Compact setup, background-operation and game-profile dialogs."""
from copy import deepcopy
from pathlib import Path
import uuid

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QCheckBox,
    QDialogButtonBox, QKeySequenceEdit, QListWidget, QListWidgetItem, QLineEdit,
    QComboBox, QFileDialog, QStackedWidget, QWidget)

from .desktop_settings import clean_rules, executable_key
from .windows_desktop import hotkey_parts
from .widgets import label, button, card
from .motion import Switch


class DesktopDialog(QDialog):
    def __init__(self, window, embedded=False):
        super().__init__(window)
        self.window, self.embedded = window, embedded
        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
            self.setObjectName("EmbeddedPage")
        self.setWindowTitle("Desktop settings")
        self.resize(640, 490)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4 if embedded else 24, 16 if embedded else 24, 4 if embedded else 24, 12 if embedded else 22)
        layout.setSpacing(16)
        if not embedded:
            layout.addWidget(label("Keep your workspace close", "Title"))
            layout.addWidget(label("Control how Controller Lab stays available while you play.", "Muted", True))
        tray, body = card("System tray")
        self.minimize = Switch("Minimize to the system tray")
        self.close_tray = Switch("Keep running in the tray when I close the window")
        for check, key in ((self.minimize, "minimize_to_tray"), (self.close_tray, "close_to_tray")):
            check.setChecked(window.desktop.data[key])
            body.addWidget(check)
        body.addWidget(label("Choose Quit Controller Lab from the tray menu to stop output and exit. Closing the window exits by default.", "Small", True))
        layout.addWidget(tray)
        shortcut, body = card("Stop emulation from any app")
        self.enabled = Switch("Enable global stop shortcut")
        self.enabled.setChecked(window.desktop.data["hotkey_enabled"])
        body.addWidget(self.enabled)
        self.shortcut = QKeySequenceEdit(QKeySequence(window.desktop.data["stop_hotkey"]))
        self.shortcut.setMaximumSequenceLength(1)
        self.shortcut.setAccessibleName("Global stop emulation shortcut")
        body.addWidget(self.shortcut)
        self.status = label(window.hotkey_status(), "Small", True)
        body.addWidget(self.status)
        layout.addWidget(shortcut)
        appearance, body = card("Interface motion")
        self.reduce_motion = Switch("Reduce interface motion")
        self.reduce_motion.setChecked(window.desktop.data["reduce_motion"])
        body.addWidget(self.reduce_motion)
        body.addWidget(label("Turn off page transitions, animated reveals and smooth input tracks.", "Small", True))
        layout.addWidget(appearance)
        layout.addStretch()
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.footer = footer
        footer.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primary")
        footer.accepted.connect(self.save)
        footer.rejected.connect(self.reset_draft if embedded else self.reject)
        if embedded:
            footer.button(QDialogButtonBox.StandardButton.Cancel).setText("Discard changes")
        layout.addWidget(footer)

    def save(self):
        try:
            text, _, _ = hotkey_parts(self.shortcut.keySequence().toString(QKeySequence.SequenceFormat.PortableText))
            self.window.save_desktop_options(minimize_to_tray=self.minimize.isChecked(),
                close_to_tray=self.close_tray.isChecked(), hotkey_enabled=self.enabled.isChecked(), stop_hotkey=text,
                reduce_motion=self.reduce_motion.isChecked())
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))
            return
        if self.embedded:
            self.status.setText("Saved. " + self.window.hotkey_status())
        else:
            self.accept()

    def reset_draft(self):
        data = self.window.desktop.data
        self.minimize.setChecked(data["minimize_to_tray"])
        self.close_tray.setChecked(data["close_to_tray"])
        self.enabled.setChecked(data["hotkey_enabled"])
        self.reduce_motion.setChecked(data["reduce_motion"])
        self.shortcut.setKeySequence(QKeySequence(data["stop_hotkey"]))
        self.status.setText(self.window.hotkey_status())

    def reject(self):
        if self.embedded:
            self.reset_draft()
        else:
            super().reject()


class GameProfilesDialog(QDialog):
    def __init__(self, window, embedded=False):
        super().__init__(window)
        self.embedded = embedded
        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
            self.setObjectName("EmbeddedPage")
        self.window, self.rules = window, deepcopy(window.desktop.data["game_rules"])
        self.guid = window.device.guid if window.device else None
        self.setWindowTitle("Game profiles")
        self.resize(760, 590)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4 if embedded else 24, 4 if embedded else 24, 4 if embedded else 24, 4 if embedded else 22)
        layout.setSpacing(10)
        if not embedded:
            layout.addWidget(label("The right profile for each game", "Title"))
        layout.addWidget(label("Choose the game's .exe and the profile to load. Changes stop emulation; start it again when ready.", "Muted", True))
        self.enabled = QCheckBox("Automatically select profiles for running games")
        self.enabled.setChecked(window.desktop.data["game_profiles_enabled"])
        layout.addWidget(self.enabled)
        layout.addWidget(label("Controller: " + (window.device.name if window.device else "Connect a controller to add or edit rules."), "Small", True))
        if embedded:
            columns = QHBoxLayout()
            columns.setSpacing(12)
            listing_card, list_body = card("Your games")
            listing_card.setFixedWidth(236)
            editor_card, editor_body = card("Game profile")
            columns.addWidget(listing_card)
            columns.addWidget(editor_card, 1)
            layout.addLayout(columns, 1)
        else:
            list_body = editor_body = layout
        self.listing = QListWidget()
        self.listing.setMinimumHeight(72)
        self.listing.setAccessibleName("Games with automatic profile rules")
        self.listing.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.listing.currentRowChanged.connect(self.select_rule)
        list_body.addWidget(self.listing, 1)
        self.empty_hint = label("No games added yet. Choose a game's .exe to create your first rule.", "Small", True)
        list_body.addWidget(self.empty_hint)
        form = QGridLayout()
        self.name, self.path, self.profile = QLineEdit(), QLineEdit(), QComboBox()
        self.name.setPlaceholderText("Game name")
        self.path.setPlaceholderText("Choose the game's .exe…")
        self.path.setReadOnly(True)
        self.profile.addItem("Default", "")
        self.profile.setPlaceholderText("Choose a profile…")
        if self.guid:
            for key, name in window.store.profiles(self.guid):
                self.profile.addItem(name, key)
        self.rule_enabled = QCheckBox("Enable this game rule")
        self.rule_enabled.setChecked(True)
        browse = button("Browse…", self.browse)
        form.addWidget(label("Game"), 0, 0)
        form.addWidget(self.name, 0, 1, 1, 2)
        form.addWidget(label("Executable"), 1, 0)
        form.addWidget(self.path, 1, 1)
        form.addWidget(browse, 1, 2)
        form.addWidget(label("Profile"), 2, 0)
        form.addWidget(self.profile, 2, 1, 1, 2)
        form.addWidget(self.rule_enabled, 3, 1, 1, 2)
        editor_body.addLayout(form)
        actions = QHBoxLayout()
        self.add_button = button("Add game", self.put_rule)
        self.new_button = button("New game", self.new_rule)
        self.remove_button = button("Remove game", self.remove_rule)
        actions.addWidget(self.add_button)
        if embedded:
            list_body.addWidget(self.new_button)
            list_body.addWidget(self.remove_button)
        else:
            actions.addWidget(self.new_button)
            actions.addWidget(self.remove_button)
        actions.addStretch()
        editor_body.addLayout(actions)
        if embedded:
            editor_body.addStretch()
        for widget in (self.name, self.path, self.profile, self.rule_enabled, browse, self.add_button, self.new_button, self.remove_button):
            widget.setEnabled(self.guid is not None)
        self.status = label("If multiple games are open, focus one to choose its profile. Close it to return to your manual profile.", "Small", True)
        layout.addWidget(self.status)
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.save)
        footer.rejected.connect(self.reset_draft if embedded else self.reject)
        if embedded:
            footer.button(QDialogButtonBox.StandardButton.Cancel).setText("Discard changes")
        layout.addWidget(footer)
        self.refresh()
        self.editor_signature = self.read_editor()

    def refresh(self, selected=-1):
        self.listing.blockSignals(True)
        self.listing.clear()
        self.visible = [(i, r) for i, r in enumerate(self.rules) if r["guid"] == self.guid]
        self.empty_hint.setVisible(not self.visible)
        for _, rule in self.visible:
            profile = dict(self.window.store.profiles(self.guid)).get(rule["profile_id"], "Missing profile" if rule["profile_id"] else "Default")
            item = QListWidgetItem(rule["name"] + ("\n" if self.embedded else "  →  ") + profile + (" · Disabled" if not rule["enabled"] else ""))
            item.setToolTip(rule["executable"])
            self.listing.addItem(item)
        self.listing.setCurrentRow(selected)
        self.listing.blockSignals(False)
        self.select_rule(selected)

    def select_rule(self, row):
        selected = 0 <= row < len(getattr(self, "visible", []))
        self.add_button.setText("Update game" if selected else "Add game")
        self.remove_button.setEnabled(selected and self.guid is not None)
        if not selected:
            return
        rule = self.visible[row][1]
        self.name.setText(rule["name"])
        self.path.setText(rule["executable"])
        self.profile.setCurrentIndex(self.profile.findData(rule["profile_id"]))
        self.rule_enabled.setChecked(rule["enabled"])
        self.editor_signature = self.read_editor()

    def read_editor(self):
        return (self.name.text(), self.path.text(), self.profile.currentData(), self.rule_enabled.isChecked())

    def new_rule(self):
        self.listing.setCurrentRow(-1)
        self.name.clear()
        self.path.clear()
        self.profile.setCurrentIndex(0)
        self.rule_enabled.setChecked(True)
        self.editor_signature = self.read_editor()

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose game executable", self.path.text(), "Windows applications (*.exe)")
        if path:
            self.path.setText(path)
            if not self.name.text().strip():
                self.name.setText(Path(path).stem)

    def put_rule(self):
        if not self.guid:
            return False
        try:
            row = self.listing.currentRow()
            original = self.visible[row][0] if 0 <= row < len(self.visible) else None
            rule = dict(id=self.rules[original]["id"] if original is not None else uuid.uuid4().hex,
                name=self.name.text(), executable=executable_key(self.path.text()), guid=self.guid,
                profile_id=self.profile.currentData(), enabled=self.rule_enabled.isChecked())
            if rule["profile_id"] and rule["profile_id"] not in dict(self.window.store.profiles(self.guid)):
                raise ValueError("Choose an available profile.")
            updated = deepcopy(self.rules)
            if original is None:
                updated.append(rule)
            else:
                updated[original] = rule
            self.rules = clean_rules(updated)
            visible_rules = [r for r in self.rules if r["guid"] == self.guid]
            self.refresh(next(i for i, item in enumerate(visible_rules) if item["id"] == rule["id"]))
            self.status.setText("Rule added to the draft. Choose Save to apply it.")
            return True
        except ValueError as exc:
            self.status.setText(str(exc))
            return False

    def remove_rule(self):
        row = self.listing.currentRow()
        if 0 <= row < len(self.visible):
            del self.rules[self.visible[row][0]]
            self.new_rule()
            self.refresh()

    def save(self):
        if self.read_editor() != self.editor_signature and not self.put_rule():
            return
        try:
            self.window.save_game_rules(self.enabled.isChecked(), self.rules)
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))
            return
        if self.embedded:
            self.status.setText("Saved. Game profiles will be checked when you leave this page.")
        else:
            self.accept()

    def reset_draft(self):
        self.rules = deepcopy(self.window.desktop.data["game_rules"])
        self.enabled.setChecked(self.window.desktop.data["game_profiles_enabled"])
        self.new_rule()
        self.refresh()
        self.status.setText("Unsaved changes discarded.")

    def reject(self):
        if self.embedded:
            self.reset_draft()
        else:
            super().reject()


class SetupDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window, self.checking = window, False
        self.setWindowTitle("Set up Controller Lab")
        self.resize(700, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(15)
        layout.addWidget(label("Make yourself at home", "Title"))
        self.progress = label("", "Eyebrow")
        layout.addWidget(self.progress)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.controller = QComboBox()
        page, body = self.page("Connect a controller", "Connect via USB or pair it in Windows. Choose the controller you want to use.")
        body.addWidget(self.controller)
        body.addWidget(label("Your existing profiles and measurements stay available.", "Small", True))
        body.addStretch()
        self.controller.currentIndexChanged.connect(self.choose_controller)
        page, body = self.page("Check the input mapping", "Automatic mappings work for many controllers. For adapters or unknown models, assign their raw inputs with Listen.")
        self.mapping_status = label("", "HeroValue", True)
        body.addWidget(self.mapping_status)
        body.addWidget(button("Map inputs…", window.map_inputs))
        body.addStretch()
        page, body = self.page("Check virtual output", "Emulation is optional. This check creates and removes neutral Xbox 360 and DualShock 4 controllers without sending input or vibration.")
        self.output_status = label("Not checked. You can continue using diagnostics without emulation.", "Muted", True)
        body.addWidget(self.output_status)
        self.check_button = button("Check virtual outputs", self.check_output, True)
        body.addWidget(self.check_button)
        links = QHBoxLayout()
        links.addWidget(button("Official driver information", lambda: QDesktopServices.openUrl(QUrl("https://github.com/nefarius/ViGEmBus"))))
        links.addWidget(button("HidHide setup guide", lambda: QDesktopServices.openUrl(QUrl("https://github.com/nefarius/HidHide"))))
        body.addLayout(links)
        body.addStretch()
        page, body = self.page("Ready for your next session", "Open Emulation, choose an output and press Start emulation when you are ready to play.")
        body.addWidget(label("Stop shortcut: " + window.desktop.data["stop_hotkey"] + "\nChange it under Settings → General.", "HeroValue", True))
        body.addWidget(label("Open Game profiles in the sidebar to select presets automatically. Tray options are under Settings → General.", "Muted", True))
        body.addWidget(label("If a game responds twice, it may see both controllers. Configure HidHide separately for that game; Controller Lab does not change device hiding.", "Small", True))
        body.addStretch()
        self.error = label("", "Small", True)
        layout.addWidget(self.error)
        footer = QHBoxLayout()
        self.skip = button("Skip for now", self.finish)
        self.back = button("Back", self.go_back)
        self.next = button("Next", self.go_next, True)
        footer.addWidget(self.skip)
        footer.addStretch()
        footer.addWidget(self.back)
        footer.addWidget(self.next)
        layout.addLayout(footer)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(700)
        self.refresh()

    def page(self, title, text):
        page = QWidget()
        body = QVBoxLayout(page)
        body.setContentsMargins(0, 10, 0, 0)
        body.setSpacing(16)
        body.addWidget(label(title, "SectionTitle"))
        body.addWidget(label(text, "Muted", True))
        self.pages.addWidget(page)
        return page, body

    def refresh(self):
        current = self.window.device.instance_id if self.window.device else None
        self.controller.blockSignals(True)
        self.controller.clear()
        if not self.window.devices:
            self.controller.addItem("Waiting for a controller…", None)
        else:
            for device in self.window.devices:
                self.controller.addItem(device.name, device.instance_id)
            self.controller.setCurrentIndex(max(0, self.controller.findData(current)))
        self.controller.blockSignals(False)
        connected = self.window.device is not None and self.window.sample.connected
        mapped = connected and self.window.sample.mapped
        self.mapping_status.setText("Mapped input available" if mapped else "Map the inputs to enable virtual output" if connected else "No controller connected")
        step = self.pages.currentIndex()
        self.progress.setText("STEP " + str(step + 1) + " OF 4")
        self.back.setEnabled(step > 0 and not self.checking)
        self.next.setText("Finish" if step == 3 else "Next")
        self.next.setEnabled(not self.checking and (connected if step == 0 else mapped if step == 1 else True))

    def choose_controller(self):
        iid = self.controller.currentData()
        index = next((i for i, d in enumerate(self.window.devices) if d.instance_id == iid), -1)
        self.window.device_list.setCurrentRow(index)
        self.refresh()

    def go_back(self):
        self.pages.setCurrentIndex(max(0, self.pages.currentIndex() - 1))
        self.refresh()

    def go_next(self):
        if self.pages.currentIndex() == 3:
            self.finish()
        else:
            self.pages.setCurrentIndex(self.pages.currentIndex() + 1)
            self.refresh()

    def check_output(self):
        if self.window.demo:
            self.output_status.setText("Unavailable for simulated inputs. Run this check with the normal desktop app.")
            return
        self.checking = True
        self.check_button.setEnabled(False)
        self.skip.setEnabled(False)
        self.output_status.setText("Checking the virtual bus…")
        self.refresh()
        self.window.check_virtual_outputs(self.output_checked)

    def output_checked(self, result):
        self.checking = False
        self.check_button.setEnabled(True)
        self.skip.setEnabled(True)
        if result.get("ready"):
            text = "Xbox 360 and DualShock 4: ready. Neutral controllers were created and removed."
        else:
            text = "Virtual output is unavailable. " + result.get("error", " ".join(v.get("error", "") for v in result.get("outputs", {}).values()))
        self.output_status.setText(text)
        self.refresh()

    def finish(self):
        try:
            self.window.desktop.save(setup_completed=True)
        except (OSError, ValueError) as exc:
            self.error.setText("Setup could not be saved: " + str(exc))
            return
        self.accept()

    def done(self, result):
        self.refresh_timer.stop()
        super().done(result)
