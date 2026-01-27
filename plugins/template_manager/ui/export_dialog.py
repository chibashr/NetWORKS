#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Export dialog for Template Manager: scope (all/selected/group/subnet/tag), filters,
and actions: Load into Command Manager or Export for Command Manager (file).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QFileDialog,
    QAbstractItemView,
)

from src.ui.plugin_ui_theme import mark_plugin_ui
from plugins.template_manager.core.device_resolver import (
    DATA_SOURCE_LABELS,
    DATA_SOURCE_MAP,
    FILTER_OPERATORS,
    resolve_devices,
)
from plugins.template_manager.core.template_engine import render_template_text


class ExportDialog(QDialog):
    """Scope, filters, and Send to Command Manager or Export file."""

    def __init__(self, plugin, templates, parent=None):
        super().__init__(parent or plugin.main_window)
        mark_plugin_ui(self)
        self.setWindowTitle("Load into Command Manager")
        self.plugin = plugin
        self.templates = templates or []
        self._build_ui()
        self._on_source_changed(self.source_combo.currentText())

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Data source
        source_group = QGroupBox("Data Source")
        source_layout = QFormLayout(source_group)
        self.source_combo = QComboBox()
        self.source_combo.addItems(DATA_SOURCE_LABELS)
        self.source_combo.currentTextChanged.connect(self._on_source_changed)
        self.group_combo = QComboBox()
        groups = []
        try:
            for g in (self.plugin.device_manager.get_groups() or []):
                n = getattr(g, "name", None) or str(g)
                if n:
                    groups.append(n)
        except Exception:
            pass
        self.group_combo.addItems(sorted(set(groups)))
        self.subnet_edit = QLineEdit()
        self.subnet_edit.setPlaceholderText("e.g. 192.168.1.0/24")
        self.tag_edit = QLineEdit()
        self.tag_edit.setPlaceholderText("e.g. core")
        source_layout.addRow("Source:", self.source_combo)
        source_layout.addRow("Group:", self.group_combo)
        source_layout.addRow("Subnet:", self.subnet_edit)
        source_layout.addRow("Tag:", self.tag_edit)
        layout.addWidget(source_group)

        # Filters
        filters_group = QGroupBox("Filters")
        filters_layout = QVBoxLayout(filters_group)
        logic_row = QHBoxLayout()
        logic_row.addWidget(QLabel("Combine with:"))
        self.filter_logic_combo = QComboBox()
        self.filter_logic_combo.addItems(["AND", "OR"])
        logic_row.addWidget(self.filter_logic_combo)
        logic_row.addStretch()
        filters_layout.addLayout(logic_row)
        self.filters_table = QTableWidget(0, 3)
        self.filters_table.setHorizontalHeaderLabels(["Property", "Operator", "Value"])
        self.filters_table.horizontalHeader().setStretchLastSection(True)
        filters_layout.addWidget(self.filters_table)
        f_btn = QHBoxLayout()
        self.add_filter_btn = QPushButton("+ Add Filter")
        self.add_filter_btn.clicked.connect(self._add_filter_row)
        self.remove_filter_btn = QPushButton("Remove Selected")
        self.remove_filter_btn.clicked.connect(self._remove_filter_rows)
        f_btn.addWidget(self.add_filter_btn)
        f_btn.addWidget(self.remove_filter_btn)
        f_btn.addStretch()
        filters_layout.addLayout(f_btn)
        layout.addWidget(filters_group)

        # Actions
        actions_layout = QHBoxLayout()
        self.send_cm_btn = QPushButton("Load into Command Manager")
        self.send_cm_btn.clicked.connect(self._load_into_command_manager)
        self.export_file_btn = QPushButton("Export for Command Manager (file)…")
        self.export_file_btn.clicked.connect(self._export_for_command_manager)
        actions_layout.addWidget(self.send_cm_btn)
        actions_layout.addWidget(self.export_file_btn)
        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: var(--text-muted, #666);")
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_source_changed(self, source_label):
        st = DATA_SOURCE_MAP.get(source_label, "all")
        self.group_combo.setEnabled(st == "group")
        self.subnet_edit.setEnabled(st == "subnet")
        self.tag_edit.setEnabled(st == "tag")

    def _add_filter_row(self):
        row = self.filters_table.rowCount()
        self.filters_table.insertRow(row)
        self.filters_table.setItem(row, 0, QTableWidgetItem(""))
        op = QComboBox()
        op.addItems(FILTER_OPERATORS)
        self.filters_table.setCellWidget(row, 1, op)
        self.filters_table.setItem(row, 2, QTableWidgetItem(""))

    def _remove_filter_rows(self):
        rows = sorted({i.row() for i in self.filters_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.filters_table.removeRow(r)

    def _get_data_source(self):
        label = self.source_combo.currentText()
        st = DATA_SOURCE_MAP.get(label, "all")
        return {
            "type": st,
            "group": self.group_combo.currentText().strip(),
            "subnet": self.subnet_edit.text().strip(),
            "tag": self.tag_edit.text().strip(),
        }

    def _get_filters(self):
        out = []
        for row in range(self.filters_table.rowCount()):
            prop = self.filters_table.item(row, 0)
            op_w = self.filters_table.cellWidget(row, 1)
            val = self.filters_table.item(row, 2)
            prop_s = (prop.text() or "").strip() if prop else ""
            if not prop_s:
                continue
            op_s = op_w.currentText() if op_w else "equals"
            val_s = (val.text() or "").strip() if val else ""
            out.append({"property": prop_s, "operator": op_s, "value": val_s})
        return out

    def _resolve_devices(self):
        dm = self.plugin.device_manager
        ds = self._get_data_source()
        flt = self._get_filters()
        logic = self.filter_logic_combo.currentText() or "AND"
        return resolve_devices(dm, ds, filter_logic=logic, filters=flt)

    def _build_command_sets(self, devices, templates):
        """Return list of (device_type, firmware_version, list of Command dicts)."""
        from plugins.command_manager.utils.command_set import Command, CommandSet
        sets = []
        for t in templates:
            name = (t.get("name") or "Template").strip()
            body = (t.get("body") or "").strip()
            desc = (t.get("description") or "").strip()
            device_type = f"Template: {name}"
            firmware_version = "1.0"
            commands = []
            for idx, device in enumerate(devices, start=1):
                ctx = dict(device.get_properties() or {})
                ctx["index"] = idx
                ctx["total"] = len(devices)
                expanded = render_template_text(body, ctx)
                alias = device.get_property("alias") or device.get_property("hostname") or f"Device {idx}"
                commands.append(Command(expanded, str(alias), desc or f"From template: {name}"))
            if commands:
                cs = CommandSet(device_type, firmware_version, commands)
                sets.append(cs)
        return sets

    def _load_into_command_manager(self):
        if not self.templates:
            QMessageBox.warning(self, "Load into Command Manager", "No templates selected.")
            return
        devices = self._resolve_devices()
        if not devices:
            QMessageBox.warning(
                self,
                "Load into Command Manager",
                "No devices matched the selected source and filters.",
            )
            return
        info = self.plugin.app.plugin_manager.get_plugin("command_manager")
        if not info or not getattr(info, "instance", None):
            QMessageBox.warning(
                self,
                "Load into Command Manager",
                "Command Manager plugin is not loaded. Use \"Export for Command Manager (file)\" and import that file in Command Manager.",
            )
            return
        cmd_mgr = info.instance
        sets = self._build_command_sets(devices, self.templates)
        for cs in sets:
            cmd_mgr.add_command_set(cs)
        QMessageBox.information(
            self,
            "Load into Command Manager",
            f"Added {len(sets)} template set(s) for {len(devices)} device(s). Open Command Manager to run them.",
        )
        self.status_label.setText(f"Sent {len(sets)} set(s) to Command Manager.")

    def _export_for_command_manager(self):
        """Write Command Manager–style JSON (device_type, firmware_version, commands) to file."""
        if not self.templates:
            QMessageBox.warning(self, "Export", "No templates selected.")
            return
        devices = self._resolve_devices()
        if not devices:
            QMessageBox.warning(
                self,
                "Export",
                "No devices matched the selected source and filters.",
            )
            return
        sets = self._build_command_sets(devices, self.templates)
        if not sets:
            QMessageBox.warning(self, "Export", "No command sets to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export for Command Manager",
            "",
            "Command set (*.json);;All Files (*)",
        )
        if not path:
            return
        try:
            import json
            # Command Manager import expects one set per file (device_type, firmware_version, commands).
            data = sets[0].to_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            msg = f"Exported to {path}. Import this file in Command Manager."
            if len(sets) > 1:
                msg += f" (Exported first of {len(sets)} template sets; export again for others.)"
            QMessageBox.information(self, "Export", msg)
        except Exception as e:
            QMessageBox.critical(self, "Export", f"Export failed: {e}")
