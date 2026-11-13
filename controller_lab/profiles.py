"""Named app-local presets; selection never claims a unique hardware identity."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QDialogButtonBox, QInputDialog, QMessageBox, QLineEdit
from .widgets import label, button


class NewProfileDialog(QDialog):
    def __init__(self, create_profile, parent=None):
        super().__init__(parent)
        self.create_profile, self.profile_id = create_profile, None
        self.setWindowTitle("New controller profile")
        self.resize(460, 300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        layout.addWidget(label("New profile", "Title"))
        description = label("Copy the current configuration into a separate profile. Creating it selects the new profile and stops emulation.", "Muted", True)
        description.setMinimumHeight(40)
        layout.addWidget(description)
        layout.addWidget(label("Profile name", "Small"))
        self.name = QLineEdit()
        self.name.setMaxLength(80)
        self.name.setPlaceholderText("e.g. Racing or Swapped buttons")
        self.name.setAccessibleName("New controller profile name")
        layout.addWidget(self.name)
        self.error = label("", "Small", True)
        self.error.setMinimumHeight(28)
        layout.addWidget(self.error)
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.create_button = footer.button(QDialogButtonBox.StandardButton.Save)
        self.create_button.setText("Create profile")
        self.create_button.setObjectName("Primary")
        self.create_button.setDefault(True)
        self.create_button.setEnabled(False)
        self.name.textChanged.connect(self.name_changed)
        footer.accepted.connect(self.create)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)
        self.name.setFocus()

    def name_changed(self, text):
        self.error.clear()
        self.create_button.setEnabled(bool(text.strip()))

    def create(self):
        try:
            self.profile_id = self.create_profile(self.name.text())
        except (ValueError, OSError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class ProfilesDialog(QDialog):
    def __init__(self, store, guid, parent=None, current_settings=None):
        super().__init__(parent)
        self.store, self.guid = store, guid
        self.current_settings = current_settings
        self.setWindowTitle("Controller profiles")
        self.resize(560, 270)
        layout = QVBoxLayout(self)
        layout.addWidget(label("Controller profiles", "Title"))
        layout.addWidget(label("Save separate mappings, overlays and emulation settings. Select one here or associate it with a game under Game profiles. Identical controllers may share a device GUID.", "Muted", True))
        self.combo = QComboBox()
        layout.addWidget(self.combo)
        actions = QHBoxLayout()
        actions.addWidget(button("New from current…", self.create))
        actions.addWidget(button("Rename…", self.rename))
        actions.addWidget(button("Delete…", self.delete))
        layout.addLayout(actions)
        layout.addStretch()
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.accept)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)
        self.refresh(store.active_profile(guid))

    def refresh(self, selected=""):
        self.combo.clear()
        self.combo.addItem("Default", "")
        for key, name in self.store.profiles(self.guid):
            self.combo.addItem(name, key)
        self.combo.setCurrentIndex(max(0, self.combo.findData(selected)))

    def create(self):
        name, accepted = QInputDialog.getText(self, "New profile", "Profile name")
        if accepted:
            try:
                self.refresh(self.store.create_profile(self.guid, name, settings=self.current_settings))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Profile could not be saved", str(exc))

    def rename(self):
        key = self.combo.currentData()
        if not key:
            return
        name, accepted = QInputDialog.getText(self, "Rename profile", "Profile name", text=self.combo.currentText())
        if accepted:
            try:
                self.store.rename_profile(self.guid, key, name)
                self.refresh(key)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Profile could not be saved", str(exc))

    def delete(self):
        key = self.combo.currentData()
        if not key:
            return
        if QMessageBox.question(self, "Delete profile", "Delete this preset? Saved sessions are kept.") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete_profile(self.guid, key)
            self.refresh()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Profile could not be deleted", str(exc))
