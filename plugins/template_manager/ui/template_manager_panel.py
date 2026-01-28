#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Template Manager panel: Templates + Details on one row, Source (with Load from CM),
searchable Variables, Export; right side = device preview.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QLabel,
    QFormLayout,
    QAbstractItemView,
    QMessageBox,
    QFileDialog,
    QSplitter,
    QComboBox,
    QMenu,
)
from PySide6.QtGui import QTextCursor, QAction
from src.ui.plugin_ui_theme import mark_plugin_ui
from plugins.template_manager.core.template_engine import STANDARD_DEVICE_PROPERTIES
from plugins.template_manager.core.template_storage import default_template
from plugins.template_manager.ui.template_preview_widget import TemplatePreviewWidget
import uuid
import json
from datetime import datetime


def _collect_device_properties(device_manager):
    """Standard + custom properties from workspace devices. Mirrors Report Generator."""
    names = set()
    for d in (device_manager.get_devices() or []):
        for k in (d.get_properties() or {}).keys():
            names.add(k)
    standard = [p for p in STANDARD_DEVICE_PROPERTIES if p in names]
    custom = sorted(p for p in names if p not in STANDARD_DEVICE_PROPERTIES)
    return standard, custom


class TemplateManagerPanel(QWidget):
    """Templates + Details same row; Source (Load from CM); searchable Variables; Export; right = preview."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.plugin = plugin
        self.storage = plugin.storage
        self._templates = []
        self._current_id = None
        self._vars_full_list = []  # list of (prop_name, display_text) for filtering
        self._build_ui()
        self._refresh_templates_list()
        self._refresh_variables()
        self._refresh_preview_devices()
        self.preview_widget.selection_in_preview_triggered.connect(
            self._on_preview_selection_from_widget
        )

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(4, 4, 4, 4)
        main.setSpacing(4)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # —— Left: templates + details (stacked) ——
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        templates_group = QGroupBox("Templates")
        templates_layout = QVBoxLayout(templates_group)
        self.templates_list = QListWidget()
        # Let the global theme (theme.py) control background/selection colors
        # so this matches the Workspace Manager list appearance.
        self.templates_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.templates_list.currentItemChanged.connect(self._on_template_selected)
        self.templates_list.setMinimumWidth(160)
        self.templates_list.setMaximumHeight(140)
        templates_layout.addWidget(self.templates_list)
        btn_row = QHBoxLayout()
        for label, slot in [
            ("New", self._new_template),
            ("Duplicate", self._duplicate_template),
            ("Delete", self._delete_template),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        templates_layout.addLayout(btn_row)
        left_layout.addWidget(templates_group)

        details_group = QGroupBox("Template Details")
        details_layout = QFormLayout(details_group)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Template name")
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Description (optional)")
        details_layout.addRow("Name:", self.name_edit)
        details_layout.addRow("Description:", self.desc_edit)
        left_layout.addWidget(details_group)
        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # —— Middle: Source / Body + Variables ——
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)

        # Source / Body + Load from Command Manager
        source_group = QGroupBox("Source / Body")
        source_layout = QVBoxLayout(source_group)
        load_row = QHBoxLayout()
        self.load_cm_btn = QPushButton("Load from Command Manager…")
        self.load_cm_btn.clicked.connect(self._load_from_command_manager)
        load_row.addWidget(self.load_cm_btn)
        load_row.addStretch()
        source_layout.addLayout(load_row)
        self.body_edit = QTextEdit()
        self.body_edit.setPlaceholderText("Paste or type template text. Use {{property_name}} for device fields. Right-click to insert variables.")
        # Slightly smaller minimum height so the overall dialog can be more compact.
        self.body_edit.setMinimumHeight(80)
        self.body_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self.body_edit.customContextMenuRequested.connect(self._on_body_context_menu)
        source_layout.addWidget(self.body_edit)
        middle_layout.addWidget(source_group)

        # Variables (searchable)
        vars_group = QGroupBox("Variables")
        vars_layout = QVBoxLayout(vars_group)
        self.vars_help = QLabel("Available fields (use {{property_name}} in body):")
        self.vars_help.setWordWrap(True)
        vars_layout.addWidget(self.vars_help)
        self.vars_search = QLineEdit()
        self.vars_search.setPlaceholderText("Search variables…")
        self.vars_search.textChanged.connect(self._filter_variables)
        vars_layout.addWidget(self.vars_search)
        self.vars_list = QListWidget()
        self.vars_list.setMaximumHeight(100)
        self.vars_list.itemDoubleClicked.connect(self._insert_placeholder)
        vars_layout.addWidget(self.vars_list)
        insert_btn = QPushButton("Insert placeholder at cursor")
        insert_btn.clicked.connect(self._insert_placeholder_from_selection)
        vars_layout.addWidget(insert_btn)
        middle_layout.addWidget(vars_group)
        middle_layout.addStretch()
        splitter.addWidget(middle_widget)

        # —— Right: Preview ——
        self.preview_widget = TemplatePreviewWidget(self.plugin, self.body_edit, self)
        splitter.addWidget(self.preview_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        main.addWidget(splitter)
        # Export buttons and status label are created here but added to the
        # dialog layout so they can share a single bottom row with the Close
        # button.
        self.export_file_btn = QPushButton("Export template file…")
        self.export_file_btn.clicked.connect(self._export_template_file)
        self.send_cm_btn = QPushButton("Load into Command Manager")
        self.send_cm_btn.clicked.connect(self._load_into_command_manager_direct)
        self.export_cm_file_btn = QPushButton("Export for Command Manager (file)…")
        self.export_cm_file_btn.clicked.connect(self._open_export_dialog)
        self.batch_export_btn = QPushButton("Batch export…")
        self.batch_export_btn.clicked.connect(self._open_batch_export_dialog)
        self.status_label = QLabel("")
        self.status_label.setProperty("plugin_ui_muted", "true")

    def _refresh_preview_devices(self):
        self.preview_widget.refresh_devices()

    def _on_preview_selection_from_widget(self, plain):
        """When text is selected in the preview, select the same text in the body editor."""
        if not plain:
            return
        # Selects the first occurrence of the preview selection in the body; if the same text appears multiple times, only the first match is used.
        body = self.body_edit.toPlainText()
        pos = body.find(plain)
        if pos == -1:
            return
        ec = self.body_edit.textCursor()
        ec.setPosition(pos)
        ec.setPosition(pos + len(plain), QTextCursor.KeepAnchor)
        self.body_edit.setTextCursor(ec)
        self.body_edit.setFocus()

    def _on_body_context_menu(self, pos):
        """Right-click on body: show Insert variable submenu."""
        menu = QMenu(self.body_edit)
        insert_menu = menu.addMenu("Insert variable")
        dm = getattr(self.plugin, "device_manager", None)
        standard, custom = ([], []) if not dm else _collect_device_properties(dm)
        names = standard + custom if (standard or custom) else list(STANDARD_DEVICE_PROPERTIES)
        std_set = set(standard) if (standard or custom) else set(STANDARD_DEVICE_PROPERTIES)
        for name in names:
            label = f"{name} (standard)" if name in std_set else name
            action = QAction(label, self.body_edit)
            action.triggered.connect(lambda checked, n=name: self._insert_at_cursor(f"{{{{{n}}}}}"))
            insert_menu.addAction(action)
        menu.exec(self.body_edit.mapToGlobal(pos))

    def _load_from_command_manager(self):
        from plugins.template_manager.ui.command_output_picker import CommandOutputPickerDialog
        d = CommandOutputPickerDialog(self.plugin, self)
        if d.exec() and d.chosen_output() is not None:
            self.body_edit.setPlainText(d.chosen_output())

    def _filter_variables(self):
        q = (self.vars_search.text() or "").strip().lower()
        for i in range(self.vars_list.count()):
            item = self.vars_list.item(i)
            prop = (item.data(Qt.UserRole) or "").lower()
            text = (item.text() or "").lower()
            item.setHidden(bool(q) and q not in prop and q not in text)

    def _refresh_templates_list(self):
        self._templates = self.storage.ensure_loaded()
        self.templates_list.clear()
        for t in self._templates:
            name = (t.get("name") or "Unnamed").strip()
            desc = (t.get("description") or "").strip()[:40]
            label = f"{name}" + (f" — {desc}" if desc else "")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, t.get("id"))
            self.templates_list.addItem(item)
        self._update_status()

    def _current_template(self):
        if not self._current_id:
            return None
        for t in self._templates:
            if t.get("id") == self._current_id:
                return t
        return None

    def _on_template_selected(self, current, _previous):
        if not current:
            self._current_id = None
            self.name_edit.clear()
            self.desc_edit.clear()
            self.body_edit.clear()
            return
        self._current_id = current.data(Qt.UserRole)
        t = self._current_template()
        if not t:
            return
        self.name_edit.setText(t.get("name") or "")
        self.desc_edit.setText(t.get("description") or "")
        self.body_edit.setPlainText(t.get("body") or "")

    def _save_current_to_model(self):
        t = self._current_template()
        if not t:
            return
        t["name"] = self.name_edit.text().strip() or "Unnamed"
        t["description"] = self.desc_edit.text().strip()
        t["body"] = self.body_edit.toPlainText()
        t["updated_at"] = datetime.utcnow().isoformat() + "Z"
        if t.get("created_at") is None:
            t["created_at"] = t["updated_at"]
        self.storage.save(self._templates)
        self._refresh_templates_list()
        self._update_status()

    def _new_template(self):
        t = default_template()
        self._templates.append(t)
        self.storage.save(self._templates)
        self._refresh_templates_list()
        for i in range(self.templates_list.count()):
            if self.templates_list.item(i).data(Qt.UserRole) == t["id"]:
                self.templates_list.setCurrentRow(i)
                break
        self.name_edit.setText(t.get("name") or "")
        self.desc_edit.setText(t.get("description") or "")
        self.body_edit.setPlainText(t.get("body") or "")

    def _duplicate_template(self):
        t = self._current_template()
        if not t:
            return
        import copy
        new_t = copy.deepcopy(t)
        new_t["id"] = str(uuid.uuid4())
        new_t["name"] = (t.get("name") or "Template") + " (Copy)"
        new_t["created_at"] = datetime.utcnow().isoformat() + "Z"
        new_t["updated_at"] = new_t["created_at"]
        self._templates.append(new_t)
        self.storage.save(self._templates)
        self._refresh_templates_list()
        for i in range(self.templates_list.count()):
            if self.templates_list.item(i).data(Qt.UserRole) == new_t["id"]:
                self.templates_list.setCurrentRow(i)
                break

    def _delete_template(self):
        t = self._current_template()
        if not t:
            return
        if QMessageBox.question(
            self,
            "Delete Template",
            f"Delete template \"{t.get('name', 'Unnamed')}\"?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self._templates = [x for x in self._templates if x.get("id") != self._current_id]
        self.storage.save(self._templates)
        self._current_id = None
        self._refresh_templates_list()
        self.name_edit.clear()
        self.desc_edit.clear()
        self.body_edit.clear()

    def _refresh_variables(self):
        dm = getattr(self.plugin, "device_manager", None)
        self._vars_full_list = []
        self.vars_list.clear()
        if not dm:
            self.vars_help.setText("Available fields: (no device manager)")
            return
        standard, custom = _collect_device_properties(dm)
        for p in standard:
            self._vars_full_list.append((p, f"{p} (standard)"))
        for p in custom:
            self._vars_full_list.append((p, p))
        for prop, disp in self._vars_full_list:
            item = QListWidgetItem(disp)
            item.setData(Qt.UserRole, prop)
            self.vars_list.addItem(item)
        if self._vars_full_list:
            self.vars_help.setText("Search and double-click or use Insert. Use {{property_name}} in body.")
        else:
            self.vars_help.setText("No device properties. Add devices or use: id, alias, hostname, ip_address, …")
        self._filter_variables()

    def _insert_placeholder(self, item):
        name = item.data(Qt.UserRole) or (item.text() or "").split(" ")[0]
        self._insert_at_cursor(f"{{{{{name}}}}}")

    def _insert_placeholder_from_selection(self):
        item = self.vars_list.currentItem()
        if not item:
            return
        name = (item.data(Qt.UserRole) or "").strip() or (item.text() or "").strip().split("(")[0].strip()
        if name:
            self._insert_at_cursor(f"{{{{{name}}}}}")

    def _insert_at_cursor(self, text):
        self.body_edit.insertPlainText(text)

    def _update_status(self):
        n = len(self._templates)
        self.status_label.setText(f"{n} template(s)")

    def _export_template_file(self):
        self._save_current_to_model()
        selected = self._current_template()
        to_export = [selected] if selected else self._templates
        if not to_export:
            QMessageBox.information(self, "Export", "No templates to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export template file", "", "Template file (*.json);;All Files (*)"
        )
        if not path:
            return
        payload = {"version": 1, "templates": to_export}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            QMessageBox.information(self, "Export", f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export", f"Export failed: {e}")

    def _load_into_command_manager_direct(self):
        """Load the current template into Command Manager as a command set (one command per line). No dialog."""
        t = self._current_template()
        if not t:
            QMessageBox.information(
                self, "Load into Command Manager", "Select a template to load."
            )
            return
        current_id = self._current_id
        self._save_current_to_model()
        # Restore selection after refresh (refresh clears list and _current_id)
        for i in range(self.templates_list.count()):
            if self.templates_list.item(i).data(Qt.UserRole) == current_id:
                self.templates_list.setCurrentRow(i)
                break
        body = (t.get("body") or "").strip()
        if not body:
            QMessageBox.information(
                self, "Load into Command Manager", "Template has no commands."
            )
            return
        info = self.plugin.app.plugin_manager.get_plugin("command_manager")
        if not info or not getattr(info, "instance", None):
            QMessageBox.warning(
                self,
                "Load into Command Manager",
                "Command Manager plugin is not loaded.",
            )
            return
        cmd_mgr = info.instance
        # Prefill Command Manager's Custom Commands dialog instead of creating a saved set.
        if hasattr(cmd_mgr, "pending_custom_commands_text"):
            cmd_mgr.pending_custom_commands_text = body
        cmd_mgr.open_dialog()
        # Close Template Manager so only Command Manager is visible
        top = self.window()
        if top and top.isWindow():
            top.close()

    def _open_export_dialog(self):
        """Open Export dialog for scope/filters and Export for Command Manager (file)."""
        from plugins.template_manager.ui.export_dialog import ExportDialog
        self._save_current_to_model()
        to_export = self.get_selected_templates_for_export()
        if not to_export:
            QMessageBox.information(self, "Export", "No templates selected.")
            return
        d = ExportDialog(self.plugin, to_export, self)
        d.exec()

    def _open_batch_export_dialog(self, initial_devices=None):
        """Open batch export (expanded output for devices/group/subnet). initial_devices = list from context menu."""
        from plugins.template_manager.ui.batch_export_dialog import BatchExportDialog
        self._save_current_to_model()
        to_export = self.get_selected_templates_for_export()
        if not to_export:
            QMessageBox.information(self, "Batch export", "No templates selected.")
            return
        d = BatchExportDialog(self.plugin, to_export, initial_devices=initial_devices, parent=self)
        d.exec()

    def get_selected_templates_for_export(self):
        cur = self._current_template()
        if cur:
            return [cur]
        return self._templates
