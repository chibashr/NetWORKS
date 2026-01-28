#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Batch export dialog: export template(s) with variables applied for
selected devices / group / subnet. Collapsible filters, devices list,
missing-data warnings, and sample preview before export.
"""

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QComboBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QFileDialog,
    QRadioButton,
    QTextEdit,
    QSplitter,
    QScrollArea,
    QWidget,
    QAbstractItemView,
)

from src.ui.plugin_ui_theme import mark_plugin_ui
from src.ui.plugin_widgets import CollapsibleSection
from plugins.template_manager.core.device_resolver import (
    DATA_SOURCE_LABELS,
    DATA_SOURCE_MAP,
    FILTER_OPERATORS,
    resolve_devices,
)
from plugins.template_manager.core.template_engine import render_template_text
from plugins.template_manager.core.device_utils import device_display_name, group_names_for_combo


def _placeholders_in_body(body):
    """Return set of placeholder property names in template body."""
    pattern = re.compile(r"\{\{\s*([^}]+)\s*\}\}")
    return set(m.group(1).strip() for m in pattern.finditer(body or ""))


class BatchExportDialog(QDialog):
    """Export expanded template output for devices (scope or initial_devices)."""

    def __init__(self, plugin, templates, initial_devices=None, parent=None):
        super().__init__(parent or plugin.main_window)
        mark_plugin_ui(self)
        self.setWindowTitle("Batch export")
        self.plugin = plugin
        self.templates = templates or []
        self.initial_devices = list(initial_devices) if initial_devices else None
        self._devices = []
        self.setMinimumSize(1100, 620)
        self.resize(1200, 700)
        self._build_ui()
        self._on_source_changed(self.source_combo.currentText())
        self._refresh_preview()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        if self.initial_devices:
            main_layout.addWidget(
                QLabel(f"Exporting for {len(self.initial_devices)} selected device(s).")
            )

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # —— Left: form ——
        left_widget = QWidget()
        left_widget.setMinimumWidth(480)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(480)
        form_widget = QWidget()
        form_widget.setMinimumWidth(460)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)

        # Data source
        source_group = QGroupBox("Data Source")
        source_layout = QFormLayout(source_group)
        self.source_combo = QComboBox()
        self.source_combo.addItems(DATA_SOURCE_LABELS)
        self.source_combo.currentTextChanged.connect(self._on_source_changed)
        self.source_combo.currentTextChanged.connect(self._refresh_preview)
        if self.initial_devices:
            self.source_combo.setCurrentText("Selected Devices")
            self.source_combo.setEnabled(False)
        self.group_combo = QComboBox()
        self.group_combo.addItems(group_names_for_combo(self.plugin.device_manager))
        self.group_combo.currentTextChanged.connect(self._refresh_preview)
        self.subnet_edit = QLineEdit()
        self.subnet_edit.setPlaceholderText("e.g. 192.168.1.0/24")
        self.subnet_edit.textChanged.connect(self._refresh_preview)
        self.tag_edit = QLineEdit()
        self.tag_edit.setPlaceholderText("e.g. core")
        self.tag_edit.textChanged.connect(self._refresh_preview)
        source_layout.addRow("Source:", self.source_combo)
        source_layout.addRow("Group:", self.group_combo)
        source_layout.addRow("Subnet:", self.subnet_edit)
        source_layout.addRow("Tag:", self.tag_edit)
        form_layout.addWidget(source_group)

        # Filters (collapsible, initially collapsed)
        self.filters_section = CollapsibleSection("Filters", expanded=False)
        self.filter_logic_combo = QComboBox()
        self.filter_logic_combo.addItems(["AND", "OR"])
        self.filter_logic_combo.currentTextChanged.connect(self._refresh_preview)
        logic_row = QHBoxLayout()
        logic_row.addWidget(QLabel("Combine with:"))
        logic_row.addWidget(self.filter_logic_combo)
        logic_row.addStretch()
        self.filters_section.content_layout.addLayout(logic_row)
        self.filters_table = QTableWidget(0, 3)
        self.filters_table.setHorizontalHeaderLabels(["Property", "Operator", "Value"])
        self.filters_table.horizontalHeader().setStretchLastSection(True)
        self.filters_table.setMaximumHeight(120)
        self.filters_table.itemChanged.connect(self._refresh_preview)
        self.filters_section.content_layout.addWidget(self.filters_table)
        f_btn = QHBoxLayout()
        add_f = QPushButton("+ Add Filter")
        add_f.clicked.connect(self._add_filter_row)
        rem_f = QPushButton("Remove Selected")
        rem_f.clicked.connect(self._remove_filter_rows)
        f_btn.addWidget(add_f)
        f_btn.addWidget(rem_f)
        f_btn.addStretch()
        self.filters_section.content_layout.addLayout(f_btn)
        form_layout.addWidget(self.filters_section)

        # Output format
        out_group = QGroupBox("Output")
        out_layout = QVBoxLayout(out_group)
        self.one_per_device_radio = QRadioButton("One file per device")
        self.one_per_device_radio.setChecked(True)
        self.one_combined_radio = QRadioButton("One combined file (sections per device)")
        out_layout.addWidget(self.one_per_device_radio)
        out_layout.addWidget(self.one_combined_radio)
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Path:"))
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Directory or file")
        path_row.addWidget(self.path_edit, 1)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(browse_btn)
        out_layout.addLayout(path_row)
        form_layout.addWidget(out_group)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._do_export)
        form_layout.addWidget(export_btn)

        form_layout.addStretch()
        scroll.setWidget(form_widget)
        left_layout.addWidget(scroll)
        splitter.addWidget(left_widget)

        # —— Right: scrollable device list + one-device preview ——
        right_widget = QWidget()
        right_widget.setMinimumWidth(520)
        preview_layout = QVBoxLayout(right_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        preview_group = QGroupBox("Preview")
        preview_inner = QVBoxLayout(preview_group)
        preview_inner.addWidget(QLabel("Devices to export:"))
        self.devices_list = QListWidget()
        self.devices_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.devices_list.setMinimumHeight(120)
        self.devices_list.currentRowChanged.connect(self._on_device_selected)
        preview_inner.addWidget(self.devices_list)
        preview_inner.addWidget(QLabel("Missing data (empty placeholders):"))
        self.missing_label = QLabel("")
        self.missing_label.setWordWrap(True)
        self.missing_label.setProperty("plugin_ui_warning", "true")
        preview_inner.addWidget(self.missing_label)
        preview_inner.addWidget(QLabel("Preview for selected device (first template):"))
        self.sample_text = QTextEdit()
        self.sample_text.setReadOnly(True)
        self.sample_text.setPlaceholderText("Select a device above to see its export preview.")
        preview_inner.addWidget(self.sample_text)
        preview_layout.addWidget(preview_group)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _on_source_changed(self, source_label):
        st = DATA_SOURCE_MAP.get(source_label, "all")
        self.group_combo.setEnabled(st == "group" and not self.initial_devices)
        self.subnet_edit.setEnabled(st == "subnet" and not self.initial_devices)
        self.tag_edit.setEnabled(st == "tag" and not self.initial_devices)

    def _add_filter_row(self):
        row = self.filters_table.rowCount()
        self.filters_table.insertRow(row)
        self.filters_table.setItem(row, 0, QTableWidgetItem(""))
        op = QComboBox()
        op.addItems(FILTER_OPERATORS)
        op.currentTextChanged.connect(self._refresh_preview)
        self.filters_table.setCellWidget(row, 1, op)
        self.filters_table.setItem(row, 2, QTableWidgetItem(""))
        self._refresh_preview()

    def _remove_filter_rows(self):
        rows = sorted({i.row() for i in self.filters_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.filters_table.removeRow(r)
        self._refresh_preview()

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
        if self.initial_devices is not None:
            return list(self.initial_devices)
        dm = self.plugin.device_manager
        ds = self._get_data_source()
        flt = self._get_filters()
        logic = self.filter_logic_combo.currentText() or "AND"
        return resolve_devices(dm, ds, filter_logic=logic, filters=flt)

    def _on_device_selected(self, row):
        """Show one-device preview for the selected row in the devices list."""
        if row < 0 or row >= len(self._devices):
            self.sample_text.setPlainText("")
            return
        device = self._devices[row]
        ctx = dict(device.get_properties() or {})
        ctx["index"] = row + 1
        ctx["total"] = len(self._devices)
        for t in self.templates:
            body = (t.get("body") or "").strip()
            if not body:
                continue
            out = render_template_text(body, ctx)
            self.sample_text.setPlainText(out)
            return
        self.sample_text.setPlainText("(No template body to preview)")

    def _refresh_preview(self):
        devices = self._resolve_devices()
        self._devices = list(devices)
        n = len(self._devices)

        self.devices_list.clear()
        if n == 0:
            self.missing_label.setText("")
            self.sample_text.setPlainText("(No devices matched)")
            return

        for d in self._devices:
            self.devices_list.addItem(QListWidgetItem(device_display_name(d)))

        # Missing data: for each placeholder in templates, which devices have empty?
        missing_parts = []
        for t in self.templates:
            body = (t.get("body") or "").strip()
            placeholders = _placeholders_in_body(body)
            for prop in placeholders:
                empty_devices = [
                    device_display_name(d)
                    for d in self._devices
                    if not (d.get_property(prop, "") if hasattr(d, "get_property") else (d.get_properties() or {}).get(prop, ""))
                ]
                if empty_devices:
                    missing_parts.append(
                        f"{{{{{prop}}}}} empty for: {', '.join(empty_devices[:5])}"
                        + (f" (+{len(empty_devices) - 5} more)" if len(empty_devices) > 5 else "")
                    )
        if missing_parts:
            self.missing_label.setText("Missing data: " + "; ".join(missing_parts[:3]) + ("; …" if len(missing_parts) > 3 else ""))
        else:
            self.missing_label.setText("")

        # Select first device and show its one-device preview
        self.devices_list.blockSignals(True)
        self.devices_list.setCurrentRow(0)
        self.devices_list.blockSignals(False)
        self._on_device_selected(0)

    def _browse_path(self):
        if self.one_combined_radio.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "Export combined file", "", "Text (*.txt);;All Files (*)"
            )
            if path:
                self.path_edit.setText(path)
        else:
            path = QFileDialog.getExistingDirectory(self, "Export directory")
            if path:
                self.path_edit.setText(path)

    def _do_export(self):
        if not self.templates:
            QMessageBox.warning(self, "Batch export", "No templates selected.")
            return
        devices = self._resolve_devices()
        if not devices:
            QMessageBox.warning(
                self, "Batch export", "No devices matched the selected source and filters."
            )
            return
        path = self.path_edit.text().strip()
        if not path:
            self._browse_path()
            path = self.path_edit.text().strip()
        if not path:
            return
        combined = self.one_combined_radio.isChecked()
        import os
        try:
            written = 0
            base_dir = path if os.path.isdir(path) else (os.path.dirname(path) or ".")
            if not combined:
                if not os.path.isdir(path):
                    os.makedirs(path, exist_ok=True)
                base_dir = path if os.path.isdir(path) else base_dir
            for t in self.templates:
                name = (t.get("name") or "template").strip().replace("/", "-").replace("\\", "-")
                body = (t.get("body") or "").strip()
                if not body:
                    continue
                if combined:
                    lines = []
                    for idx, device in enumerate(devices, start=1):
                        ctx = dict(device.get_properties() or {})
                        ctx["index"] = idx
                        ctx["total"] = len(devices)
                        lines.append(f"--- {device_display_name(device)} ---")
                        lines.append(render_template_text(body, ctx))
                    if lines:
                        if os.path.isdir(path) or (len(self.templates) > 1):
                            filepath = os.path.join(base_dir, f"{name}.txt")
                        else:
                            filepath = path if path.endswith(".txt") else (path + ".txt")
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write("\n\n".join(lines))
                        written += 1
                else:
                    dirpath = base_dir if os.path.isdir(base_dir) else path
                    if not os.path.isdir(dirpath):
                        os.makedirs(dirpath, exist_ok=True)
                    for device in devices:
                        ctx = dict(device.get_properties() or {})
                        ctx["index"] = 1
                        ctx["total"] = 1
                        out = render_template_text(body, ctx)
                        safe = device_display_name(device).replace("/", "-").replace("\\", "-")
                        filepath = os.path.join(dirpath, f"{name}_{safe}.txt")
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(out)
                        written += 1
            QMessageBox.information(
                self, "Batch export", f"Exported {written} file(s)."
            )
        except Exception as e:
            QMessageBox.critical(self, "Batch export", f"Export failed: {e}")
