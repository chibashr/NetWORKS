# -*- coding: utf-8 -*-
"""
Report Builder widget: form, preview, export. Uses core report_engine for execution.
"""

import csv
import datetime
import html
import io
import json
import uuid
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)
from src.ui.plugin_ui_theme import mark_plugin_ui
from src.ui.theme import get_theme_tokens

from core.constants import (
    DATA_SOURCE_LABELS,
    DATA_SOURCE_MAP,
    DATA_SOURCE_REVERSE,
    EXPORT_FORMATS,
    FILTER_OPERATORS,
    MODE_LABELS,
    MODE_MAP,
    MODE_REVERSE,
    STANDARD_DEVICE_PROPERTIES,
    TRANSFORM_TYPES,
    default_report_definition,
)
from core.report_engine import (
    apply_filters,
    build_rows,
    render_table_report,
    render_template_report,
    resolve_devices,
)
from core.transforms import build_transform_map

from ui.manage_reports_dialog import show_manage_reports_dialog
from ui.report_builder_ui_builder import build_report_builder_ui
from ui.report_preview_helpers import render_csv_preview_html, render_json_preview_html


class ReportBuilderWidget(QWidget):
    report_saved = Signal()

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.storage = plugin.storage
        self.reports = []
        self.current_report_id = None
        self._workspace = None
        self._use_all_columns = False
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._refresh_preview_from_form)

        self._build_ui()
        self.refresh_metadata()
        self.load_reports()

    def _build_ui(self):
        build_report_builder_ui(self)

    def refresh_metadata(self):
        self.storage.ensure_loaded()
        if self._workspace != self.plugin.device_manager.current_workspace:
            self.load_reports()
        self.group_combo.clear()
        groups = [group.name for group in self.plugin.device_manager.get_groups()]
        groups = sorted(set(groups))
        self.group_combo.addItems(groups)
        self.update_sort_options()
        if self.mode_combo.currentText() == "Template":
            self._refresh_template_properties()
        else:
            self._refresh_available_columns_list()

    def load_reports(self):
        self.reports = self.storage.ensure_loaded()
        self._workspace = self.plugin.device_manager.current_workspace
        if not self.reports:
            self.create_report()
        else:
            if not self.current_report_id or not self._find_report(self.current_report_id):
                self.current_report_id = self.reports[0].get("id")
            report = self._find_report(self.current_report_id)
            if report:
                self.load_report_into_form(report)
        self._schedule_preview()

    def _collect_device_properties(self):
        properties = set()
        devices = self.plugin.device_manager.get_devices()
        for device in devices:
            for key in device.get_properties().keys():
                properties.add(key)
        return sorted(properties)

    def _column_names_in_use(self):
        names = set()
        for row in range(self.columns_list.count()):
            item = self.columns_list.item(row)
            data = item.data(Qt.UserRole) or {}
            name = (data.get("name") or "").strip()
            if name:
                names.add(name)
        return names

    def _available_transform_targets(self):
        targets = []
        seen = set()
        for row in range(self.columns_list.count()):
            item = self.columns_list.item(row)
            data = item.data(Qt.UserRole) or {}
            name = (data.get("name") or "").strip()
            if name and name not in seen:
                targets.append(name)
                seen.add(name)
        for prop in self._collect_device_properties():
            if prop not in seen:
                targets.append(prop)
                seen.add(prop)
        return targets

    def _format_column_label(self, column_data):
        name = (column_data.get("name") or "").strip()
        if not name:
            return ""
        label = name
        if column_data.get("type") == "computed":
            label = f"{label} (computed)"
        transforms = [t.get("transform", "") for t in column_data.get("transformations", []) if t.get("transform")]
        if transforms:
            label = f"{label} (transform: {', '.join(transforms)})"
        return label

    def _add_column_item(self, column_data):
        name = (column_data.get("name") or "").strip()
        if not name:
            return
        item = QListWidgetItem(self._format_column_label(column_data))
        item.setData(Qt.UserRole, column_data)
        self.columns_list.addItem(item)

    def _find_column_item(self, name):
        if not name:
            return None
        for row in range(self.columns_list.count()):
            item = self.columns_list.item(row)
            data = item.data(Qt.UserRole) or {}
            if (data.get("name") or "").strip() == name:
                return item
        return None

    def _append_transformation_to_item(self, item, transform_data):
        data = item.data(Qt.UserRole) or {}
        transforms = data.get("transformations") or []
        transforms.append(transform_data)
        data["transformations"] = transforms
        item.setData(Qt.UserRole, data)
        item.setText(self._format_column_label(data))

    def _on_mode_changed(self, mode_label):
        mode = MODE_MAP.get(mode_label, "table")
        self.table_controls_group.setVisible(mode == "table")
        self.sort_group.setEnabled(mode == "table")
        self.wizard_tabs.setEnabled(mode == "table")
        self.template_group.setVisible(mode == "template")
        if mode == "template":
            self._refresh_template_properties()
        else:
            self._refresh_available_columns_list()

    def _get_standard_and_custom_properties(self):
        """Return (standard_props, custom_props) for display in template editor."""
        all_props = self._collect_device_properties()
        standard = [p for p in STANDARD_DEVICE_PROPERTIES if p in all_props]
        custom = sorted(p for p in all_props if p not in STANDARD_DEVICE_PROPERTIES)
        return standard, custom

    def _refresh_template_properties(self):
        """Update the template editor's list of available properties."""
        standard, custom = self._get_standard_and_custom_properties()
        parts = []
        if standard:
            parts.append("Standard: " + ", ".join(standard))
        if custom:
            parts.append("Custom: " + ", ".join(custom))
        self.template_properties_label.setText("\n".join(parts) if parts else "No device properties available.")

    def _refresh_available_columns_list(self):
        """Populate Available Fields from standard and custom device properties."""
        self.available_columns_list.clear()
        standard, custom = self._get_standard_and_custom_properties()
        used = self._column_names_in_use()
        for name in standard:
            if name not in used:
                item = QListWidgetItem(f"{name} (Standard)")
                item.setData(Qt.UserRole, name)
                self.available_columns_list.addItem(item)
        for name in custom:
            if name not in used:
                item = QListWidgetItem(f"{name} (Custom)")
                item.setData(Qt.UserRole, name)
                self.available_columns_list.addItem(item)
        self._filter_available_columns()

    def _filter_available_columns(self):
        """Show/hide available columns by search text."""
        q = (self.column_search_edit.text() or "").strip().lower()
        for i in range(self.available_columns_list.count()):
            item = self.available_columns_list.item(i)
            name = (item.data(Qt.UserRole) or "")
            text = (item.text() or "").lower()
            item.setHidden(bool(q) and q not in text and q not in name.lower())

    def _add_available_column_to_selected(self, list_item):
        """Add one available field to selected (double-click)."""
        name = (list_item.data(Qt.UserRole) or "").strip()
        if not name or self._find_column_item(name):
            return
        self._use_all_columns = False
        self._add_column_item({"type": "existing", "name": name, "transformations": [], "visible": True, "header": ""})
        self.update_sort_options()
        self._refresh_available_columns_list()
        self._schedule_preview()

    def _add_selected_available_to_columns(self):
        """Add selected available fields to selected columns."""
        for item in self.available_columns_list.selectedItems():
            name = (item.data(Qt.UserRole) or "").strip()
            if name and not self._find_column_item(name):
                self._use_all_columns = False
                self._add_column_item({"type": "existing", "name": name, "transformations": [], "visible": True, "header": ""})
        self.update_sort_options()
        self._refresh_available_columns_list()
        self._schedule_preview()

    def _add_all_available_columns(self):
        """Add all visible available fields to selected columns."""
        for i in range(self.available_columns_list.count()):
            item = self.available_columns_list.item(i)
            if item.isHidden():
                continue
            name = (item.data(Qt.UserRole) or "").strip()
            if name and not self._find_column_item(name):
                self._use_all_columns = False
                self._add_column_item({"type": "existing", "name": name, "transformations": [], "visible": True, "header": ""})
        self.update_sort_options()
        self._refresh_available_columns_list()
        self._schedule_preview()

    def _remove_all_columns(self):
        """Remove all selected columns."""
        self.columns_list.clear()
        self._use_all_columns = True
        self.update_sort_options()
        self._refresh_available_columns_list()
        self._schedule_preview()

    def _on_selected_column_changed(self):
        """Sync visibility/header controls to the first selected column."""
        items = self.columns_list.selectedItems()
        if not items:
            self.column_visible_check.setEnabled(False)
            self.column_header_edit.setEnabled(False)
            self.column_visible_check.blockSignals(True)
            self.column_header_edit.blockSignals(True)
            self.column_visible_check.setChecked(True)
            self.column_header_edit.clear()
            self.column_visible_check.blockSignals(False)
            self.column_header_edit.blockSignals(False)
            return
        data = items[0].data(Qt.UserRole) or {}
        self.column_visible_check.setEnabled(True)
        self.column_header_edit.setEnabled(True)
        self.column_visible_check.blockSignals(True)
        self.column_header_edit.blockSignals(True)
        self.column_visible_check.setChecked(data.get("visible", True))
        self.column_header_edit.setText((data.get("header") or "").strip())
        self.column_visible_check.blockSignals(False)
        self.column_header_edit.blockSignals(False)

    def _apply_column_options_to_selection(self):
        """Apply visible/header from controls to the first selected column."""
        items = self.columns_list.selectedItems()
        if not items:
            return
        item = items[0]
        data = item.data(Qt.UserRole) or {}
        data["visible"] = self.column_visible_check.isChecked()
        data["header"] = (self.column_header_edit.text() or "").strip()
        item.setData(Qt.UserRole, data)
        self._schedule_preview()

    def _on_source_changed(self, source_label):
        source_type = DATA_SOURCE_MAP.get(source_label, "all")
        self.group_combo.setEnabled(source_type == "group")
        self.subnet_edit.setEnabled(source_type == "subnet")
        self.tag_edit.setEnabled(source_type == "tag")

    def _find_report(self, report_id):
        for report in self.reports:
            if report.get("id") == report_id:
                return report
        return None

    def create_report(self):
        report = default_report_definition()
        self.reports.append(report)
        self.storage.save(self.reports)
        self.load_reports()
        self._select_report(report["id"])

    def duplicate_report(self):
        report = self._get_current_report()
        if not report:
            return
        new_report = json.loads(json.dumps(report))
        new_report["id"] = str(uuid.uuid4())
        new_report["name"] = f"{report.get('name', 'Report')} (Copy)"
        self.reports.append(new_report)
        self.storage.save(self.reports)
        self.load_reports()
        self._select_report(new_report["id"])

    def delete_report(self):
        report = self._get_current_report()
        if not report:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Report",
            f"Delete report '{report.get('name', 'Report')}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.reports = [r for r in self.reports if r.get("id") != report.get("id")]
        self.storage.save(self.reports)
        self.load_reports()

    def _select_report(self, report_id):
        self.current_report_id = report_id
        report = self._find_report(report_id)
        if report:
            self.load_report_into_form(report)
        self._refresh_preview_from_form()

    def _get_current_report(self):
        if not self.current_report_id:
            return None
        return self._find_report(self.current_report_id)

    def load_report_into_form(self, report):
        self.current_report_id = report.get("id")
        self.name_edit.setText(report.get("name", ""))
        mode_label = MODE_REVERSE.get(report.get("mode", "table"), "Table")
        self.mode_combo.setCurrentText(mode_label)

        data_source = report.get("data_source", {})
        source_label = DATA_SOURCE_REVERSE.get(data_source.get("type", "all"), "All Devices")
        self.source_combo.setCurrentText(source_label)
        self.group_combo.setCurrentText(data_source.get("group", ""))
        self.subnet_edit.setText(data_source.get("subnet", ""))
        self.tag_edit.setText(data_source.get("tag", ""))

        self._load_filters(report.get("filters", []))
        if hasattr(self, "filter_logic_combo"):
            logic = report.get("filter_logic", "AND")
            self.filter_logic_combo.setCurrentText("OR" if logic == "OR" else "AND")
        self._use_all_columns = not report.get("columns")
        self._load_columns(
            report.get("columns", []),
            report.get("computed_columns", []),
            report.get("transformations", []),
            report.get("column_options", {}),
        )

        self.update_sort_options()
        sort_definitions = report.get("sorts") or []
        if not sort_definitions:
            legacy_sort = report.get("sort", {})
            if legacy_sort.get("column"):
                sort_definitions = [legacy_sort]
        self._load_sorts(sort_definitions)

        template = report.get("template", {})
        self.template_header_edit.setPlainText(template.get("header", ""))
        self.template_item_edit.setPlainText(template.get("item", "{{alias}}"))
        self.template_footer_edit.setPlainText(template.get("footer", ""))

        output = report.get("output", {})
        self.format_combo.setCurrentText(output.get("format", "HTML"))
        if mode_label == "Table":
            self._refresh_available_columns_list()

    def _load_filters(self, filters):
        self.filters_table.setRowCount(0)
        for flt in filters:
            self.add_filter_row(flt.get("property", ""), flt.get("operator", "equals"), flt.get("value", ""))

    def _load_columns(self, columns, computed_columns, transformations, column_options=None):
        opts = column_options or {}
        self.columns_list.clear()
        for name in columns:
            o = opts.get(name, {})
            self._add_column_item({
                "type": "existing", "name": name, "transformations": [],
                "visible": o.get("visible", True), "header": (o.get("header") or "").strip(),
            })
        for computed in computed_columns:
            name = computed.get("name", "")
            o = opts.get(name, {})
            self._add_column_item({
                "type": "computed", "name": name, "parts": computed.get("parts", ""), "transformations": [],
                "visible": o.get("visible", True), "header": (o.get("header") or "").strip(),
            })
        for transform in transformations:
            target = (transform.get("target") or "").strip()
            if not target:
                continue
            item = self._find_column_item(target)
            if item is None:
                implicit_column = self._use_all_columns and not columns
                o = opts.get(target, {})
                self._add_column_item({
                    "type": "existing", "name": target, "implicit": implicit_column,
                    "transformations": [{"transform": transform.get("transform", "upper"), "value": transform.get("value", "")}],
                    "visible": o.get("visible", True), "header": (o.get("header") or "").strip(),
                })
            else:
                self._append_transformation_to_item(
                    item,
                    {"transform": transform.get("transform", "upper"), "value": transform.get("value", "")},
                )
        self.update_sort_options()

    def add_filter_row(self, prop_name="", operator="equals", value=""):
        row = self.filters_table.rowCount()
        self.filters_table.insertRow(row)
        self.filters_table.setItem(row, 0, QTableWidgetItem(prop_name))
        operator_combo = QComboBox()
        operator_combo.addItems(FILTER_OPERATORS)
        operator_combo.setCurrentText(operator)
        operator_combo.currentTextChanged.connect(self._schedule_preview)
        self.filters_table.setCellWidget(row, 1, operator_combo)
        self.filters_table.setItem(row, 2, QTableWidgetItem(value))
        self._schedule_preview()

    def remove_selected_rows(self):
        rows = sorted({item.row() for item in self.filters_table.selectedItems()}, reverse=True)
        for row in rows:
            self.filters_table.removeRow(row)
        self._schedule_preview()

    def add_sort_row(self, column="", direction="asc"):
        row = self.sorts_table.rowCount()
        self.sorts_table.insertRow(row)
        self.sorts_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        num_item = self.sorts_table.item(row, 0)
        if num_item:
            num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
        column_combo = QComboBox()
        column_combo.addItem("")
        for name in self._get_available_sort_columns():
            column_combo.addItem(name)
        if column:
            if column_combo.findText(column) == -1:
                column_combo.addItem(column)
            column_combo.setCurrentText(column)
        column_combo.currentTextChanged.connect(self._schedule_preview)
        self.sorts_table.setCellWidget(row, 1, column_combo)

        direction_combo = QComboBox()
        direction_combo.addItems(["asc", "desc"])
        direction_combo.setCurrentText(direction or "asc")
        direction_combo.currentTextChanged.connect(self._schedule_preview)
        self.sorts_table.setCellWidget(row, 2, direction_combo)
        self._refresh_sort_priority_labels()
        self._schedule_preview()

    def remove_selected_sorts(self):
        rows = sorted({i.row() for i in self.sorts_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.sorts_table.removeRow(row)
        self._refresh_sort_priority_labels()
        self._schedule_preview()

    def _move_sort_rows(self, direction):
        if direction not in (-1, 1):
            return
        sorts = self._get_sort_rows(include_empty=True)
        if not sorts:
            return
        selected = sorted({i.row() for i in self.sorts_table.selectedIndexes()})
        if not selected:
            return
        if direction == 1:
            selected = list(reversed(selected))
        for row in selected:
            new_row = row + direction
            if new_row < 0 or new_row >= len(sorts):
                continue
            sorts[row], sorts[new_row] = sorts[new_row], sorts[row]
        new_selected = []
        for row in sorted({i.row() for i in self.sorts_table.selectedIndexes()}):
            moved = row + direction
            if 0 <= moved < len(sorts):
                new_selected.append(moved)
            else:
                new_selected.append(row)
        self._load_sorts(sorts)
        for row in new_selected:
            self.sorts_table.selectRow(row)
        self._schedule_preview()

    def _load_sorts(self, sorts):
        self.sorts_table.setRowCount(0)
        for sort_def in sorts:
            self.add_sort_row(sort_def.get("column", ""), sort_def.get("direction", "asc"))

    def _get_available_sort_columns(self):
        columns = []
        for row in range(self.columns_list.count()):
            item = self.columns_list.item(row)
            data = item.data(Qt.UserRole) or {}
            name = (data.get("name") or "").strip()
            if name:
                columns.append(name)
        if not columns:
            columns = self._collect_device_properties()
        return sorted(set(columns))

    def _get_sort_rows(self, include_empty=False):
        sorts = []
        for row in range(self.sorts_table.rowCount()):
            column_combo = self.sorts_table.cellWidget(row, 1)
            direction_combo = self.sorts_table.cellWidget(row, 2)
            column = column_combo.currentText().strip() if column_combo else ""
            direction = direction_combo.currentText() if direction_combo else "asc"
            if column or include_empty:
                sorts.append({"column": column, "direction": direction})
        return sorts

    def _refresh_sort_priority_labels(self):
        for row in range(self.sorts_table.rowCount()):
            num_item = self.sorts_table.item(row, 0)
            if num_item is None:
                self.sorts_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                num_item = self.sorts_table.item(row, 0)
            if num_item:
                num_item.setText(str(row + 1))
                num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)

    def _get_sort_definitions(self):
        return [sort_def for sort_def in self._get_sort_rows(include_empty=True) if sort_def.get("column")]

    def show_add_column_menu(self):
        menu = QMenu(self)
        add_existing = menu.addAction("Existing Column")
        add_computed = menu.addAction("Computed Column")
        add_transformed = menu.addAction("Transformed Column")
        action = menu.exec(self.add_column_button.mapToGlobal(QPoint(0, self.add_column_button.height())))
        if action == add_existing:
            self.add_existing_column()
        elif action == add_computed:
            self.add_computed_column()
        elif action == add_transformed:
            self.add_transformed_column()

    def add_existing_column(self):
        properties = self._collect_device_properties()
        used = self._column_names_in_use()
        available = [prop for prop in properties if prop not in used]
        if not available:
            QMessageBox.information(self, "Add Column", "All available properties are already added.")
            return
        dialog = QDialog(self)
        mark_plugin_ui(dialog)
        dialog.setWindowTitle("Add Existing Columns")
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for name in available:
            list_widget.addItem(name)
        layout.addWidget(list_widget)
        controls = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_none = QPushButton("Select None")
        controls.addWidget(select_all)
        controls.addWidget(select_none)
        controls.addStretch()
        layout.addLayout(controls)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        def on_select_all():
            for row in range(list_widget.count()):
                list_widget.item(row).setSelected(True)

        def on_select_none():
            list_widget.clearSelection()

        select_all.clicked.connect(on_select_all)
        select_none.clicked.connect(on_select_none)

        if dialog.exec() != QDialog.Accepted:
            return
        selected = [item.text().strip() for item in list_widget.selectedItems() if item.text().strip()]
        if not selected:
            return
        self._use_all_columns = False
        for name in selected:
            self._add_column_item({"type": "existing", "name": name, "transformations": []})
        self.update_sort_options()
        self._schedule_preview()

    def add_computed_column(self):
        dialog = QDialog(self)
        mark_plugin_ui(dialog)
        dialog.setWindowTitle("Add Computed Column")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name_edit = QLineEdit()
        parts_edit = QLineEdit()
        parts_edit.setPlaceholderText('hostname, " - ", ip_address')
        form.addRow("Column Name:", name_edit)
        form.addRow("Parts:", parts_edit)
        layout.addLayout(form)
        help_text = QLabel("Parts can be property names or quoted literals, comma separated.")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return
        name = name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Add Computed Column", "Column name is required.")
            return
        if name in self._column_names_in_use():
            QMessageBox.warning(self, "Add Computed Column", "That column name is already in use.")
            return
        self._add_column_item(
            {"type": "computed", "name": name, "parts": parts_edit.text().strip(), "transformations": []}
        )
        self.update_sort_options()
        self._schedule_preview()

    def add_transformed_column(self):
        dialog = QDialog(self)
        mark_plugin_ui(dialog)
        dialog.setWindowTitle("Add Transformed Column")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        target_combo = QComboBox()
        targets = self._available_transform_targets()
        if not targets:
            QMessageBox.information(
                self, "Add Transformed Column", "No properties are available to transform."
            )
            return
        target_combo.addItems(targets)
        transform_combo = QComboBox()
        transform_combo.addItems(TRANSFORM_TYPES)
        value_edit = QLineEdit()
        form.addRow("Target Column:", target_combo)
        form.addRow("Transform:", transform_combo)
        form.addRow("Value:", value_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return
        target = target_combo.currentText().strip()
        if not target:
            QMessageBox.warning(self, "Add Transformed Column", "Target column is required.")
            return
        transform = transform_combo.currentText()
        value = value_edit.text().strip()
        item = self._find_column_item(target)
        if item is None:
            self._use_all_columns = False
            self._add_column_item(
                {
                    "type": "existing",
                    "name": target,
                    "transformations": [{"transform": transform, "value": value}],
                }
            )
        else:
            self._append_transformation_to_item(item, {"transform": transform, "value": value})
        self.update_sort_options()
        self._schedule_preview()

    def remove_selected_columns(self):
        selected_rows = sorted({i.row() for i in self.columns_list.selectedIndexes()}, reverse=True)
        if not selected_rows:
            return
        for row in selected_rows:
            self.columns_list.takeItem(row)
        self.update_sort_options()
        self._refresh_available_columns_list()
        self._schedule_preview()

    def _on_columns_reordered(self, *_args):
        self.update_sort_options()
        self._schedule_preview()

    def clear_current_report(self):
        report_id = self.current_report_id or str(uuid.uuid4())
        cleared = default_report_definition()
        cleared["id"] = report_id
        cleared["name"] = self.name_edit.text().strip() or cleared["name"]
        self.load_report_into_form(cleared)
        self._schedule_preview()

    def save_report_as(self):
        current = self._get_current_report()
        if current:
            default_name = f"{current.get('name', 'Report')} (Copy)"
        else:
            default_name = "New Report"
        name, ok = QInputDialog.getText(self, "Save Report As", "Report name:", text=default_name)
        if not ok or not name.strip():
            return
        report, error_message = self._build_report_definition(show_errors=True)
        if not report:
            return
        report["id"] = str(uuid.uuid4())
        report["name"] = name.strip()
        self.reports.append(report)
        if self.storage.save(self.reports):
            self.report_saved.emit()
            self.load_reports()
            self._select_report(report["id"])

    def move_columns_up(self):
        self._move_list_items(-1)

    def move_columns_down(self):
        self._move_list_items(1)

    def _move_list_items(self, direction):
        if direction not in (-1, 1):
            return
        selected_rows = [i.row() for i in self.columns_list.selectedIndexes()]
        if not selected_rows:
            return
        selected_rows = sorted(set(selected_rows))
        if direction == 1:
            selected_rows = list(reversed(selected_rows))
        for row in selected_rows:
            new_row = row + direction
            if new_row < 0 or new_row >= self.columns_list.count():
                continue
            item = self.columns_list.takeItem(row)
            self.columns_list.insertItem(new_row, item)
            item.setSelected(True)
        self.update_sort_options()
        self._schedule_preview()

    def update_sort_options(self):
        columns = self._get_available_sort_columns()
        for row in range(self.sorts_table.rowCount()):
            combo = self.sorts_table.cellWidget(row, 1)
            if combo is None:
                continue
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("")
            for column in columns:
                combo.addItem(column)
            if current and combo.findText(current) == -1:
                combo.addItem(current)
            if current:
                combo.setCurrentText(current)
            combo.blockSignals(False)
        self._refresh_sort_priority_labels()

    def browse_output_path(self):
        selected_format = self.format_combo.currentText().lower()
        suffix = ".txt" if selected_format == "txt" else f".{selected_format}"
        default_name = self._build_default_export_filename()
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report",
            default_name,
            f"Report (*{suffix});;All Files (*)"
        )
        if filename:
            if not filename.lower().endswith(suffix):
                filename = f"{filename}{suffix}"
            self.path_edit.setText(filename)

    def save_report(self):
        report, error_message = self._build_report_definition(show_errors=True)
        if not report:
            return
        updated = False
        for idx, existing in enumerate(self.reports):
            if existing.get("id") == report.get("id"):
                self.reports[idx] = report
                updated = True
                break
        if not updated:
            self.reports.append(report)
        if self.storage.save(self.reports):
            self.report_saved.emit()
            self.load_reports()
            self._select_report(report["id"])

    def generate_preview(self):
        report, error_message = self._build_report_definition(show_errors=True)
        if not report:
            return
        content, error = self._generate_report_content(report)
        if error:
            QMessageBox.warning(self, "Report Preview", error)
            return
        self._render_preview(report, content)

    def export_report(self):
        report, error_message = self._build_report_definition(show_errors=True)
        if not report:
            return
        content, error = self._generate_report_content(report)
        if error:
            QMessageBox.warning(self, "Export Report", error)
            return
        output_path = self.path_edit.text().strip()
        if not output_path:
            self.browse_output_path()
            output_path = self.path_edit.text().strip()
        if not output_path:
            return
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(content)
            QMessageBox.information(self, "Export Report", f"Report exported to {output_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Report", f"Failed to export report: {exc}")

    def _schedule_preview(self, *_args):
        if not self.preview_timer.isActive():
            self.preview_timer.start(300)

    def _refresh_preview_from_form(self):
        report, error_message = self._build_report_definition(show_errors=False)
        if not report:
            if error_message:
                self.preview_text.setPlainText(error_message)
            else:
                self.preview_text.clear()
            return
        try:
            content, error = self._generate_report_content(report)
            if error:
                self.preview_text.setPlainText(error)
                return
            self._render_preview(report, content)
        except Exception as exc:
            self.preview_text.setPlainText(f"Preview error: {exc}")

    def _render_preview(self, report, content):
        output_format = report.get("output", {}).get("format", "HTML")
        if output_format == "JSON":
            rendered = self._render_json_preview(content)
        elif output_format == "CSV":
            rendered = self._render_csv_preview(content)
        elif output_format == "HTML":
            rendered = content
        else:
            rendered = f"<pre>{html.escape(content)}</pre>"
        self.preview_text.setHtml(rendered)

    def _build_default_export_filename(self):
        now = datetime.datetime.now()
        report_name = self.name_edit.text().strip() or "Report"
        template = self.filename_template_edit.text().strip() or "{name}_{date}_{time}"
        variables = {
            "name": report_name,
            "date": now.strftime("%Y%m%d"),
            "time": now.strftime("%H%M%S"),
        }
        try:
            filename = template.format(**variables)
        except Exception:
            filename = f"{report_name}_{variables['date']}_{variables['time']}"
        return filename

    def open_report_manager(self):
        show_manage_reports_dialog(self, self)

    def _build_report_definition(self, show_errors=True):
        name = self.name_edit.text().strip()
        if not name:
            if show_errors:
                QMessageBox.warning(self, "Report", "Report name is required.")
            return None, "Preview error: report name is required."
        report_id = self.current_report_id or str(uuid.uuid4())

        mode = MODE_MAP.get(self.mode_combo.currentText(), "table")
        source_type = DATA_SOURCE_MAP.get(self.source_combo.currentText(), "all")

        filters = []
        for row in range(self.filters_table.rowCount()):
            prop_item = self.filters_table.item(row, 0)
            operator_widget = self.filters_table.cellWidget(row, 1)
            value_item = self.filters_table.item(row, 2)
            prop = prop_item.text().strip() if prop_item else ""
            operator = operator_widget.currentText() if operator_widget else "equals"
            value = value_item.text().strip() if value_item else ""
            if prop:
                filters.append({"property": prop, "operator": operator, "value": value})

        columns = []
        computed_columns = []
        transformations = []
        column_options = {}
        for row in range(self.columns_list.count()):
            item = self.columns_list.item(row)
            data = item.data(Qt.UserRole) or {}
            col_name = (data.get("name") or "").strip()
            if not col_name:
                continue
            column_options[col_name] = {
                "visible": data.get("visible", True),
                "header": (data.get("header") or "").strip(),
            }
            if data.get("type") == "computed":
                computed_columns.append({"name": col_name, "parts": data.get("parts", "")})
            else:
                if not (self._use_all_columns and data.get("implicit")):
                    columns.append(col_name)
            for transform in data.get("transformations", []):
                transform_name = (transform.get("transform") or "").strip()
                if not transform_name:
                    continue
                transformations.append(
                    {"target": col_name, "transform": transform_name, "value": transform.get("value", "")}
                )

        filter_logic = self.filter_logic_combo.currentText() if hasattr(self, "filter_logic_combo") else "AND"
        sort_definitions = self._get_sort_definitions()
        sort_fallback = sort_definitions[0] if sort_definitions else {"column": "", "direction": "asc"}
        report_definition = {
            "id": report_id,
            "name": name,
            "mode": mode,
            "data_source": {
                "type": source_type,
                "group": self.group_combo.currentText().strip(),
                "subnet": self.subnet_edit.text().strip(),
                "tag": self.tag_edit.text().strip(),
            },
            "filters": filters,
            "filter_logic": filter_logic,
            "columns": columns,
            "column_options": column_options,
            "computed_columns": computed_columns,
            "transformations": transformations,
            "sort": sort_fallback,
            "sorts": sort_definitions,
            "template": {
                "header": self.template_header_edit.toPlainText(),
                "item": self.template_item_edit.toPlainText(),
                "footer": self.template_footer_edit.toPlainText(),
            },
            "output": {"format": self.format_combo.currentText()},
        }
        return report_definition, None

    def _generate_report_content(self, report):
        devices = resolve_devices(report, self.plugin.device_manager)
        if not devices:
            return "", "No devices matched the report criteria."
        filters = report.get("filters", [])
        filter_logic = report.get("filter_logic", "AND")
        devices = apply_filters(devices, filters, filter_logic)
        if not devices:
            return "", "No devices matched the filters."
        mode = report.get("mode", "table")
        transformations = report.get("transformations", [])
        transform_map = build_transform_map(transformations)
        computed_columns = report.get("computed_columns", [])
        rows = build_rows(devices, report, transform_map, self._collect_device_properties())
        theme_tokens = self._get_report_theme_tokens()
        if mode == "template":
            return render_template_report(report, devices, rows, transform_map, theme_tokens)
        return render_table_report(
            report, rows, computed_columns,
            report.get("column_options") or {},
            lambda: self._collect_device_properties(),
            theme_tokens,
        )
    def _get_report_theme_tokens(self):
        app = getattr(self.plugin, "app", None)
        config = getattr(app, "config", None) if app else None
        theme_name = config.get("ui.theme", "light") if config else "light"
        font_size = config.get("ui.font_size", 10) if config else 10
        row_height = config.get("ui.row_height", 22) if config else 22
        accent_color = config.get("ui.accent_color", "") if config else ""
        return get_theme_tokens(
            theme_name,
            font_size=font_size,
            row_height=row_height,
            accent_override=accent_color,
        )
