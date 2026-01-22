#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device import wizard UI for NetWORKS.
"""

import os
from loguru import logger

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QPlainTextEdit, QFileDialog,
    QMessageBox, QTabWidget, QSpinBox, QProgressDialog
)

from ..core.importer import DeviceImporter


class DeviceImportWizard(QWizard):
    """Wizard for importing devices from files or pasted text."""

    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.importer = DeviceImporter(device_manager)
        self.import_success = None
        self.import_stats = None
        self._data = []
        self._headers = []
        self._field_mapping = {}
        self._preview_rows = 10

        self.setWindowTitle("Import Devices")
        self.setMinimumSize(900, 650)

        self._create_pages()
        self.currentIdChanged.connect(self._on_page_changed)

    def _create_pages(self):
        self._create_source_page()
        self._create_mapping_page()
        self._create_options_page()
        self._create_confirm_page()

    def _create_source_page(self):
        self.source_page = QWizardPage()
        self.source_page.setTitle("Select Import Source")
        self.source_page.setSubTitle("Choose a file or paste text data")

        layout = QVBoxLayout(self.source_page)

        self.source_tabs = QTabWidget()

        # File tab
        file_tab = QGroupBox()
        file_layout = QVBoxLayout(file_tab)

        file_select_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select a CSV, TXT, or Excel file...")
        file_select_layout.addWidget(self.file_path_edit)

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._select_file)
        file_select_layout.addWidget(browse_button)
        file_layout.addLayout(file_select_layout)

        file_options_group = QGroupBox("File Options")
        file_options_layout = QFormLayout(file_options_group)

        self.file_delimiter_combo = QComboBox()
        self.file_delimiter_combo.addItems(
            ["Auto-detect", "Comma (,)", "Tab", "Semicolon (;)", "Pipe (|)", "Space"]
        )
        file_options_layout.addRow("Delimiter:", self.file_delimiter_combo)

        self.file_has_header_check = QCheckBox("First row contains headers")
        self.file_has_header_check.setChecked(True)
        file_options_layout.addRow("", self.file_has_header_check)

        self.file_encoding_combo = QComboBox()
        self.file_encoding_combo.addItems(
            ["Auto-detect", "UTF-8", "ASCII", "Latin-1 (ISO-8859-1)", "Windows-1252"]
        )
        file_options_layout.addRow("Text Encoding:", self.file_encoding_combo)

        self.file_skip_rows_spin = QSpinBox()
        self.file_skip_rows_spin.setRange(0, 100)
        self.file_skip_rows_spin.setToolTip("Skip rows after the header row is processed")
        file_options_layout.addRow("Skip Rows:", self.file_skip_rows_spin)

        file_layout.addWidget(file_options_group)

        self.source_tabs.addTab(file_tab, "File")

        # Text tab
        text_tab = QGroupBox()
        text_layout = QVBoxLayout(text_tab)

        text_options_group = QGroupBox("Text Options")
        text_options_layout = QFormLayout(text_options_group)

        self.text_delimiter_combo = QComboBox()
        self.text_delimiter_combo.addItems(
            ["Auto-detect", "Comma (,)", "Tab", "Semicolon (;)", "Pipe (|)", "Space"]
        )
        text_options_layout.addRow("Delimiter:", self.text_delimiter_combo)

        self.text_has_header_check = QCheckBox("First row contains headers")
        self.text_has_header_check.setChecked(True)
        text_options_layout.addRow("", self.text_has_header_check)

        self.text_skip_rows_spin = QSpinBox()
        self.text_skip_rows_spin.setRange(0, 100)
        self.text_skip_rows_spin.setToolTip("Skip rows after the header row is processed")
        text_options_layout.addRow("Skip Rows:", self.text_skip_rows_spin)

        text_layout.addWidget(text_options_group)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Paste CSV, TXT, or a list of IPs/hostnames here...")
        text_layout.addWidget(self.text_edit)

        help_label = QLabel(
            "Paste delimited text or a simple list of IP addresses/hostnames (one per line)."
        )
        help_label.setWordWrap(True)
        text_layout.addWidget(help_label)

        self.source_tabs.addTab(text_tab, "Text")

        layout.addWidget(self.source_tabs)

        def is_complete():
            if self.source_tabs.currentIndex() == 0:
                return bool(self.file_path_edit.text().strip())
            return bool(self.text_edit.toPlainText().strip())

        self.source_page.isComplete = is_complete
        self.addPage(self.source_page)

        self.file_path_edit.textChanged.connect(lambda: self.source_page.completeChanged.emit())
        self.text_edit.textChanged.connect(lambda: self.source_page.completeChanged.emit())

    def _create_mapping_page(self):
        self.mapping_page = QWizardPage()
        self.mapping_page.setTitle("Preview & Field Mapping")
        self.mapping_page.setSubTitle("Review data and map fields to device properties")

        layout = QVBoxLayout(self.mapping_page)

        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(2)
        self.mapping_table.setHorizontalHeaderLabels(["Field", "Device Property"])
        self.mapping_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.mapping_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.mapping_table)

        self.mapping_warning_label = QLabel("")
        self.mapping_warning_label.setStyleSheet("color: #a04a00;")
        self.mapping_warning_label.setWordWrap(True)
        layout.addWidget(self.mapping_warning_label)

        preview_group = QGroupBox("Data Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget()
        preview_layout.addWidget(self.preview_table)
        layout.addWidget(preview_group)

        self.addPage(self.mapping_page)

    def _create_options_page(self):
        self.options_page = QWizardPage()
        self.options_page.setTitle("Import Options")
        self.options_page.setSubTitle("Configure import behavior")

        layout = QVBoxLayout(self.options_page)

        target_group_label = QLabel("Target Group:")
        layout.addWidget(target_group_label)

        self.target_group_combo = QComboBox()
        self.target_group_combo.addItem("All Devices")
        for group in self.device_manager.get_groups():
            if group != self.device_manager.root_group:
                self.target_group_combo.addItem(group.name)
        layout.addWidget(self.target_group_combo)

        new_group_layout = QHBoxLayout()
        self.new_group_check = QCheckBox("Create new group:")
        self.new_group_edit = QLineEdit()
        self.new_group_edit.setEnabled(False)

        def toggle_new_group():
            self.new_group_edit.setEnabled(self.new_group_check.isChecked())
            self.target_group_combo.setEnabled(not self.new_group_check.isChecked())

        self.new_group_check.toggled.connect(toggle_new_group)
        new_group_layout.addWidget(self.new_group_check)
        new_group_layout.addWidget(self.new_group_edit)
        layout.addLayout(new_group_layout)

        duplicate_group = QGroupBox("Duplicate Handling")
        duplicate_layout = QFormLayout(duplicate_group)
        self.duplicate_strategy_combo = QComboBox()
        self.duplicate_strategy_combo.addItem("Skip duplicates", "skip")
        self.duplicate_strategy_combo.addItem("Overwrite existing", "overwrite")
        self.duplicate_strategy_combo.addItem("Create new entries", "create_new")
        duplicate_layout.addRow("When duplicates are found:", self.duplicate_strategy_combo)
        layout.addWidget(duplicate_group)

        self.mark_imported_check = QCheckBox("Add 'imported' tag to devices")
        self.mark_imported_check.setChecked(True)
        layout.addWidget(self.mark_imported_check)

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #a04a00;")
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        layout.addStretch()

        self.addPage(self.options_page)

    def _create_confirm_page(self):
        self.confirm_page = QWizardPage()
        self.confirm_page.setTitle("Confirm & Import")
        self.confirm_page.setSubTitle("Review summary and import devices")

        layout = QVBoxLayout(self.confirm_page)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.addPage(self.confirm_page)

    def _select_file(self):
        filter_str = "CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xlsx *.xls)"
        filter_str = "Supported Files (*.csv *.txt *.xlsx *.xls);;" + filter_str
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Import File", "", filter_str)
        if file_path:
            self.file_path_edit.setText(file_path)
            logger.debug(f"Import file selected: {file_path}")

    def _on_page_changed(self, page_id):
        if self.page(page_id) == self.mapping_page:
            self._populate_mapping_page()
        elif self.page(page_id) == self.options_page:
            self._update_validation_warnings()
        elif self.page(page_id) == self.confirm_page:
            self._update_summary()

    def _prepare_data(self):
        if self.source_tabs.currentIndex() == 0:
            file_path = self.file_path_edit.text().strip()
            if not file_path or not os.path.exists(file_path):
                return [], None
            options = {
                "delimiter": self.file_delimiter_combo.currentText(),
                "has_header": self.file_has_header_check.isChecked(),
                "encoding": self.file_encoding_combo.currentText(),
                "skip_rows": self.file_skip_rows_spin.value(),
            }
            return self.importer._extract_data_from_file(
                file_path, os.path.splitext(file_path)[1].lower(), options
            )

        text = self.text_edit.toPlainText().strip()
        if not text:
            return [], None
        options = {
            "delimiter": self.text_delimiter_combo.currentText(),
            "has_header": self.text_has_header_check.isChecked(),
            "skip_rows": self.text_skip_rows_spin.value(),
        }
        return self.importer._extract_data_from_text(text, options)

    def _populate_mapping_page(self):
        data, headers = self._prepare_data()
        if not data or not headers:
            QMessageBox.critical(self, "Import Error", "No data could be extracted.")
            self.back()
            return

        self._data = data
        self._headers = headers

        self.mapping_table.setRowCount(len(headers))

        properties = [
            "ignore",
            "alias",
            "hostname",
            "ip_address",
            "mac_address",
            "status",
            "notes",
            "tags",
            "groups",
            "type",
            "vendor",
            "model",
            "serial_number",
            "location",
            "custom",
        ]

        auto_mappings = self.importer._auto_detect_field_mapping(headers)

        for i, header in enumerate(headers):
            header_item = QTableWidgetItem(str(header))
            header_item.setFlags(header_item.flags() & ~Qt.ItemIsEditable)
            self.mapping_table.setItem(i, 0, header_item)

            combo = QComboBox()
            combo.addItems(properties)
            for field_name, mapped_headers in auto_mappings.items():
                if header in mapped_headers:
                    combo.setCurrentText(field_name)
                    break
            combo.currentTextChanged.connect(self._update_mapping_warning)
            self.mapping_table.setCellWidget(i, 1, combo)

        max_rows = min(self._preview_rows, len(data))
        self.preview_table.setRowCount(max_rows)
        self.preview_table.setColumnCount(len(headers))
        self.preview_table.setHorizontalHeaderLabels([str(h) for h in headers])

        for row in range(max_rows):
            for col in range(len(headers)):
                if col < len(data[row]):
                    item = QTableWidgetItem(str(data[row][col]))
                    self.preview_table.setItem(row, col, item)

        self._update_mapping_warning()

    def _collect_field_mapping(self):
        mapping = {}
        for i in range(self.mapping_table.rowCount()):
            header_item = self.mapping_table.item(i, 0)
            combo = self.mapping_table.cellWidget(i, 1)
            if not header_item or not combo:
                continue
            header = header_item.text()
            mapping_value = combo.currentText()
            if mapping_value == "ignore":
                continue
            if mapping_value not in mapping:
                mapping[mapping_value] = []
            mapping[mapping_value].append(header)
        return mapping

    def _count_missing_required_rows(self, data, headers, field_mapping):
        if not data or not headers:
            return 0

        header_index = {header: idx for idx, header in enumerate(headers)}
        ip_headers = field_mapping.get("ip_address", [])
        host_headers = field_mapping.get("hostname", [])

        if not ip_headers and not host_headers:
            return len(data)

        missing = 0
        for row in data:
            ip_value = ""
            hostname_value = ""
            for header in ip_headers:
                idx = header_index.get(header)
                if idx is not None and idx < len(row):
                    ip_value = str(row[idx]).strip() if row[idx] is not None else ""
                    if ip_value:
                        break
            for header in host_headers:
                idx = header_index.get(header)
                if idx is not None and idx < len(row):
                    hostname_value = str(row[idx]).strip() if row[idx] is not None else ""
                    if hostname_value:
                        break
            if not ip_value and not hostname_value:
                missing += 1
        return missing

    def _update_mapping_warning(self):
        mapping = self._collect_field_mapping()
        has_required_mapping = bool(mapping.get("ip_address") or mapping.get("hostname"))
        if not has_required_mapping:
            self.mapping_warning_label.setText(
                "Warning: No IP address or hostname mapping is selected."
            )
        else:
            self.mapping_warning_label.setText("")

    def _update_validation_warnings(self):
        self._field_mapping = self._collect_field_mapping()
        warnings = []
        if not (self._field_mapping.get("ip_address") or self._field_mapping.get("hostname")):
            warnings.append("No IP address or hostname mapping is selected.")

        missing_rows = self._count_missing_required_rows(
            self._data, self._headers, self._field_mapping
        )
        if missing_rows:
            warnings.append(
                f"{missing_rows} row(s) are missing both IP address and hostname and will be skipped."
            )

        if warnings:
            self.validation_label.setText("Warnings:\n" + "\n".join(warnings))
        else:
            self.validation_label.setText("")

    def _update_summary(self):
        data_count = len(self._data) if self._data else 0
        if self.new_group_check.isChecked():
            target = f"Create new group: {self.new_group_edit.text().strip() or 'Unnamed'}"
        else:
            target = f"Add to group: {self.target_group_combo.currentText()}"

        duplicate_strategy = self.duplicate_strategy_combo.currentData()
        duplicate_label = {
            "skip": "Skip duplicates",
            "overwrite": "Overwrite existing",
            "create_new": "Create new entries",
        }.get(duplicate_strategy, "Skip duplicates")

        warnings = self.validation_label.text().strip()
        warning_text = f"\n\n{warnings}" if warnings else ""

        summary = (
            f"Ready to import {data_count} row(s).\n\n"
            f"{target}\n"
            f"Duplicate handling: {duplicate_label}\n"
            f"Add 'imported' tag: {'Yes' if self.mark_imported_check.isChecked() else 'No'}"
            f"{warning_text}"
        )
        self.summary_label.setText(summary)

    def _run_import(self):
        if not self._data or not self._headers:
            self._data, self._headers = self._prepare_data()
        if not self._data:
            QMessageBox.critical(self, "Import Error", "No data to import.")
            return False

        field_mapping = self._collect_field_mapping()
        duplicate_strategy = self.duplicate_strategy_combo.currentData()

        target_group = None
        if self.new_group_check.isChecked():
            group_name = self.new_group_edit.text().strip()
            if group_name:
                target_group = self.device_manager.create_group(group_name)
        else:
            group_name = self.target_group_combo.currentText()
            target_group = self.device_manager.get_group(group_name)

        progress = QProgressDialog("Importing devices...", "", 0, len(self._data), self)
        progress.setWindowTitle("Importing")
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)

        def progress_callback(current, total):
            progress.setMaximum(total)
            progress.setValue(current)

        options = {
            "field_mapping": field_mapping,
            "duplicate_strategy": duplicate_strategy,
            "mark_imported": self.mark_imported_check.isChecked(),
            "target_group": target_group,
            "progress_callback": progress_callback,
        }

        if self.source_tabs.currentIndex() == 0:
            file_path = self.file_path_edit.text().strip()
            options.update(
                {
                    "delimiter": self.file_delimiter_combo.currentText(),
                    "has_header": self.file_has_header_check.isChecked(),
                    "encoding": self.file_encoding_combo.currentText(),
                    "skip_rows": self.file_skip_rows_spin.value(),
                }
            )
            success, stats = self.importer.import_from_file(file_path, options)
        else:
            text = self.text_edit.toPlainText().strip()
            options.update(
                {
                    "delimiter": self.text_delimiter_combo.currentText(),
                    "has_header": self.text_has_header_check.isChecked(),
                    "skip_rows": self.text_skip_rows_spin.value(),
                }
            )
            success, stats = self.importer.import_from_text(text, options)

        progress.close()
        self.import_stats = stats
        self.import_success = success

        if success:
            QMessageBox.information(
                self,
                "Import Successful",
                f"Successfully imported {stats['imported_count']} device(s).\n"
                f"Skipped: {stats['skipped_count']}\n"
                f"Errors: {stats['error_count']}",
            )
        else:
            QMessageBox.warning(
                self,
                "Import Completed",
                f"Imported: {stats['imported_count']}\n"
                f"Skipped: {stats['skipped_count']}\n"
                f"Errors: {stats['error_count']}",
            )

        return success

    def accept(self):
        try:
            self._run_import()
        except Exception as exc:
            logger.error(f"Error during import: {exc}", exc_info=True)
            QMessageBox.critical(self, "Import Error", f"Import failed: {exc}")
            self.import_success = False
            return
        super().accept()


def run_device_import_wizard(device_manager, parent=None):
    """Run the device import wizard and return True if import succeeded."""
    wizard = DeviceImportWizard(device_manager, parent)
    wizard.exec()
    return bool(wizard.import_success)
