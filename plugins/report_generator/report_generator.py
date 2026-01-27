#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Report Generator Plugin for NetWORKS
"""

import csv
import datetime
import html
import io
import json
import re
import uuid
from pathlib import Path

import ipaddress
from loguru import logger
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QAction
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
    QStyle,
)

from src.core.plugin_interface import PluginInterface
from src.ui.plugin_ui_theme import mark_plugin_ui
from src.ui.theme import get_theme_tokens
from src.ui.material_icons import material_icon


DATA_SOURCE_LABELS = [
    "All Devices",
    "Selected Devices",
    "Group",
    "Subnet",
    "Tag",
]

DATA_SOURCE_MAP = {
    "All Devices": "all",
    "Selected Devices": "selected",
    "Group": "group",
    "Subnet": "subnet",
    "Tag": "tag",
}

DATA_SOURCE_REVERSE = {value: key for key, value in DATA_SOURCE_MAP.items()}

MODE_LABELS = ["Table", "Template"]
MODE_MAP = {"Table": "table", "Template": "template"}
MODE_REVERSE = {value: key for key, value in MODE_MAP.items()}

FILTER_OPERATORS = [
    "equals",
    "not_equals",
    "contains",
    "starts_with",
    "ends_with",
    "regex",
    ">",
    ">=",
    "<",
    "<=",
]

TRANSFORM_TYPES = [
    "upper",
    "lower",
    "title",
    "prefix",
    "suffix",
    "date_format",
    "concat",
]

EXPORT_FORMATS = ["HTML", "JSON", "CSV", "TXT"]

# Standard device properties (from Device model). All others are custom.
STANDARD_DEVICE_PROPERTIES = (
    "id", "alias", "hostname", "ip_address", "mac_address", "status", "notes", "tags"
)


def default_report_definition():
    return {
        "id": str(uuid.uuid4()),
        "name": "New Report",
        "mode": "table",
        "data_source": {
            "type": "all",
            "group": "",
            "subnet": "",
            "tag": "",
        },
        "filters": [],
        "filter_logic": "AND",
        "columns": [],
        "column_options": {},
        "computed_columns": [],
        "transformations": [],
        "sort": {"column": "", "direction": "asc"},
        "sorts": [],
        "template": {"header": "", "item": "{{alias}}", "footer": ""},
        "output": {"format": "HTML"},
    }


def sanitize_value(value):
    if isinstance(value, list):
        return ", ".join([str(v) for v in value])
    if value is None:
        return ""
    return str(value)


def apply_date_format(value, fmt):
    if not value:
        return ""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime(fmt)
    try:
        parsed = datetime.datetime.fromisoformat(str(value))
        return parsed.strftime(fmt)
    except Exception:
        return sanitize_value(value)


def parse_concat_parts(value):
    parts = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if (part.startswith('"') and part.endswith('"')) or (part.startswith("'") and part.endswith("'")):
            parts.append(("literal", part[1:-1]))
        else:
            parts.append(("property", part))
    return parts


def apply_transform(value, transform, transform_value, context=None):
    base_value = sanitize_value(value)
    if transform == "upper":
        return base_value.upper()
    if transform == "lower":
        return base_value.lower()
    if transform == "title":
        return base_value.title()
    if transform == "prefix":
        return f"{sanitize_value(transform_value)}{base_value}"
    if transform == "suffix":
        return f"{base_value}{sanitize_value(transform_value)}"
    if transform == "date_format":
        return apply_date_format(value, sanitize_value(transform_value) or "%Y-%m-%d")
    if transform == "concat":
        if context is None:
            return base_value
        parts = parse_concat_parts(sanitize_value(transform_value))
        resolved = []
        for part_type, part_value in parts:
            if part_type == "literal":
                resolved.append(part_value)
            else:
                resolved.append(sanitize_value(context.get(part_value, "")))
        return "".join(resolved)
    return base_value


def build_transform_map(transformations):
    transform_map = {}
    for transform in transformations:
        target = (transform.get("target") or "").strip()
        if not target:
            continue
        transform_map.setdefault(target, []).append(transform)
    return transform_map


def apply_transforms_for_target(value, target, transform_map, context):
    if target not in transform_map:
        return value
    transformed_value = value
    for transform in transform_map[target]:
        transformed_value = apply_transform(
            transformed_value,
            transform.get("transform"),
            transform.get("value"),
            context,
        )
    return transformed_value


def is_expression_line(line):
    if "+" not in line:
        return False
    expression_pattern = re.compile(
        r'^\s*(?:\{\{[^}]+\}\}|"[^"]*"|\'[^\']*\'|\+|\s+)+\s*$'
    )
    return bool(expression_pattern.match(line))


def render_expression_line(line, context):
    token_pattern = re.compile(r'\{\{[^}]+\}\}|"[^"]*"|\'[^\']*\'|\+')
    parts = []
    for token in token_pattern.findall(line):
        token = token.strip()
        if not token or token == "+":
            continue
        if token.startswith("{{"):
            key = token[2:-2].strip()
            parts.append(sanitize_value(context.get(key, "")))
        elif token.startswith('"') or token.startswith("'"):
            parts.append(token[1:-1])
        else:
            parts.append(token)
    return "".join(parts)


def render_template_text(template_text, context):
    if not template_text:
        return ""
    rendered_lines = []
    placeholder_pattern = re.compile(r"\{\{\s*([^}]+)\s*\}\}")
    for line in template_text.splitlines():
        if is_expression_line(line):
            rendered_lines.append(render_expression_line(line, context))
            continue
        rendered_lines.append(
            placeholder_pattern.sub(lambda match: sanitize_value(context.get(match.group(1), "")), line)
        )
    return "\n".join(rendered_lines)


def parse_subnet(subnet_text):
    subnet_text = subnet_text.strip()
    if not subnet_text:
        return None
    try:
        return ipaddress.ip_network(subnet_text, strict=False)
    except Exception:
        return None


def ip_in_subnet(ip_address, subnet):
    if not subnet:
        return False
    try:
        return ipaddress.ip_address(ip_address) in subnet
    except Exception:
        return False


class ReportStorage:
    def __init__(self, device_manager):
        self.device_manager = device_manager
        self._cached_workspace = None
        self._reports = []

    def _reports_path(self):
        workspace = self.device_manager.current_workspace or "default"
        base_dir = Path(self.device_manager.workspaces_dir) / workspace / "plugins" / "report_generator"
        return base_dir / "reports.json"

    def ensure_loaded(self):
        workspace = self.device_manager.current_workspace or "default"
        if workspace != self._cached_workspace:
            self.load()
        return self._reports

    def load(self):
        path = self._reports_path()
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, list):
                    self._reports = data
                else:
                    self._reports = []
            except Exception as exc:
                logger.error(f"Report Generator: Failed to load reports: {exc}")
                self._reports = []
        else:
            self._reports = []
        self._cached_workspace = self.device_manager.current_workspace or "default"
        return self._reports

    def save(self, reports):
        path = self._reports_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(reports, handle, indent=2)
            self._reports = reports
            self._cached_workspace = self.device_manager.current_workspace or "default"
            return True
        except Exception as exc:
            logger.error(f"Report Generator: Failed to save reports: {exc}")
            return False


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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        menu_bar = QMenuBar()
        menu_bar.setNativeMenuBar(False)
        menu_bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("New Report", self.create_report)
        file_menu.addAction("Duplicate Report", self.duplicate_report)
        file_menu.addAction("Delete Report", self.delete_report)
        file_menu.addSeparator()
        file_menu.addAction("Manage Reports...", self.open_report_manager)
        file_menu.addSeparator()
        file_menu.addAction("Save Report", self.save_report)
        file_menu.addAction("Save Report As...", self.save_report_as)
        file_menu.addAction("Export Report", self.export_report)
        file_menu.addSeparator()
        file_menu.addAction("Clear Current", self.clear_current_report)
        layout.setMenuBar(menu_bar)

        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(2, 0, 2, 0)
        top_bar_layout.setSpacing(8)
        top_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_bar.setMinimumHeight(26)
        top_bar.setMaximumHeight(26)

        self.current_report_label = QLabel("No report selected")
        self.current_report_label.setWordWrap(True)
        title_font = self.current_report_label.font()
        title_font.setPointSize(title_font.pointSize() + 1)
        title_font.setBold(True)
        self.current_report_label.setFont(title_font)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.current_report_label, alignment=Qt.AlignCenter)
        top_bar_layout.addStretch()
        layout.addWidget(top_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter)

        form_panel = QWidget()
        form_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignTop)
        form_layout.addWidget(scroll_area)

        form_container = QWidget()
        form_container.setMinimumWidth(700)
        scroll_area.setWidget(form_container)
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(8)

        quick_group = QGroupBox("Quick Start")
        quick_layout = QVBoxLayout(quick_group)
        quick_label = QLabel(
            "1) Name your report\n"
            "2) Choose a data source\n"
            "3) Select columns (table) or write a template\n"
            "4) Generate a preview\n"
            "5) Export to a file"
        )
        quick_label.setWordWrap(True)
        quick_layout.addWidget(quick_label)
        form_layout.addWidget(quick_group)

        details_group = QGroupBox("Report Details")
        details_layout = QFormLayout(details_group)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Weekly Inventory")
        self.name_edit.textChanged.connect(self._schedule_preview)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(MODE_LABELS)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.mode_combo.currentTextChanged.connect(self._schedule_preview)
        details_layout.addRow("Name:", self.name_edit)
        details_layout.addRow("Mode:", self.mode_combo)
        form_layout.addWidget(details_group)

        source_group = QGroupBox("Data Source")
        source_layout = QFormLayout(source_group)
        self.source_combo = QComboBox()
        self.source_combo.addItems(DATA_SOURCE_LABELS)
        self.source_combo.currentTextChanged.connect(self._on_source_changed)
        self.source_combo.currentTextChanged.connect(self._schedule_preview)

        self.group_combo = QComboBox()
        self.group_combo.currentTextChanged.connect(self._schedule_preview)
        self.subnet_edit = QLineEdit()
        self.subnet_edit.setPlaceholderText("e.g. 192.168.1.0/24")
        self.subnet_edit.textChanged.connect(self._schedule_preview)
        self.tag_edit = QLineEdit()
        self.tag_edit.setPlaceholderText("e.g. core")
        self.tag_edit.textChanged.connect(self._schedule_preview)

        source_layout.addRow("Source:", self.source_combo)
        source_layout.addRow("Group:", self.group_combo)
        source_layout.addRow("Subnet:", self.subnet_edit)
        source_layout.addRow("Tag:", self.tag_edit)
        source_help = QLabel("Tip: Use Selected Devices from the table for quick reports.")
        source_help.setWordWrap(True)
        source_layout.addRow("", source_help)
        form_layout.addWidget(source_group)

        self.table_controls_group = QFrame()
        self.table_controls_group.setFrameShape(QFrame.NoFrame)
        wizard_layout = QVBoxLayout(self.table_controls_group)
        wizard_layout.setContentsMargins(0, 0, 0, 0)

        self.wizard_tabs = QTabWidget()
        self.wizard_tabs.setDocumentMode(True)

        # ---- Tab 1: Columns ----
        columns_tab = QWidget()
        col_layout = QVBoxLayout(columns_tab)
        col_splitter = QSplitter(Qt.Horizontal)
        col_splitter.setChildrenCollapsible(False)

        available_panel = QGroupBox("Available Fields")
        av_layout = QVBoxLayout(available_panel)
        self.column_search_edit = QLineEdit()
        self.column_search_edit.setPlaceholderText("Search fields...")
        self.column_search_edit.textChanged.connect(self._filter_available_columns)
        av_layout.addWidget(self.column_search_edit)
        self.available_columns_list = QListWidget()
        self.available_columns_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.available_columns_list.itemDoubleClicked.connect(self._add_available_column_to_selected)
        av_layout.addWidget(self.available_columns_list)
        add_one_btn = QPushButton("Add →")
        add_one_btn.clicked.connect(self._add_selected_available_to_columns)
        add_all_btn = QPushButton("Add All")
        add_all_btn.clicked.connect(self._add_all_available_columns)
        av_layout.addWidget(add_one_btn)
        av_layout.addWidget(add_all_btn)
        col_splitter.addWidget(available_panel)

        selected_panel = QGroupBox("Selected Columns")
        sel_layout = QVBoxLayout(selected_panel)
        self.columns_list = QListWidget()
        self.columns_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.columns_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.columns_list.setDefaultDropAction(Qt.MoveAction)
        if self.columns_list.model():
            self.columns_list.model().rowsMoved.connect(self._on_columns_reordered)
        self.columns_list.itemSelectionChanged.connect(self._on_selected_column_changed)
        sel_layout.addWidget(self.columns_list)
        col_options_row = QHBoxLayout()
        self.column_visible_check = QCheckBox("Visible")
        self.column_visible_check.setChecked(True)
        self.column_visible_check.toggled.connect(self._apply_column_options_to_selection)
        self.column_header_edit = QLineEdit()
        self.column_header_edit.setPlaceholderText("Custom header (optional)")
        self.column_header_edit.textChanged.connect(self._apply_column_options_to_selection)
        col_options_row.addWidget(self.column_visible_check)
        col_options_row.addWidget(QLabel("Header:"))
        col_options_row.addWidget(self.column_header_edit, 1)
        sel_layout.addLayout(col_options_row)
        sel_buttons = QHBoxLayout()
        self.remove_column_button = QPushButton("Remove Selected")
        remove_all_btn = QPushButton("Remove All")
        sel_buttons.addWidget(self.remove_column_button)
        sel_buttons.addWidget(remove_all_btn)
        sel_layout.addLayout(sel_buttons)
        self.remove_column_button.clicked.connect(self.remove_selected_columns)
        remove_all_btn.clicked.connect(self._remove_all_columns)
        self.add_column_button = QPushButton("Add Column…")
        self.add_column_button.clicked.connect(self.show_add_column_menu)
        sel_layout.addWidget(self.add_column_button)
        col_splitter.addWidget(selected_panel)
        col_splitter.setStretchFactor(0, 1)
        col_splitter.setStretchFactor(1, 1)
        col_layout.addWidget(col_splitter)
        self.wizard_tabs.addTab(columns_tab, "Columns")

        # ---- Tab 2: Filters ----
        filters_tab = QWidget()
        ft_layout = QVBoxLayout(filters_tab)
        filters_group = QGroupBox("Filters")
        filters_layout = QVBoxLayout(filters_group)
        filter_logic_row = QHBoxLayout()
        filter_logic_row.addWidget(QLabel("Combine with:"))
        self.filter_logic_combo = QComboBox()
        self.filter_logic_combo.addItems(["AND", "OR"])
        self.filter_logic_combo.currentTextChanged.connect(self._schedule_preview)
        filter_logic_row.addWidget(self.filter_logic_combo)
        filter_logic_row.addStretch()
        filters_layout.addLayout(filter_logic_row)
        filters_help = QLabel("Each row: [Field] [Operator] [Value]. Property names: alias, ip_address, status, tags, etc.")
        filters_help.setWordWrap(True)
        filters_layout.addWidget(filters_help)
        self.filters_table = QTableWidget(0, 3)
        self.filters_table.setHorizontalHeaderLabels(["Property", "Operator", "Value"])
        self.filters_table.horizontalHeader().setStretchLastSection(True)
        self.filters_table.itemChanged.connect(self._schedule_preview)
        filters_layout.addWidget(self.filters_table)
        filter_buttons = QHBoxLayout()
        self.add_filter_button = QPushButton("+ Add Filter")
        self.remove_filter_button = QPushButton("Remove Selected")
        filter_buttons.addWidget(self.add_filter_button)
        filter_buttons.addWidget(self.remove_filter_button)
        filters_layout.addLayout(filter_buttons)
        self.add_filter_button.clicked.connect(self.add_filter_row)
        self.remove_filter_button.clicked.connect(self.remove_selected_rows)
        ft_layout.addWidget(filters_group)
        self.wizard_tabs.addTab(filters_tab, "Filters")

        # ---- Tab 3: Sorting ----
        sort_tab = QWidget()
        st_layout = QVBoxLayout(sort_tab)
        self.sort_group = QGroupBox("Sort Rules")
        sort_layout = QVBoxLayout(self.sort_group)
        sort_help = QLabel("Order: 1, 2, 3… Drag or use Move Up/Down to change priority.")
        sort_help.setWordWrap(True)
        sort_layout.addWidget(sort_help)
        self.sorts_table = QTableWidget(0, 3)
        self.sorts_table.setHorizontalHeaderLabels(["#", "Column", "Direction"])
        self.sorts_table.horizontalHeader().setStretchLastSection(True)
        self.sorts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sorts_table.setSelectionMode(QAbstractItemView.SingleSelection)
        sort_layout.addWidget(self.sorts_table)
        sort_buttons = QHBoxLayout()
        self.add_sort_button = QPushButton("+ Add Sort Level")
        self.remove_sort_button = QPushButton("Remove Selected")
        self.sort_up_button = QPushButton("Move Up")
        self.sort_down_button = QPushButton("Move Down")
        sort_buttons.addWidget(self.add_sort_button)
        sort_buttons.addWidget(self.remove_sort_button)
        sort_buttons.addWidget(self.sort_up_button)
        sort_buttons.addWidget(self.sort_down_button)
        sort_layout.addLayout(sort_buttons)
        self.add_sort_button.clicked.connect(self.add_sort_row)
        self.remove_sort_button.clicked.connect(self.remove_selected_sorts)
        self.sort_up_button.clicked.connect(lambda: self._move_sort_rows(-1))
        self.sort_down_button.clicked.connect(lambda: self._move_sort_rows(1))
        st_layout.addWidget(self.sort_group)
        self.wizard_tabs.addTab(sort_tab, "Sorting")

        wizard_layout.addWidget(self.wizard_tabs)
        form_layout.addWidget(self.table_controls_group)

        self.template_group = QGroupBox("Template Settings")
        template_layout = QVBoxLayout(self.template_group)
        self.template_header_edit = QTextEdit()
        self.template_item_edit = QTextEdit()
        self.template_footer_edit = QTextEdit()
        self.template_header_edit.setPlaceholderText("Optional header text")
        self.template_item_edit.setPlaceholderText("e.g. {{alias}} ({{ip_address}})")
        self.template_footer_edit.setPlaceholderText("Optional footer text")
        self.template_header_edit.textChanged.connect(self._schedule_preview)
        self.template_item_edit.textChanged.connect(self._schedule_preview)
        self.template_footer_edit.textChanged.connect(self._schedule_preview)
        tl_form = QFormLayout()
        tl_form.addRow("Header:", self.template_header_edit)
        tl_form.addRow("Item:", self.template_item_edit)
        tl_form.addRow("Footer:", self.template_footer_edit)
        template_layout.addLayout(tl_form)
        props_help = QLabel("Available properties (use {{property_name}} in templates):")
        props_help.setWordWrap(True)
        template_layout.addWidget(props_help)
        self.template_properties_label = QLabel()
        self.template_properties_label.setWordWrap(True)
        self.template_properties_label.setStyleSheet("color: var(--text-muted, #666); font-size: 0.95em;")
        template_layout.addWidget(self.template_properties_label)
        form_layout.addWidget(self.template_group)


        actions_help = QLabel("Tip: Save reports you want to reuse across sessions.")
        actions_help.setWordWrap(True)
        form_layout.addWidget(actions_help)

        preview_panel = QWidget()
        preview_panel.setMinimumWidth(360)
        preview_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)

        output_group = QGroupBox("Output")
        output_layout = QFormLayout(output_group)
        self.format_combo = QComboBox()
        self.format_combo.addItems(EXPORT_FORMATS)
        self.format_combo.currentTextChanged.connect(self._schedule_preview)
        self.filename_template_edit = QLineEdit()
        self.filename_template_edit.setPlaceholderText("{name}_{date}_{time}")
        self.filename_template_edit.setText("{name}_{date}_{time}")
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Choose where to save the exported report")
        self.browse_button = QPushButton("Browse")
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit)
        path_row.addWidget(self.browse_button)
        output_layout.addRow("Format:", self.format_combo)
        output_layout.addRow("Filename Template:", self.filename_template_edit)
        output_layout.addRow("File:", path_row)
        output_help = QLabel("Filename variables: {name}, {date}, {time}. Preview shows export content.")
        output_help.setWordWrap(True)
        output_layout.addRow("", output_help)
        self.browse_button.clicked.connect(self.browse_output_path)

        output_actions = QHBoxLayout()
        self.save_button = QPushButton("Save Report")
        self.preview_button = QPushButton("Generate Preview")
        self.export_button = QPushButton("Export Report")
        output_actions.addWidget(self.save_button)
        output_actions.addWidget(self.preview_button)
        output_actions.addWidget(self.export_button)
        output_layout.addRow("", output_actions)
        preview_layout.addWidget(output_group)

        preview_group = QGroupBox("Preview")
        preview_group_layout = QVBoxLayout(preview_group)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setLineWrapMode(QTextEdit.NoWrap)
        preview_group_layout.addWidget(self.preview_text)
        preview_layout.addWidget(preview_group)

        self.save_button.clicked.connect(self.save_report)
        self.preview_button.clicked.connect(self.generate_preview)
        self.export_button.clicked.connect(self.export_report)

        splitter.addWidget(form_panel)
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([740, 520])

        self._on_mode_changed(self.mode_combo.currentText())
        self._on_source_changed(self.source_combo.currentText())

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
        self._update_current_report_label()
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
        self._update_current_report_label()
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

    def _update_current_report_label(self):
        report = self._get_current_report()
        if not report:
            self.current_report_label.setText("No report selected")
            return
        name = report.get("name", "Unnamed Report")
        mode = report.get("mode", "table").title()
        self.current_report_label.setText(f"{name} ({mode})")

    def open_report_manager(self):
        dialog = QDialog(self)
        mark_plugin_ui(dialog)
        dialog.setWindowTitle("Manage Reports")
        dialog.resize(520, 420)

        layout = QVBoxLayout(dialog)
        report_list = QListWidget()
        layout.addWidget(report_list)

        def refresh_list():
            report_list.clear()
            for report in self.reports:
                item = QListWidgetItem(report.get("name", "Unnamed Report"))
                item.setData(Qt.UserRole, report.get("id"))
                report_list.addItem(item)
            current_id = self.current_report_id
            if current_id:
                for row in range(report_list.count()):
                    item = report_list.item(row)
                    if item.data(Qt.UserRole) == current_id:
                        report_list.setCurrentRow(row)
                        break

        def on_selection_changed():
            selected = report_list.selectedItems()
            if not selected:
                return
            report_id = selected[0].data(Qt.UserRole)
            self._select_report(report_id)

        report_list.itemSelectionChanged.connect(on_selection_changed)

        button_row = QHBoxLayout()
        new_button = QPushButton("New")
        duplicate_button = QPushButton("Duplicate")
        delete_button = QPushButton("Delete")
        button_row.addWidget(new_button)
        button_row.addWidget(duplicate_button)
        button_row.addWidget(delete_button)
        layout.addLayout(button_row)

        def on_new():
            self.create_report()
            refresh_list()

        def on_duplicate():
            self.duplicate_report()
            refresh_list()

        def on_delete():
            self.delete_report()
            refresh_list()

        new_button.clicked.connect(on_new)
        duplicate_button.clicked.connect(on_duplicate)
        delete_button.clicked.connect(on_delete)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        refresh_list()
        dialog.exec()

    def _render_json_preview(self, content):
        try:
            data = json.loads(content)
        except Exception:
            return f"<pre>{html.escape(content)}</pre>"

        def render_node(node):
            if isinstance(node, dict):
                items = []
                for key, value in node.items():
                    items.append(
                        f"<details><summary>{html.escape(str(key))}</summary>{render_node(value)}</details>"
                    )
                return "".join(items) or "<em>{}</em>"
            if isinstance(node, list):
                items = []
                for index, value in enumerate(node):
                    items.append(
                        f"<details><summary>[{index}]</summary>{render_node(value)}</details>"
                    )
                return "".join(items) or "<em>[]</em>"
            return f"<pre>{html.escape(sanitize_value(node))}</pre>"

        return render_node(data)

    def _render_csv_preview(self, content):
        buffer = io.StringIO(content)
        try:
            reader = csv.reader(buffer)
            rows = list(reader)
        except Exception:
            return f"<pre>{html.escape(content)}</pre>"
        if not rows:
            return "<em>No data</em>"
        header = rows[0]
        body = rows[1:]
        header_cells = "".join(f"<th>{html.escape(cell)}</th>" for cell in header)
        body_rows = []
        for row in body:
            cells = "".join(f"<td>{html.escape(cell)}</td>" for cell in row)
            body_rows.append(f"<tr>{cells}</tr>")
        table_html = (
            "<table border='1' cellspacing='0' cellpadding='4' style='white-space: nowrap;'>"
            f"<thead><tr>{header_cells}</tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody></table>"
        )
        return table_html

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
        devices = self._resolve_devices(report)
        if not devices:
            return "", "No devices matched the report criteria."

        filters = report.get("filters", [])
        filter_logic = report.get("filter_logic", "AND")
        devices = self._apply_filters(devices, filters, filter_logic)
        if not devices:
            return "", "No devices matched the filters."

        mode = report.get("mode", "table")
        transformations = report.get("transformations", [])
        transform_map = build_transform_map(transformations)

        computed_columns = report.get("computed_columns", [])
        rows = self._build_rows(devices, report, transform_map)

        if mode == "template":
            return self._render_template_report(report, devices, rows, transform_map)
        return self._render_table_report(report, rows, computed_columns)

    def _resolve_devices(self, report):
        data_source = report.get("data_source", {})
        source_type = data_source.get("type", "all")
        if source_type == "selected":
            return self.plugin.device_manager.get_selected_devices()
        if source_type == "group":
            group = self.plugin.device_manager.get_group(data_source.get("group"))
            return group.get_all_devices() if group else []
        if source_type == "subnet":
            subnet = parse_subnet(data_source.get("subnet", ""))
            return [
                device
                for device in self.plugin.device_manager.get_devices()
                if ip_in_subnet(device.get_property("ip_address", ""), subnet)
            ]
        if source_type == "tag":
            tag = data_source.get("tag", "").strip().lower()
            if not tag:
                return []
            results = []
            for device in self.plugin.device_manager.get_devices():
                tags = device.get_property("tags", []) or []
                tag_values = [str(t).lower() for t in tags]
                if tag in tag_values:
                    results.append(device)
            return results
        return self.plugin.device_manager.get_devices()

    def _apply_filters(self, devices, filters, filter_logic="AND"):
        if not filters:
            return devices
        use_or = (filter_logic or "AND").strip().upper() == "OR"
        filtered = []
        for device in devices:
            properties = device.get_properties()
            if use_or:
                passes = any(
                    self._filter_match(properties.get(flt.get("property")), flt.get("operator", "equals"), flt.get("value", ""))
                    for flt in filters
                )
            else:
                passes = True
                for flt in filters:
                    if not self._filter_match(properties.get(flt.get("property")), flt.get("operator", "equals"), flt.get("value", "")):
                        passes = False
                        break
            if passes:
                filtered.append(device)
        return filtered

    def _filter_match(self, actual, operator, expected):
        if operator in (">", ">=", "<", "<="):
            try:
                actual_val = float(actual)
                expected_val = float(expected)
            except Exception:
                return False
            if operator == ">":
                return actual_val > expected_val
            if operator == ">=":
                return actual_val >= expected_val
            if operator == "<":
                return actual_val < expected_val
            if operator == "<=":
                return actual_val <= expected_val
        actual_text = sanitize_value(actual)
        expected_text = sanitize_value(expected)
        actual_lower = actual_text.lower()
        expected_lower = expected_text.lower()
        if operator == "equals":
            return actual_lower == expected_lower
        if operator == "not_equals":
            return actual_lower != expected_lower
        if operator == "contains":
            if isinstance(actual, list):
                actual_values = [sanitize_value(item).lower() for item in actual]
                return expected_lower in actual_values
            return expected_lower in actual_lower
        if operator == "starts_with":
            return actual_lower.startswith(expected_lower)
        if operator == "ends_with":
            return actual_lower.endswith(expected_lower)
        if operator == "regex":
            try:
                return re.search(expected_text, actual_text) is not None
            except re.error:
                return False
        return False

    def _build_rows(self, devices, report, transform_map):
        columns = report.get("columns", [])
        if not columns:
            columns = self._collect_device_properties()
        computed_columns = report.get("computed_columns", [])
        rows = []
        for device in devices:
            properties = device.get_properties()
            context = {key: sanitize_value(value) for key, value in properties.items()}
            row = {}
            for column in columns:
                value = properties.get(column, "")
                transformed = apply_transforms_for_target(value, column, transform_map, context)
                row[column] = sanitize_value(transformed)
            for computed in computed_columns:
                name = computed.get("name", "")
                parts = computed.get("parts", "")
                computed_value = apply_transform("", "concat", parts, context)
                transformed = apply_transforms_for_target(computed_value, name, transform_map, context)
                row[name] = sanitize_value(transformed)
            rows.append(row)
        sort_definitions = report.get("sorts") or []
        if not sort_definitions:
            legacy_sort = report.get("sort", {})
            if legacy_sort.get("column"):
                sort_definitions = [legacy_sort]
        for sort_def in reversed(sort_definitions):
            sort_column = (sort_def.get("column") or "").strip()
            if not sort_column:
                continue
            rows.sort(
                key=lambda r, column=sort_column: r.get(column, ""),
                reverse=sort_def.get("direction") == "desc",
            )
        return rows

    def _render_table_report(self, report, rows, computed_columns):
        output_format = report.get("output", {}).get("format", "HTML")
        columns = report.get("columns", []) or self._collect_device_properties()
        computed_names = [col.get("name") for col in computed_columns if col.get("name")]
        opts = report.get("column_options") or {}
        visible = lambda c: opts.get(c, {}).get("visible", True)
        header = lambda c: (opts.get(c, {}).get("header") or "").strip() or c
        all_names = [c for c in columns + computed_names if visible(c)]
        display_names = [header(c) for c in all_names]

        if output_format == "JSON":
            filtered = [{k: r[k] for k in all_names if k in r} for r in rows]
            return json.dumps(filtered, indent=2), None
        if output_format == "CSV":
            return self._rows_to_csv(rows, all_names, display_names), None
        if output_format == "TXT":
            return self._rows_to_txt(rows, all_names, display_names), None
        return self._rows_to_html(rows, all_names, report.get("name") or "Report", display_names), None

    def _render_template_report(self, report, devices, rows, transform_map):
        template = report.get("template", {})
        output_format = report.get("output", {}).get("format", "HTML")
        total = len(devices)
        content_lines = []
        header_context = {"total": total, "index": 0}
        header = render_template_text(template.get("header", ""), header_context)
        if header:
            content_lines.append(header)
        for index, device in enumerate(devices, start=1):
            base_context = device.get_properties()
            context = {key: sanitize_value(value) for key, value in base_context.items()}
            context["index"] = index
            context["total"] = total
            for computed in report.get("computed_columns", []):
                name = computed.get("name", "")
                parts = computed.get("parts", "")
                if name:
                    context[name] = sanitize_value(apply_transform("", "concat", parts, context))
            for key in list(context.keys()):
                context[key] = sanitize_value(
                    apply_transforms_for_target(context[key], key, transform_map, context)
                )
            content_lines.append(render_template_text(template.get("item", ""), context))
        footer_context = {"total": total, "index": total}
        footer = render_template_text(template.get("footer", ""), footer_context)
        if footer:
            content_lines.append(footer)
        content = "\n".join([line for line in content_lines if line is not None])
        if output_format == "JSON":
            return json.dumps({"content": content, "lines": content_lines}, indent=2), None
        if output_format == "CSV":
            return self._lines_to_csv(content_lines), None
        if output_format == "HTML":
            escaped = html.escape(content)
            content_html = f"<pre class='report-pre'>{escaped}</pre>"
            return self._wrap_report_html(content_html, report.get("name") or "Report"), None
        return content, None

    def _rows_to_html(self, rows, columns, title, display_headers=None):
        headers = display_headers if display_headers is not None else columns
        header_cells = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
        body_rows = []
        for row in rows:
            cells = "".join(f"<td>{html.escape(sanitize_value(row.get(col, '')))}</td>" for col in columns)
            body_rows.append(f"<tr>{cells}</tr>")
        table_html = f"<table><thead><tr>{header_cells}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
        return self._wrap_report_html(table_html, title)

    def _wrap_report_html(self, body_html, title):
        tokens = self._get_report_theme_tokens()
        color_scheme = "dark" if tokens.name == "dark" else "light"
        title_text = html.escape(title or "Report")
        font_size = tokens.font_size
        meta_size = max(font_size - 1, 8)
        return f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title_text}</title>
    <style>
        :root {{
            color-scheme: {color_scheme};
            --accent: {tokens.accent};
            --accent-soft: {tokens.accent_soft};
            --bg: {tokens.background};
            --surface: {tokens.surface};
            --surface-alt: {tokens.surface_alt};
            --surface-raised: {tokens.surface_raised};
            --border: {tokens.border};
            --text: {tokens.text};
            --text-muted: {tokens.text_muted};
            --header-bg: {tokens.header_bg};
            --header-text: {tokens.header_text};
            --table-alt: {tokens.table_alt};
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 16px;
            font-family: "Segoe UI", "San Francisco", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
            font-size: {font_size}px;
            color: var(--text);
            background: var(--bg);
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            white-space: nowrap;
        }}
        th, td {{
            border: 1px solid var(--border);
            padding: 2px 4px;
            text-align: left;
        }}
        th {{
            background: var(--header-bg);
            color: var(--header-text);
            font-weight: 600;
        }}
        tbody tr:nth-child(even) {{
            background: var(--table-alt);
        }}
        tbody tr:hover {{
            background: var(--surface-raised);
        }}
        .report-pre {{
            border: 1px solid var(--border);
            background: var(--surface);
            padding: 8px;
            white-space: pre-wrap;
        }}
        .report-meta {{
            color: var(--text-muted);
            font-size: {meta_size}px;
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    {body_html}
</body>
</html>
"""

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

    def _rows_to_csv(self, rows, columns, display_headers=None):
        buffer = io.StringIO()
        headers = display_headers if display_headers is not None else columns
        writer = csv.writer(buffer)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(col, "") for col in columns])
        return buffer.getvalue()

    def _lines_to_csv(self, lines):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["content"])
        for line in lines:
            writer.writerow([line])
        return buffer.getvalue()

    def _rows_to_txt(self, rows, columns, display_headers=None):
        headers = display_headers if display_headers is not None else columns
        header = "\t".join(headers)
        lines = [header]
        for row in rows:
            lines.append("\t".join(sanitize_value(row.get(col, "")) for col in columns))
        return "\n".join(lines)


class ReportBuilderDialog(QDialog):
    def __init__(self, plugin, prefill_source=None, parent=None):
        super().__init__(parent or plugin.main_window)
        mark_plugin_ui(self)
        self.setWindowTitle("Report Generator")
        self.setMinimumSize(1200, 700)
        self.resize(1420, 860)

        layout = QVBoxLayout(self)
        self.builder = ReportBuilderWidget(plugin, self)
        layout.addWidget(self.builder)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if prefill_source:
            self.builder.source_combo.setCurrentText(prefill_source)


class ReportGeneratorPlugin(PluginInterface):
    def __init__(self):
        super().__init__()
        self.storage = None
        self.actions = []
        self.toolbar_action = None
        self.menu_action = None
        self.context_action_name = "Generate Report"
        self._connected_signals = set()

    def initialize(self, app, plugin_info):
        self.app = app
        self.plugin_info = plugin_info
        self.main_window = app.main_window
        self.device_manager = app.device_manager

        self.storage = ReportStorage(self.device_manager)
        self.storage.ensure_loaded()

        self._register_actions()
        self._register_context_menu()
        self._connect_signals()

        self._initialized = True
        self.plugin_initialized.emit()
        logger.info("Report Generator plugin initialized")
        return True

    def _register_actions(self):
        self.menu_action = QAction("Report Generator", self.main_window)
        self.menu_action.triggered.connect(self.show_report_dialog)
        self.toolbar_action = QAction("Report Generator", self.main_window)
        self.toolbar_action.triggered.connect(self.show_report_dialog)
        if self.main_window:
            self.toolbar_action.setIcon(material_icon("description", self.main_window, QStyle.SP_FileDialogDetailedView))
        self.actions = [self.menu_action]
        return True

    def _register_context_menu(self):
        if hasattr(self.main_window, "device_table"):
            self.main_window.device_table.register_context_menu_action(
                self.context_action_name,
                self.show_report_dialog_for_selection,
                priority=560,
            )

    def _connect_signals(self):
        self.device_manager.device_added.connect(self.on_device_added)
        self.device_manager.device_removed.connect(self.on_device_removed)
        self.device_manager.device_changed.connect(self.on_device_changed)
        self.device_manager.group_added.connect(self.on_group_added)
        self.device_manager.group_removed.connect(self.on_group_removed)
        self._connected_signals.update(
            {"device_added", "device_removed", "device_changed", "group_added", "group_removed"}
        )

    def get_toolbar_actions(self):
        return [self.toolbar_action] if self.toolbar_action else []

    def get_menu_actions(self):
        return {"Tools": [self.menu_action]} if self.menu_action else {}

    def get_dock_widgets(self):
        return []

    def show_report_dialog(self):
        dialog = ReportBuilderDialog(self, parent=self.main_window)
        dialog.exec()

    def show_report_dialog_for_selection(self, devices):
        dialog = ReportBuilderDialog(self, prefill_source="Selected Devices", parent=self.main_window)
        dialog.exec()

    def on_device_added(self, _device):
        pass

    def on_device_removed(self, _device):
        pass

    def on_device_changed(self, _device):
        pass

    def on_group_added(self, _group):
        pass

    def on_group_removed(self, _group):
        pass

    def cleanup(self):
        if hasattr(self.main_window, "device_table"):
            try:
                self.main_window.device_table.unregister_context_menu_action(self.context_action_name)
            except Exception as exc:
                logger.debug(f"Report Generator: context menu cleanup failed: {exc}")
        return super().cleanup()


__all__ = ["ReportGeneratorPlugin"]
