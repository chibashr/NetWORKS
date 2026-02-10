#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device import wizard UI for NetWORKS.
"""

import os
from loguru import logger

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QPlainTextEdit, QFileDialog,
    QMessageBox, QTabWidget, QSpinBox, QProgressDialog, QSplitter,
    QScrollArea, QFrame, QSizePolicy,
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
        self._updating_preview = False
        self._selected_sheet = None
        self._selected_sheets = []

        self.setWindowTitle("Import Devices")
        self.setMinimumSize(900, 650)
        if self.layout():
            # Tighten outer margins so the top border gap is minimal
            self.layout().setContentsMargins(4, 4, 4, 4)

        self._create_pages()
        self.currentIdChanged.connect(self._on_page_changed)

        # Ensure wizard buttons follow consistent sizing guidelines
        for button_role in (
            QWizard.BackButton,
            QWizard.NextButton,
            QWizard.FinishButton,
            QWizard.CancelButton,
        ):
            btn = self.button(button_role)
            if btn is not None:
                btn.setMinimumHeight(28)
                btn.setMinimumWidth(90)

    def _create_pages(self):
        self._create_source_page()
        self._create_mapping_page()
        self._create_confirm_page()

    def _create_source_page(self):
        self.source_page = QWizardPage()
        self.source_page.setTitle("Select Import Source")
        self.source_page.setSubTitle("Choose a file or paste text data")

        layout = QVBoxLayout(self.source_page)
        layout.setContentsMargins(8, 8, 8, 8)

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

        # Placeholder labels that will be updated after auto-detection runs
        self.auto_detect_info_label = QLabel("")
        self.auto_detect_info_label.setWordWrap(True)
        self.auto_detect_info_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(self.auto_detect_info_label)

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
        self.mapping_page.setSubTitle("Review data, map fields, and configure import options")

        page_layout = QVBoxLayout(self.mapping_page)
        page_layout.setContentsMargins(8, 8, 8, 8)

        # Top bar: worksheet and skip rows (full width)
        controls_layout = QHBoxLayout()
        self.sheet_label = QLabel("Worksheet:")
        self.sheet_combo = QComboBox()
        self.sheet_label.setVisible(False)
        self.sheet_combo.setVisible(False)
        self.sheet_combo.currentTextChanged.connect(self._on_sheet_changed)
        controls_layout.addWidget(self.sheet_label)
        controls_layout.addWidget(self.sheet_combo)

        self.import_all_sheets_check = QCheckBox("Import all worksheets")
        self.import_all_sheets_check.setVisible(False)
        self.import_all_sheets_check.toggled.connect(self._on_import_all_sheets_toggled)
        controls_layout.addWidget(self.import_all_sheets_check)

        controls_layout.addStretch()

        self.preview_skip_rows_label = QLabel("Skip Rows:")
        self.preview_skip_rows_spin = QSpinBox()
        self.preview_skip_rows_spin.setRange(0, 100)
        self.preview_skip_rows_spin.setToolTip(
            "Skip rows after the header row is processed"
        )
        self.preview_skip_rows_spin.valueChanged.connect(
            self._on_preview_skip_rows_changed
        )
        controls_layout.addWidget(self.preview_skip_rows_label)
        controls_layout.addWidget(self.preview_skip_rows_spin)

        page_layout.addLayout(controls_layout)

        # Paneled content: left = field mapping + import options, right = preview (larger)
        splitter = QSplitter(Qt.Horizontal)

        # Left panel: field mapping and import options
        left_widget = QFrame()
        left_widget.setFrameShape(QFrame.NoFrame)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        mapping_group = QGroupBox("Field Mapping")
        mapping_group_layout = QVBoxLayout(mapping_group)
        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(2)
        self.mapping_table.setHorizontalHeaderLabels(["Field", "Device Property"])
        self.mapping_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.mapping_table.horizontalHeader().setStretchLastSection(True)
        mapping_group_layout.addWidget(self.mapping_table)

        self.mapping_warning_label = QLabel("")
        self.mapping_warning_label.setStyleSheet("color: #a04a00;")
        self.mapping_warning_label.setWordWrap(True)
        mapping_group_layout.addWidget(self.mapping_warning_label)
        left_layout.addWidget(mapping_group)

        options_group = QGroupBox("Import Options")
        options_layout = QVBoxLayout(options_group)
        target_group_label = QLabel("Target Group:")
        options_layout.addWidget(target_group_label)
        self.target_group_combo = QComboBox()
        self.target_group_combo.addItem("All Devices")
        for group in self.device_manager.get_groups():
            if group != self.device_manager.root_group:
                self.target_group_combo.addItem(group.name)
        options_layout.addWidget(self.target_group_combo)

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
        options_layout.addLayout(new_group_layout)

        duplicate_group = QGroupBox("Duplicate Handling")
        duplicate_layout = QFormLayout(duplicate_group)
        self.duplicate_strategy_combo = QComboBox()
        self.duplicate_strategy_combo.addItem("Skip duplicates", "skip")
        self.duplicate_strategy_combo.addItem("Overwrite existing", "overwrite")
        self.duplicate_strategy_combo.addItem("Create new entries", "create_new")
        duplicate_layout.addRow("When duplicates are found:", self.duplicate_strategy_combo)
        options_layout.addWidget(duplicate_group)

        self.mark_imported_check = QCheckBox("Add 'imported' tag to devices")
        self.mark_imported_check.setChecked(True)
        options_layout.addWidget(self.mark_imported_check)

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #a04a00;")
        self.validation_label.setWordWrap(True)
        options_layout.addWidget(self.validation_label)

        left_layout.addWidget(options_group)
        left_layout.addStretch()

        left_scroll = QScrollArea()
        left_scroll.setWidget(left_widget)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_scroll.setMinimumWidth(280)
        left_scroll.setMaximumWidth(420)
        splitter.addWidget(left_scroll)

        # Right panel: preview (effective data, like confirmation page)
        preview_group = QGroupBox("Preview")
        preview_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout = QVBoxLayout(preview_group)
        self.preview_caption_label = QLabel("")
        self.preview_caption_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        preview_layout.addWidget(self.preview_caption_label)

        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview_table.setAlternatingRowColors(True)
        preview_layout.addWidget(self.preview_table)

        splitter.addWidget(preview_group)

        # Give more space to the right (preview): e.g. left ~35%, right ~65%
        splitter.setSizes([350, 650])
        page_layout.addWidget(splitter, 1)

        self.addPage(self.mapping_page)

    def _create_confirm_page(self):
        self.confirm_page = QWizardPage()
        self.confirm_page.setTitle("Confirm & Import")
        self.confirm_page.setSubTitle("Review summary and import devices")

        layout = QVBoxLayout(self.confirm_page)
        layout.setContentsMargins(8, 8, 8, 8)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # Final review table showing the rows that will be imported
        self.review_table = QTableWidget()
        self.review_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.review_table)

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
            self._prepare_mapping_page_state()
            self._populate_mapping_page()
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
                "skip_rows": self.preview_skip_rows_spin.value(),
                "sheet_name": self._selected_sheet,
                "sheet_names": self._selected_sheets or None,
            }
            data, headers = self.importer._extract_data_from_file(
                file_path, os.path.splitext(file_path)[1].lower(), options
            )
            # Update auto-detect info if applicable
            self._update_auto_detect_info()
            return data, headers

        text = self.text_edit.toPlainText().strip()
        if not text:
            return [], None
        options = {
            "delimiter": self.text_delimiter_combo.currentText(),
            "has_header": self.text_has_header_check.isChecked(),
            "skip_rows": self.preview_skip_rows_spin.value(),
        }
        data, headers = self.importer._extract_data_from_text(text, options)
        self._update_auto_detect_info()
        return data, headers

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

        self._update_mapping_warning()
        self._refresh_effective_preview()
        self._update_validation_warnings()

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
        self._field_mapping = self._collect_field_mapping()
        has_required_mapping = bool(
            self._field_mapping.get("ip_address")
            or self._field_mapping.get("hostname")
        )
        if not has_required_mapping:
            self.mapping_warning_label.setText(
                "Warning: No IP address or hostname mapping is selected."
            )
        else:
            self.mapping_warning_label.setText("")
        self._refresh_effective_preview()

    def _refresh_effective_preview(self):
        """Update the right-side preview to show effective data (mapped columns, eligible rows only)."""
        self.preview_table.clear()
        self.preview_caption_label.setText("")
        if not self._data or not self._headers:
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            return

        field_mapping = self._field_mapping or self._collect_field_mapping()
        header_index = {header: idx for idx, header in enumerate(self._headers)}
        ip_headers = field_mapping.get("ip_address", [])
        host_headers = field_mapping.get("hostname", [])

        # Effective columns: only mapped (non-ignore) in original order
        effective_headers = []
        for prop, mapped_headers in field_mapping.items():
            if prop == "ignore":
                continue
            effective_headers.extend(mapped_headers)
        effective_headers = [h for h in self._headers if h in effective_headers]

        rows_for_import = []
        for row in self._data:
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
                    hostname_value = (
                        str(row[idx]).strip() if row[idx] is not None else ""
                    )
                    if hostname_value:
                        break
            if ip_value or hostname_value:
                rows_for_import.append(row)

        subset = rows_for_import[: self._preview_rows]
        total_eligible = len(rows_for_import)

        if effective_headers:
            self.preview_table.setColumnCount(len(effective_headers))
            self.preview_table.setHorizontalHeaderLabels(
                [str(h) for h in effective_headers]
            )
        self.preview_table.setRowCount(len(subset))

        for row_idx, row in enumerate(subset):
            for col_idx, header in enumerate(effective_headers):
                idx = header_index.get(header)
                value = ""
                if idx is not None and idx < len(row):
                    value = str(row[idx]) if row[idx] is not None else ""
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.preview_table.setItem(row_idx, col_idx, item)

        # Caption: subset info
        if total_eligible == 0:
            self.preview_caption_label.setText(
                "No eligible rows (map IP address or hostname). Ignored columns are hidden."
            )
        elif len(subset) < total_eligible:
            self.preview_caption_label.setText(
                f"Showing first {len(subset)} of {total_eligible} eligible rows. "
                "Ignored columns are hidden."
            )
        else:
            self.preview_caption_label.setText(
                f"Showing all {total_eligible} eligible row(s). Ignored columns are hidden."
            )

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

        # Derive counts based on current mapping so the user can see exactly
        # what will be imported vs skipped.
        field_mapping = self._collect_field_mapping()
        self._field_mapping = field_mapping
        missing_required = self._count_missing_required_rows(
            self._data, self._headers, field_mapping
        )
        eligible_rows = max(data_count - missing_required, 0)

        summary = (
            f"Total rows in data: {data_count}\n"
            f"Rows with required IP/hostname (eligible for import): {eligible_rows}\n"
            f"Rows missing IP/hostname (will be skipped): {missing_required}\n\n"
            f"{target}\n"
            f"Duplicate handling: {duplicate_label}\n"
            f"Add 'imported' tag: {'Yes' if self.mark_imported_check.isChecked() else 'No'}"
            f"{warning_text}"
        )
        self.summary_label.setText(summary)

        # Populate the final review table with the rows that will be imported.
        # This table only shows mapped fields; ignored fields are omitted so the
        # user can clearly see the effective dataset.
        self.review_table.clear()
        if not self._data or not self._headers:
            self.review_table.setRowCount(0)
            self.review_table.setColumnCount(0)
            return

        # Use the current field mapping to determine which rows have required
        # fields and which columns are actually imported.
        header_index = {header: idx for idx, header in enumerate(self._headers)}
        ip_headers = field_mapping.get("ip_address", [])
        host_headers = field_mapping.get("hostname", [])

        # Build a flat list of effective columns (ignore + unmapped are dropped)
        effective_headers = []
        for prop, mapped_headers in field_mapping.items():
            if prop == "ignore":
                continue
            effective_headers.extend(mapped_headers)
        # Deduplicate while preserving order of appearance in original headers
        effective_headers = [h for h in self._headers if h in effective_headers]

        rows_for_import = []
        for row in self._data:
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
                    hostname_value = (
                        str(row[idx]).strip() if row[idx] is not None else ""
                    )
                    if hostname_value:
                        break
            if ip_value or hostname_value:
                rows_for_import.append(row)

        self.review_table.setColumnCount(len(effective_headers))
        self.review_table.setHorizontalHeaderLabels([str(h) for h in effective_headers])
        self.review_table.setRowCount(len(rows_for_import))

        for row_idx, row in enumerate(rows_for_import):
            for col_idx, header in enumerate(effective_headers):
                idx = header_index.get(header)
                value = ""
                if idx is not None and idx < len(row):
                    value = str(row[idx]) if row[idx] is not None else ""
                item = QTableWidgetItem(value)
                self.review_table.setItem(row_idx, col_idx, item)

    def _prepare_mapping_page_state(self):
        """Prepare mapping-page-specific state before populating data."""
        # Load worksheet list for Excel files when applicable
        if self.source_tabs.currentIndex() == 0:
            file_path = self.file_path_edit.text().strip()
            self._load_sheet_names(file_path)
        else:
            # Text source has no sheets
            self._selected_sheet = None
            self._selected_sheets = []
            self.sheet_label.setVisible(False)
            self.sheet_combo.setVisible(False)
            self.import_all_sheets_check.setVisible(False)

        # Ensure preview skip-rows starts at zero for fresh configuration
        self.preview_skip_rows_spin.blockSignals(True)
        if self.preview_skip_rows_spin.value() < 0:
            self.preview_skip_rows_spin.setValue(0)
        self.preview_skip_rows_spin.blockSignals(False)

    def _load_sheet_names(self, file_path: str):
        """Load worksheet names for an Excel file into the sheet selector."""
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.blockSignals(False)
        self.sheet_label.setVisible(False)
        self.sheet_combo.setVisible(False)
        self._selected_sheet = None
        self._selected_sheets = []
        self.import_all_sheets_check.setVisible(False)
        self.import_all_sheets_check.setChecked(False)

        if not file_path or not os.path.exists(file_path):
            return
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in (".xlsx", ".xls"):
            return

        try:
            sheet_names = self.importer.get_excel_sheet_names(file_path)
        except Exception as exc:
            logger.error(f"Failed to get Excel sheet names: {exc}", exc_info=True)
            return

        if not sheet_names:
            return

        self.sheet_combo.blockSignals(True)
        for name in sheet_names:
            self.sheet_combo.addItem(name)
        self.sheet_combo.blockSignals(False)

        # Select the first sheet by default
        self._selected_sheet = sheet_names[0]
        self.sheet_combo.setCurrentIndex(0)
        self.sheet_label.setVisible(True)
        self.sheet_combo.setVisible(True)
        self.import_all_sheets_check.setVisible(True)

    def _on_sheet_changed(self, sheet_name: str):
        """Handle user changing the worksheet selection."""
        if self.import_all_sheets_check.isChecked():
            # When importing all sheets, individual selection is informational only
            self._selected_sheet = None
        else:
            self._selected_sheet = sheet_name or None
        self._selected_sheets = []
        # Refresh data and preview based on the newly selected sheet
        self._populate_mapping_page()

    def _on_import_all_sheets_toggled(self, checked: bool):
        """Toggle between single-sheet import and all-sheets import."""
        if checked:
            # Cache all sheet names from the combo
            self._selected_sheets = [
                self.sheet_combo.itemText(i) for i in range(self.sheet_combo.count())
            ]
            self._selected_sheet = None
        else:
            self._selected_sheets = []
            current = self.sheet_combo.currentText()
            self._selected_sheet = current or None
        self._populate_mapping_page()

    def _on_preview_skip_rows_changed(self, value: int):
        """When the preview skip-rows is changed, update the active source control and preview."""
        self._populate_mapping_page()

    def _on_preview_item_changed(self, item: QTableWidgetItem):
        """Keep the internal data model in sync with edits made in the preview table."""
        if self._updating_preview:
            return
        row = item.row()
        col = item.column()
        if row < 0 or col < 0:
            return
        if row >= len(self._data):
            return
        # Ensure the row has enough columns
        while len(self._data[row]) <= col:
            self._data[row].append("")
        self._data[row][col] = item.text()
        # Re-evaluate highlighting for this row
        self._update_preview_error_highlighting()

    def _update_preview_error_highlighting(self):
        """Highlight rows in the preview that are missing required fields."""
        if not self._data or not self._headers:
            return
        if self.preview_table.rowCount() == 0:
            return

        field_mapping = self._field_mapping or self._collect_field_mapping()
        header_index = {header: idx for idx, header in enumerate(self._headers)}
        ip_headers = field_mapping.get("ip_address", [])
        host_headers = field_mapping.get("hostname", [])

        for row_idx in range(self.preview_table.rowCount()):
            # Determine if this row has the required values
            has_required = False
            if row_idx < len(self._data):
                row = self._data[row_idx]
                ip_value = ""
                hostname_value = ""
                for header in ip_headers:
                    idx = header_index.get(header)
                    if idx is not None and idx < len(row):
                        ip_value = (
                            str(row[idx]).strip() if row[idx] is not None else ""
                        )
                        if ip_value:
                            break
                for header in host_headers:
                    idx = header_index.get(header)
                    if idx is not None and idx < len(row):
                        hostname_value = (
                            str(row[idx]).strip() if row[idx] is not None else ""
                        )
                        if hostname_value:
                            break
                has_required = bool(ip_value or hostname_value)

            # Apply coloring/tooltips to the entire row
            for col_idx in range(self.preview_table.columnCount()):
                item = self.preview_table.item(row_idx, col_idx)
                if item is None:
                    item = QTableWidgetItem("")
                    self.preview_table.setItem(row_idx, col_idx, item)
                if has_required:
                    item.setBackground(QColor(Qt.white))
                    item.setToolTip("")
                else:
                    item.setBackground(QColor("#ffe6e6"))
                    item.setToolTip(
                        "Row is missing both IP address and hostname and will be skipped."
                    )

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
                    "skip_rows": self.preview_skip_rows_spin.value(),
                    "sheet_name": self._selected_sheet,
                    "sheet_names": self._selected_sheets or None,
                }
            )
            success, stats = self.importer.import_from_file(file_path, options)
        else:
            text = self.text_edit.toPlainText().strip()
            options.update(
                {
                    "delimiter": self.text_delimiter_combo.currentText(),
                    "has_header": self.text_has_header_check.isChecked(),
                    "skip_rows": self.preview_skip_rows_spin.value(),
                }
            )
            success, stats = self.importer.import_from_text(text, options)

        progress.close()
        self.import_stats = stats
        self.import_success = success

        # Build a detailed summary including reasons for skipped rows (when available)
        base_msg = (
            f"Imported: {stats.get('imported_count', 0)}\n"
            f"Skipped: {stats.get('skipped_count', 0)}\n"
            f"Errors: {stats.get('error_count', 0)}"
        )
        skipped_reasons = stats.get("skipped_reasons") or []
        if skipped_reasons:
            # Only show the first few reasons to avoid overwhelming the dialog
            max_details = 10
            reason_lines = "\n".join(
                f"- {reason}" for reason in skipped_reasons[:max_details]
            )
            if len(skipped_reasons) > max_details:
                reason_lines += f"\n… and {len(skipped_reasons) - max_details} more skipped row(s)."
            base_msg += "\n\nReasons for skipped rows:\n" + reason_lines

        if success:
            QMessageBox.information(
                self,
                "Import Successful",
                base_msg,
            )
        else:
            QMessageBox.warning(
                self,
                "Import Completed",
                base_msg,
            )

        return success

    def _update_auto_detect_info(self):
        """Show the resolved delimiter/encoding when auto-detect options are used."""
        parts = []
        if self.source_tabs.currentIndex() == 0:
            # File source
            if self.file_delimiter_combo.currentText() == "Auto-detect":
                detected = getattr(self.importer, "last_detected_delimiter", None)
                if detected:
                    parts.append(f"Detected delimiter: '{detected}'")
            if self.file_encoding_combo.currentText() == "Auto-detect":
                detected_enc = getattr(self.importer, "last_detected_encoding", None)
                if detected_enc:
                    parts.append(f"Detected encoding: {detected_enc}")
        else:
            # Text source
            if self.text_delimiter_combo.currentText() == "Auto-detect":
                detected = getattr(self.importer, "last_detected_delimiter", None)
                if detected:
                    parts.append(f"Detected delimiter: '{detected}'")
        self.auto_detect_info_label.setText(" • ".join(parts))

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
