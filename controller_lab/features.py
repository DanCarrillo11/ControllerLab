"""Guided tests, reports, profiles and explicitly enabled virtual controller output."""
from dataclasses import asdict
from html import escape
import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QListWidget, QListWidgetItem, QLineEdit, QTextBrowser, QComboBox, QToolButton, QMenu,
    QProgressBar, QDialog, QDialogButtonBox, QFileDialog, QMessageBox, QInputDialog,
    QScrollArea, QSpinBox, QDoubleSpinBox, QCheckBox)

from .diagnostics import GuidedRun, STEPS, capability_rows
from .emulation import OUTPUT_BUTTONS, clean_settings, driver_status
from .model import button_names
from .profiles import ProfilesDialog
from .reports import report_html, export_png, comparison_rows, table
from .storage import atomic_write, report_csv
from .widgets import label, button, card, StateBadge
from .motion import AnimatedProgress, Switch, RevealPanel, reveal
from .dashboard import OutputRoute


class Workbench:
    def decorate_report(self, report):
        guid = report["device"]["guid"]
        report.update(demo=self.demo, overlay=self.family,
                      profile_id=self.store.active_profile(guid), profile_name=self.store.profile_name(guid),
                      mapping_source="Custom app-local assignments" if self.mapping else "SDL automatic mapping" if report["device"]["mapped"] else "Raw inputs only",
                      input_mapping=self.mapping or None, vibration_evidence=self.vibration_evidence or "Not tested")
        return report

    def build_sessions_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        listing, left = card("Saved sessions")
        listing.setFixedWidth(240)
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("Search sessions…")
        self.history_search.setAccessibleName("Search saved sessions")
        self.history_search.textChanged.connect(self.filter_sessions)
        left.addWidget(self.history_search)
        tools = QToolButton()
        tools.setObjectName("ActionMenu")
        tools.setText("Session tools")
        tools.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(tools)
        menu.addAction("Import report…", self.import_session)
        menu.addAction("Restore last deleted session", self.restore_session)
        tools.setMenu(menu)
        left.addWidget(tools)
        self.history_list = QListWidget()
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_list.currentRowChanged.connect(self.show_report)
        left.addWidget(self.history_list, 1)
        layout.addWidget(listing)
        detail, right = card("Session report")
        self.history_text = QTextBrowser()
        self.history_text.setOpenExternalLinks(False)
        self.history_text.setAccessibleName("Visual session report")
        right.addWidget(self.history_text, 1)
        self.comparison = label("", "Small", True)
        right.addWidget(self.comparison)
        comparison = QHBoxLayout()
        self.compare_choice = QComboBox()
        self.compare_choice.setMinimumWidth(0)
        comparison.addWidget(self.compare_choice, 1)
        self.compare_button = button("Compare", self.compare_sessions)
        comparison.addWidget(self.compare_button)
        right.addLayout(comparison)
        toolbar = QHBoxLayout()
        export = QToolButton()
        export.setObjectName("ActionMenu")
        export.setText("Export report")
        export.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        exports = QMenu(export)
        for kind, title in (("png", "Image · PNG…"), ("html", "Web report · HTML…"), ("json", "JSON…"), ("csv", "CSV…")):
            action = exports.addAction(title, lambda checked=False, fmt=kind: self.export_report(fmt))
            setattr(self, "export_" + kind, action)
        export.setMenu(exports)
        toolbar.addWidget(export)
        self.rename_session_button = button("Rename…", self.rename_session)
        self.delete_session_button = button("Delete…", self.delete_session)
        toolbar.addWidget(self.rename_session_button)
        toolbar.addWidget(self.delete_session_button)
        toolbar.addStretch()
        right.addLayout(toolbar)
        layout.addWidget(detail, 1)
        self.pages.addWidget(page)
        self.refresh_sessions()

    def refresh_sessions(self):
        self.all_history = self.store.reports()
        self.filter_sessions()

    def filter_sessions(self):
        query = self.history_search.text().strip().casefold()
        previous = getattr(self, "selected_report_id", None)
        self.history = [(key, report) for key, report in self.all_history if not query or query in
                        (str(report.get("name", "")) + " " + report["device"]["name"] + " " + str(report.get("profile_name", "Default")) + " " + report["created"]).casefold()]
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for key, report in self.history:
            title = report.get("name") or report["device"]["name"]
            title = self.history_list.fontMetrics().elidedText(str(title), Qt.TextElideMode.ElideRight, 188)
            item = QListWidgetItem(title + "\n" + report["created"][:16].replace("T", " ") + " UTC\n" + str(report.get("profile_name", "Default")))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(str(report.get("name") or report["device"]["name"]))
            self.history_list.addItem(item)
        self.history_list.blockSignals(False)
        index = next((i for i, (key, _) in enumerate(self.history) if key == previous), 0 if self.history else -1)
        self.history_list.setCurrentRow(index)
        self.display_session(index)

    def display_session(self, index):
        valid = 0 <= index < len(self.history)
        self.selected_report_id, self.selected_report = self.history[index] if valid else (None, None)
        for name in ("json", "csv", "html", "png"):
            getattr(self, "export_" + name).setEnabled(valid)
        self.rename_session_button.setEnabled(valid)
        self.delete_session_button.setEnabled(valid)
        self.compare_choice.clear()
        self.compare_choice.addItem("Choose another session…", "")
        self.compare_button.setEnabled(valid)
        if not valid:
            self.history_text.setPlainText("No sessions match this view. Record a session, run a guided test or import a report.")
            self.comparison.clear()
            return
        self.history_text.setHtml(report_html(self.selected_report))
        self.history_text.moveCursor(self.history_text.textCursor().MoveOperation.Start)
        for key, report in self.all_history:
            if key != self.selected_report_id:
                title = str(report.get("name") or report["device"]["name"])
                self.compare_choice.addItem(title[:40] + " · " + report["created"][:16], key)
        self.comparison.setText("Compare recorded measurements; differences are not an automatic hardware grade.")

    def export_session(self, kind):
        report = self.selected_report
        if report is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export session report", "ControllerLab-report." + kind, kind.upper() + " files (*." + kind + ")")
        if not path:
            return
        try:
            if kind == "png":
                export_png(report, path)
            else:
                text = report_html(report) if kind == "html" else json.dumps(report, indent=2) if kind == "json" else report_csv(report)
                atomic_write(path, text)
            self.notice("Report exported.")
        except (OSError, ValueError) as exc:
            self.notice("Report could not be exported: " + str(exc))

    def rename_session(self):
        if not self.selected_report_id:
            return
        name, ok = QInputDialog.getText(self, "Rename session", "Session name", text=self.selected_report.get("name", ""))
        if ok:
            try:
                self.store.rename_report(self.selected_report_id, name)
                self.refresh_sessions()
            except (OSError, ValueError) as exc:
                self.notice(str(exc))

    def delete_session(self):
        if not self.selected_report_id:
            return
        if QMessageBox.question(self, "Delete session", "Move this session out of the history? You can restore it from Session tools.") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete_report(self.selected_report_id)
            self.refresh_sessions()
        except (OSError, ValueError) as exc:
            self.notice(str(exc))

    def restore_session(self):
        try:
            restored = self.store.restore_report()
            self.refresh_sessions()
            self.notice("Session restored." if restored else "There are no deleted sessions to restore.")
        except (OSError, ValueError) as exc:
            self.notice(str(exc))

    def import_session(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Controller Lab report", "", "JSON reports (*.json)")
        if path:
            try:
                self.store.import_report(path)
                self.history_search.clear()
                self.refresh_sessions()
                self.notice("Report imported.")
            except (OSError, ValueError) as exc:
                self.notice("Report could not be imported: " + str(exc))

    def compare_sessions(self):
        other = dict(self.all_history).get(self.compare_choice.currentData())
        if self.selected_report is None or other is None:
            self.notice("Choose a second session to compare.")
            return
        same = all(self.selected_report.get(key) == other.get(key) for key in ("profile_id", "input_mapping")) and self.selected_report["device"]["guid"] == other["device"]["guid"]
        self.text_dialog("Compare sessions", '<h2>Session comparison</h2><p>' +
                         ("Same reported device, profile and mapping." if same else "Different device, profile or mapping. Treat these as separate observations.") + '</p>' + table(comparison_rows(self.selected_report, other)), 850, 600)

    def text_dialog(self, title, html, width=720, height=540):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(width, height)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setHtml(html)
        layout.addWidget(browser)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        dialog.exec()

    def open_profiles(self):
        if not self.device:
            return
        self.stop_emulation()
        self.cancel_guided()
        if self.session:
            self.finish_recording("Profile management opened")
        self.cancel_rest()
        guid, iid = self.device.guid, self.device.instance_id
        dialog = ProfilesDialog(self.store, guid, self, current_settings=self.current_profile_settings())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.pause_game_profiles()
                self.store.select_profile(guid, dialog.combo.currentData())
            except (OSError, ValueError) as exc:
                self.notice(str(exc))
        index = next((i for i, device in enumerate(self.devices) if device.instance_id == iid), -1)
        self.device = None
        self.select_device(index)

    def build_guided_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        steps, left = card("Guided test")
        steps.setFixedWidth(175)
        self.guide_steps = QListWidget()
        self.guide_steps.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for title, _ in STEPS:
            self.guide_steps.addItem(title)
        left.addWidget(self.guide_steps, 1)
        left.addWidget(label("You choose when to continue. Unobserved inputs stay pending.", "Small", True))
        layout.addWidget(steps)
        detail, right = card()
        self.guide_title = label("A complete controller check", "SectionTitle")
        self.guide_instruction = label("Start a guided test to check buttons, stick range, triggers, center and vibration.", "Muted", True)
        right.addWidget(self.guide_title)
        right.addWidget(self.guide_instruction)
        self.guide_progress = AnimatedProgress()
        self.guide_progress.setTextVisible(False)
        self.guide_progress.setRange(0, len(STEPS))
        right.addWidget(self.guide_progress)
        self.guide_text = QTextBrowser()
        self.guide_text.setPlainText("Measurements are observations. This test does not automatically certify a controller as healthy or faulty.")
        right.addWidget(self.guide_text, 1)
        self.guide_center = button("Measure center · 5s", self.guided_center)
        right.addWidget(self.guide_center)
        vibration = QHBoxLayout()
        self.guide_vibration = button("Test vibration", self.guided_vibration)
        self.guide_felt = button("I felt it", lambda: self.confirm_vibration(True))
        self.guide_not_felt = button("Not felt", lambda: self.confirm_vibration(False))
        for widget in (self.guide_vibration, self.guide_felt, self.guide_not_felt):
            vibration.addWidget(widget)
        right.addLayout(vibration)
        controls = QHBoxLayout()
        self.guide_start = button("Start guided test", self.start_guided, True)
        self.guide_next = button("Next", self.guided_next)
        self.guide_cancel = button("Cancel", self.cancel_guided)
        self.guide_save = button("Save report", self.save_guided)
        for widget in (self.guide_start, self.guide_next, self.guide_cancel, self.guide_save):
            controls.addWidget(widget)
        right.addLayout(controls)
        layout.addWidget(detail, 1)
        self.pages.addWidget(page)
        self.update_guided()

    def start_guided(self):
        if not self.device or not self.sample.connected:
            return
        if self.emulation.running:
            self.notice("Stop emulation before starting a guided test.")
            return
        if self.session:
            self.finish_recording("Guided test started")
        self.cancel_rest()
        self.guided = GuidedRun(self.device, self.sample)
        self.update_guided()

    def cancel_guided(self, *args):
        if self.guided:
            self.guided.cancelled = True
        self.guided = None
        self.update_guided()

    def guided_next(self):
        if self.guided:
            try:
                self.guided.next()
            except ValueError as exc:
                self.notice(str(exc))
            self.update_guided()

    def guided_center(self):
        if self.guided:
            try:
                self.guided.measure_center(self.sample)
            except ValueError as exc:
                self.notice(str(exc))
            self.update_guided()

    def guided_vibration(self):
        if self.guided and not self.demo:
            accepted = self.rumble(1, 1)
            self.guided.command_accepted = bool(accepted)
            self.guided.vibration = "Command accepted; physical response not confirmed" if accepted else "Command unavailable on this connection"
            self.update_guided()

    def confirm_vibration(self, felt):
        if self.guided and self.guided.command_accepted:
            self.guided.vibration = "Felt by the user" if felt else "User did not feel vibration"
            self.vibration_evidence = self.guided.vibration
            self.update_guided()

    def save_guided(self):
        if not self.guided or self.guided.step != len(STEPS) - 1 or not self.guided.session.samples:
            return
        report = self.decorate_report(self.guided.report(self.family))
        report["name"] = "Guided test · " + report["created"][:16].replace("T", " ")
        try:
            self.store.save_report(report)
            self.guided = None
            self.refresh_history()
            self.update_guided()
            self.navigate(4)
            self.notice("Guided report saved. Export the visual report from Sessions.")
        except OSError as exc:
            self.notice("Report could not be saved: " + str(exc))

    def update_guided(self):
        if not hasattr(self, "guide_start"):
            return
        run = self.guided
        step = run.step if run else -1
        self.guide_start.setEnabled(self.device is not None and self.sample.connected and run is None)
        self.guide_start.setVisible(run is None)
        self.guide_next.setVisible(run is not None and step < len(STEPS) - 1)
        self.guide_next.setEnabled(run is not None and run.rest_start is None)
        self.guide_cancel.setVisible(run is not None)
        self.guide_save.setVisible(step == len(STEPS) - 1)
        self.guide_save.setEnabled(run is not None and bool(run.session.samples))
        self.guide_center.setVisible(step == 3)
        self.guide_center.setEnabled(run is not None and run.rest_start is None)
        for widget in (self.guide_vibration, self.guide_felt, self.guide_not_felt):
            widget.setVisible(step == 4)
        self.guide_vibration.setEnabled(run is not None and not self.demo)
        self.guide_felt.setEnabled(run is not None and bool(run.command_accepted))
        self.guide_not_felt.setEnabled(run is not None and bool(run.command_accepted))
        self.guide_progress.setValue(step + 1)
        if run:
            self.guide_steps.setCurrentRow(step)
            self.guide_title.setText(f"{step + 1} / {len(STEPS)} · {STEPS[step][0]}")
            self.guide_instruction.setText(STEPS[step][1])
            text = run.summary(self.family)
            if self.guide_text.toPlainText() != text:
                self.guide_text.setPlainText(text)
        else:
            self.guide_title.setText("A complete controller check")
            self.guide_instruction.setText("Start a guided test to check buttons, sticks, triggers, center and vibration.")
            self.guide_text.setPlainText("No active guided test. Saved reports remain available in Sessions.")

    def show_compatibility(self):
        rows = capability_rows(self.device, self.sample, self.mapping, self.vibration_evidence)
        html = '<h2>Compatibility and diagnostics</h2>' + table(rows)
        if self.device:
            html += '<p>Profile: ' + escape(self.store.profile_name(self.device.guid)) + '<br>Reported GUID: ' + escape(self.device.guid) + '</p>'
        html += '<p>Use Settings → Map inputs for an unmapped controller. If another mapper or Steam Input exposes a virtual device, this app can only inspect the device reported by Windows.</p>'
        self.text_dialog("Compatibility and diagnostics", html)

    def copy_diagnostics(self):
        data = {"application": "Controller Lab", "demo": self.demo, "device": asdict(self.device) if self.device else None,
                "capabilities": capability_rows(self.device, self.sample, self.mapping, self.vibration_evidence),
                "driver_presence": driver_status(), "emulation_running": self.emulation.running,
                "emulation_error": self.emulation.error, "input_error": getattr(self.backend, "error", "")}
        QApplication.clipboard().setText(json.dumps(data, indent=2))
        self.notice("Diagnostics copied. Review them before sharing; they include the device name and GUID.")

    def build_emulation_page(self):
        page = QWidget()
        composition = QVBoxLayout(page)
        composition.setContentsMargins(0, 0, 0, 0)
        composition.setSpacing(12)
        self.emu_route = OutputRoute()
        composition.addWidget(self.emu_route)
        layout = QHBoxLayout()
        composition.addLayout(layout, 1)
        layout.setContentsMargins(0, 0, 0, 0)
        settings, left = card("Virtual controller")
        left.addWidget(label("Choose the controller your game should receive.", "Muted", True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form = QWidget()
        form.setObjectName("FormBody")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 6, 0)
        form_layout.setSpacing(15)
        self.emu_target = QComboBox()
        self.emu_target.addItem("Xbox 360 · XInput", "x360")
        self.emu_target.addItem("DualShock 4", "ds4")
        self.emu_target.currentIndexChanged.connect(self.update_output_route)
        form_layout.addWidget(label("Output controller", "Small"))
        form_layout.addWidget(self.emu_target)
        self.emu_checks = {"feedback": Switch("Forward game vibration")}
        form_layout.addWidget(self.emu_checks["feedback"])
        self.emu_advanced_toggle = button("Advanced adjustments  ▸")
        self.emu_advanced_toggle.setCheckable(True)
        self.emu_advanced_toggle.setObjectName("Disclosure")
        form_layout.addWidget(self.emu_advanced_toggle)
        advanced_content = QWidget()
        self.emu_advanced = RevealPanel(advanced_content)
        grid = QGridLayout(advanced_content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setVerticalSpacing(10)
        self.emu_curve = QComboBox()
        for name in ("linear", "squared", "cubic"):
            self.emu_curve.addItem(name.title(), name)
        self.emu_deadzone, self.emu_trigger = QSpinBox(), QSpinBox()
        for widget in (self.emu_deadzone, self.emu_trigger):
            widget.setRange(0, 40)
            widget.setSuffix("%")
        self.emu_sensitivity = QDoubleSpinBox()
        self.emu_sensitivity.setRange(.1, 2)
        self.emu_sensitivity.setSingleStep(.1)
        self.emu_sensitivity.setSuffix(" ×")
        for row, (title, widget) in enumerate((("Stick deadzone", self.emu_deadzone),
                  ("Response curve", self.emu_curve), ("Sensitivity", self.emu_sensitivity), ("Trigger deadzone", self.emu_trigger))):
            grid.addWidget(label(title), row, 0)
            grid.addWidget(widget, row, 1)
        for row, (key, title) in enumerate((("swap_sticks", "Swap left and right sticks"), ("invert_left_y", "Invert left Y"),
                                          ("invert_right_y", "Invert right Y")), 4):
            check = QCheckBox(title)
            self.emu_checks[key] = check
            grid.addWidget(check, row, 0, 1, 2)
        self.emu_bindings = {}
        grid.addWidget(button("Remap output buttons…", self.edit_output_buttons), 7, 0, 1, 2)
        form_layout.addWidget(self.emu_advanced)
        self.emu_advanced.hide()
        self.emu_advanced_toggle.toggled.connect(lambda expanded: reveal(self.emu_advanced, expanded))
        self.emu_advanced_toggle.toggled.connect(lambda expanded: self.emu_advanced_toggle.setText("Advanced adjustments  ▾" if expanded else "Advanced adjustments  ▸"))
        form_layout.addStretch()
        form_layout.addWidget(button("Save adjustments to profile", self.save_emulation_settings))
        scroll.setWidget(form)
        self.emu_form = form
        left.addWidget(scroll, 1)
        actions = QHBoxLayout()
        self.emu_start = button("Start emulation", self.start_emulation, True)
        self.emu_stop = button("Stop emulation", lambda: self.stop_emulation())
        actions.addWidget(self.emu_start)
        actions.addWidget(self.emu_stop)
        left.addLayout(actions)
        self.emu_stop_hint = label("", "Small", True)
        left.addWidget(self.emu_stop_hint)
        layout.addWidget(settings, 1)
        status, right = card("Output status")
        status.setFixedWidth(270)
        self.emu_state = StateBadge("Stopped")
        self.emu_state.setWordWrap(True)
        self.emu_state.setProperty("variant", "output")
        right.addWidget(self.emu_state)
        self.game_profile_status = label("Game profiles off", "Small", True)
        right.addWidget(self.game_profile_status)
        self.emu_driver = QTextBrowser()
        self.emu_driver.setObjectName("HelpPane")
        self.emu_driver.setOpenExternalLinks(False)
        self.emu_driver.setFixedHeight(58)
        right.addWidget(self.emu_driver)
        right.addWidget(button("Connection setup…", self.open_connection_setup))
        self.emu_help_toggle = button("Connection help  ▸")
        self.emu_help_toggle.setObjectName("Disclosure")
        self.emu_help_toggle.setCheckable(True)
        right.addWidget(self.emu_help_toggle)
        connection_help = QWidget()
        help_layout = QVBoxLayout(connection_help)
        help_layout.setContentsMargins(0, 0, 0, 0)
        help_layout.addWidget(label("If a game responds twice, configure HidHide separately to hide the physical input from the game.", "Small", True))
        help_layout.addWidget(button("Copy application path", self.copy_application_path))
        help_layout.addWidget(button("HidHide setup guide", lambda: QDesktopServices.openUrl(QUrl("https://github.com/nefarius/HidHide"))))
        help_layout.addWidget(button("Virtual driver information", lambda: QDesktopServices.openUrl(QUrl("https://github.com/nefarius/ViGEmBus"))))
        self.emu_help_scroll = QScrollArea()
        self.emu_help_scroll.setWidgetResizable(True)
        self.emu_help_scroll.setWidget(connection_help)
        self.emu_help_scroll.setMaximumHeight(210)
        right.addWidget(self.emu_help_scroll, 1)
        self.emu_help_scroll.hide()
        self.emu_help_toggle.toggled.connect(lambda expanded: reveal(self.emu_help_scroll, expanded))
        self.emu_help_toggle.toggled.connect(lambda expanded: self.emu_help_toggle.setText("Connection help  ▾" if expanded else "Connection help  ▸"))
        right.addStretch()
        right.addWidget(label("Keep Controller Lab open while playing. Output stops on disconnect or exit.", "Small", True))
        layout.addWidget(status)
        self.pages.addWidget(page)
        self.load_emulation_settings({})
        self.sync_emulation_ui()

    def load_emulation_settings(self, settings):
        config = clean_settings(settings)
        self.emu_target.setCurrentIndex(max(0, self.emu_target.findData(config["target"])))
        self.emu_curve.setCurrentIndex(max(0, self.emu_curve.findData(config["curve"])))
        self.emu_deadzone.setValue(round(config["deadzone"] * 100))
        self.emu_trigger.setValue(round(config["trigger_deadzone"] * 100))
        self.emu_sensitivity.setValue(config["sensitivity"])
        for key, check in self.emu_checks.items():
            check.setChecked(config[key])
        self.emu_bindings = config["buttons"].copy()

    def emulation_settings(self):
        return clean_settings(dict(target=self.emu_target.currentData(), curve=self.emu_curve.currentData(),
            deadzone=self.emu_deadzone.value() / 100, trigger_deadzone=self.emu_trigger.value() / 100,
            sensitivity=self.emu_sensitivity.value(), buttons=self.emu_bindings,
            **{key: check.isChecked() for key, check in self.emu_checks.items()}))

    def save_emulation_settings(self):
        if self.device:
            self.save_preference(emulation=self.emulation_settings())
            self.notice("Emulation settings saved to the current profile.")

    def edit_output_buttons(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Output button mapping")
        dialog.resize(520, 560)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Choose what each input button sends to the virtual output.", "Muted", True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        names = button_names(self.family)
        outputs = button_names("playstation" if self.emu_target.currentData() == "ds4" else "xbox")
        combos = {}
        for row, key in enumerate(self.sample.buttons):
            grid.addWidget(label(names.get(key, key)), row, 0)
            combo = QComboBox()
            combo.addItem("Disabled", "")
            for output in OUTPUT_BUTTONS:
                if output != "touchpad" or self.emu_target.currentData() == "ds4":
                    combo.addItem(outputs.get(output, output), output)
            combo.setCurrentIndex(max(0, combo.findData(self.emu_bindings.get(key, key))))
            grid.addWidget(combo, row, 1)
            combos[key] = combo
        scroll.setWidget(body)
        layout.addWidget(scroll)
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(dialog.accept)
        footer.rejected.connect(dialog.reject)
        layout.addWidget(footer)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.emu_bindings = {key: combo.currentData() for key, combo in combos.items()}

    def start_emulation(self):
        if self.demo:
            self.notice("Emulation is disabled for simulated inputs.")
            return
        if not self.device:
            return
        if self.guided:
            self.notice("Finish or cancel the guided test before starting emulation.")
            return
        if not driver_status()["vigem"]:
            self.notice("ViGEmBus was not detected. See the official driver documentation before enabling virtual output.")
            return
        try:
            self.emulation_baseline = {device.instance_id for device in self.devices}
            self.emulation.start(self.device.instance_id, self.sample, self.emulation_settings())
            self.save_preference(emulation=self.emulation_settings())
            self.notice("Virtual output active. Keep Controller Lab open or minimized while playing.")
        except Exception as exc:
            self.emulation.error = str(exc)
            self.notice("Virtual output could not start: " + str(exc))
        self.sync_emulation_ui()

    def stop_emulation(self):
        source = self.emulation.source
        was_running = self.emulation.running
        self.emulation.stop()
        if self.feedback_owned and source is not None:
            self.backend.stop(source)
        self.feedback_owned = False
        if hasattr(self, "emu_start"):
            self.sync_emulation_ui()
        if was_running and hasattr(self, "status"):
            self.notice("Virtual output stopped and detached.")

    def update_output_route(self, *args):
        target = self.emulation.settings["target"] if self.emulation.running else self.emu_target.currentData()
        self.emu_route.set_state(self.device, target, self.emulation.running, self.demo)

    def sync_emulation_ui(self):
        running = self.emulation.running
        self.update_output_route()
        self.emu_form.setEnabled(not running)
        self.emu_start.setEnabled(not running and not self.demo and self.device is not None and self.sample.connected and self.sample.mapped)
        self.emu_stop.setEnabled(running)
        self.emu_stop.setVisible(running)
        self.device_list.setEnabled(not running)
        self.emu_state.setText(("Xbox 360 active" if self.emulation.settings["target"] == "x360" else "DualShock 4 active") if running else "Output unavailable" if self.emulation.error else "Stopped")
        self.sync_desktop_status()
        drivers = driver_status()
        readiness = getattr(self, "virtual_readiness", None)
        connection = "Virtual outputs checked: ready" if readiness and readiness.get("ready") else "Connection checked when you start"
        self.emu_driver.setPlainText("Simulated input · output disabled" if self.demo else
            "ViGEmBus: " + ("Detected" if drivers["vigem"] else "Not installed") + "\n" +
            ("Last start: " + self.emulation.error if self.emulation.error and not running else connection))

    def update_output(self, sample):
        was_running = self.emulation.running
        source = self.emulation.source
        self.emulation.update(self.device.instance_id if self.device else None, sample)
        feedback = self.emulation.feedback_due()
        if feedback is not None and self.device:
            if any(feedback):
                self.backend.rumble(self.device.instance_id, *feedback, 180)
                self.feedback_owned = True
            elif self.feedback_owned:
                self.backend.stop(self.device.instance_id)
                self.feedback_owned = False
        if was_running and not self.emulation.running:
            if self.feedback_owned and source is not None:
                self.backend.stop(source)
                self.feedback_owned = False
            self.sync_emulation_ui()
            self.notice("Virtual output stopped: " + (self.emulation.error or "input disconnected"))

    def filter_virtual_outputs(self, devices):
        current = {device.instance_id for device in devices}
        self.own_outputs.intersection_update(current)
        if self.emulation.running:
            for device in devices:
                if device.instance_id in self.emulation_baseline:
                    continue
                try:
                    raw = bytes.fromhex(device.guid)
                    pair = (int.from_bytes(raw[4:6], "little"), int.from_bytes(raw[8:10], "little"))
                    if pair in ((0x045e, 0x028e), (0x054c, 0x05c4)):
                        self.own_outputs.add(device.instance_id)
                except ValueError:
                    pass
        return [device for device in devices if device.instance_id not in self.own_outputs]

    def copy_application_path(self):
        path = Path(sys.executable)
        QApplication.clipboard().setText(str(path))
        self.notice("Executable path copied for the HidHide application allowlist.")

    def show_help(self):
        self.text_dialog("Help and troubleshooting", '<h2>Controller Lab</h2><h3>Test a controller</h3><p>Connect via USB or pair it in Windows. Choose Guided test for a checklist and a saved visual report. Pending inputs are not automatically faulty.</p><h3>Use an unrecognized controller</h3><p>Open Raw inputs, then Controller options → Map inputs. Use Listen to capture each input, review inversion and save. Profiles keep alternative assignments separate.</p><h3>Play through a virtual controller</h3><p>Choose Emulation, select Xbox 360 or DualShock 4 and press Start. Keep this app open or minimized. Output stops on input loss or exit. Only one virtual output is created at a time.</p><h3>Double input</h3><p>If a game sees both physical and virtual controllers, use HidHide. Allow ControllerLab.exe to read the physical device before hiding it from other applications. Do not hide the virtual output. The app never changes HidHide settings automatically.</p><h3>No response</h3><p>Check Compatibility and diagnostics. Other mappers or Steam Input may expose a different device. Battery, vibration and special features depend on the controller, connection and Windows driver.</p><h3>Scope</h3><p>Native Wii/GameCube adapter protocols, motion, touch coordinates, adaptive triggers, macros and keyboard/mouse output are not included. ViGEmBus is an upstream-retired optional driver; review its official documentation for your Windows configuration.</p>')
