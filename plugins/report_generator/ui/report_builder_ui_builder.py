# -*- coding: utf-8 -*-
"""
Builds the Report Builder widget UI (menu, form, preview). Called from ReportBuilderWidget._build_ui.
"""

from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenuBar,
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

from core.constants import DATA_SOURCE_LABELS, EXPORT_FORMATS, MODE_LABELS


class _WheelBlocker(QObject):
    """Event filter that swallows wheel events so lists/scroll areas do not scroll."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            return True  # consumed; no scroll
        return False


def build_report_builder_ui(widget):
    """Build the full Report Builder UI on the given widget (a ReportBuilderWidget)."""
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    menu_bar = QMenuBar()
    menu_bar.setNativeMenuBar(False)
    menu_bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
    file_menu = menu_bar.addMenu("File")
    file_menu.addAction("New Report", widget.create_report)
    file_menu.addAction("Duplicate Report", widget.duplicate_report)
    file_menu.addAction("Delete Report", widget.delete_report)
    file_menu.addSeparator()
    file_menu.addAction("Manage Reports...", widget.open_report_manager)
    file_menu.addSeparator()
    file_menu.addAction("Save Report", widget.save_report)
    file_menu.addAction("Save Report As...", widget.save_report_as)
    file_menu.addAction("Export Report", widget.export_report)
    file_menu.addSeparator()
    file_menu.addAction("Clear Current", widget.clear_current_report)
    layout.setMenuBar(menu_bar)

    top_bar = QWidget()
    top_bar_layout = QHBoxLayout(top_bar)
    top_bar_layout.setContentsMargins(2, 0, 2, 0)
    top_bar_layout.setSpacing(8)
    top_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    top_bar.setMinimumHeight(26)
    top_bar.setMaximumHeight(26)

    widget.current_report_label = QLabel("No report selected")
    widget.current_report_label.setWordWrap(True)
    title_font = widget.current_report_label.font()
    title_font.setPointSize(title_font.pointSize() + 1)
    title_font.setBold(True)
    widget.current_report_label.setFont(title_font)
    top_bar_layout.addStretch()
    top_bar_layout.addWidget(widget.current_report_label, alignment=Qt.AlignCenter)
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
    widget._scroll_wheel_blocker = _WheelBlocker(scroll_area)
    scroll_area.installEventFilter(widget._scroll_wheel_blocker)
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
    widget.name_edit = QLineEdit()
    widget.name_edit.setPlaceholderText("e.g. Weekly Inventory")
    widget.name_edit.textChanged.connect(widget._schedule_preview)
    widget.mode_combo = QComboBox()
    widget.mode_combo.addItems(MODE_LABELS)
    widget.mode_combo.currentTextChanged.connect(widget._on_mode_changed)
    widget.mode_combo.currentTextChanged.connect(widget._schedule_preview)
    details_layout.addRow("Name:", widget.name_edit)
    details_layout.addRow("Mode:", widget.mode_combo)
    form_layout.addWidget(details_group)

    source_group = QGroupBox("Data Source")
    source_layout = QFormLayout(source_group)
    widget.source_combo = QComboBox()
    widget.source_combo.addItems(DATA_SOURCE_LABELS)
    widget.source_combo.currentTextChanged.connect(widget._on_source_changed)
    widget.source_combo.currentTextChanged.connect(widget._schedule_preview)

    widget.group_combo = QComboBox()
    widget.group_combo.currentTextChanged.connect(widget._schedule_preview)
    widget.subnet_edit = QLineEdit()
    widget.subnet_edit.setPlaceholderText("e.g. 192.168.1.0/24")
    widget.subnet_edit.textChanged.connect(widget._schedule_preview)
    widget.tag_edit = QLineEdit()
    widget.tag_edit.setPlaceholderText("e.g. core")
    widget.tag_edit.textChanged.connect(widget._schedule_preview)

    source_layout.addRow("Source:", widget.source_combo)
    source_layout.addRow("Group:", widget.group_combo)
    source_layout.addRow("Subnet:", widget.subnet_edit)
    source_layout.addRow("Tag:", widget.tag_edit)
    source_help = QLabel("Tip: Use Selected Devices from the table for quick reports.")
    source_help.setWordWrap(True)
    source_layout.addRow("", source_help)
    form_layout.addWidget(source_group)

    widget.table_controls_group = QFrame()
    widget.table_controls_group.setFrameShape(QFrame.NoFrame)
    wizard_layout = QVBoxLayout(widget.table_controls_group)
    wizard_layout.setContentsMargins(0, 0, 0, 0)

    widget.wizard_tabs = QTabWidget()
    widget.wizard_tabs.setDocumentMode(True)

    # ---- Tab 1: Columns ----
    columns_tab = QWidget()
    col_layout = QVBoxLayout(columns_tab)
    col_splitter = QSplitter(Qt.Horizontal)
    col_splitter.setChildrenCollapsible(False)

    available_panel = QGroupBox("Available Fields")
    av_layout = QVBoxLayout(available_panel)
    widget.column_search_edit = QLineEdit()
    widget.column_search_edit.setPlaceholderText("Search fields...")
    widget.column_search_edit.textChanged.connect(widget._filter_available_columns)
    av_layout.addWidget(widget.column_search_edit)
    widget.available_columns_list = QListWidget()
    widget.available_columns_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
    widget.available_columns_list.itemDoubleClicked.connect(widget._add_available_column_to_selected)
    widget.available_columns_list.installEventFilter(widget._scroll_wheel_blocker)
    av_layout.addWidget(widget.available_columns_list)
    add_one_btn = QPushButton("Add →")
    add_one_btn.clicked.connect(widget._add_selected_available_to_columns)
    add_all_btn = QPushButton("Add All")
    add_all_btn.clicked.connect(widget._add_all_available_columns)
    av_layout.addWidget(add_one_btn)
    av_layout.addWidget(add_all_btn)
    col_splitter.addWidget(available_panel)

    selected_panel = QGroupBox("Selected Columns")
    sel_layout = QVBoxLayout(selected_panel)
    widget.columns_list = QListWidget()
    widget.columns_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
    widget.columns_list.setDragDropMode(QAbstractItemView.InternalMove)
    widget.columns_list.setDefaultDropAction(Qt.MoveAction)
    widget.columns_list.installEventFilter(widget._scroll_wheel_blocker)
    if widget.columns_list.model():
        widget.columns_list.model().rowsMoved.connect(widget._on_columns_reordered)
    widget.columns_list.itemSelectionChanged.connect(widget._on_selected_column_changed)
    sel_layout.addWidget(widget.columns_list)
    col_options_row = QHBoxLayout()
    widget.column_visible_check = QCheckBox("Visible")
    widget.column_visible_check.setChecked(True)
    widget.column_visible_check.toggled.connect(widget._apply_column_options_to_selection)
    widget.column_header_edit = QLineEdit()
    widget.column_header_edit.setPlaceholderText("Custom header (optional)")
    widget.column_header_edit.textChanged.connect(widget._apply_column_options_to_selection)
    col_options_row.addWidget(widget.column_visible_check)
    col_options_row.addWidget(QLabel("Header:"))
    col_options_row.addWidget(widget.column_header_edit, 1)
    sel_layout.addLayout(col_options_row)
    col_hint = QLabel("Applied to first selected column.")
    col_hint.setStyleSheet("color: var(--text-muted, #666); font-size: 0.9em;")
    col_hint.setWordWrap(True)
    sel_layout.addWidget(col_hint)
    sel_buttons = QHBoxLayout()
    widget.remove_column_button = QPushButton("Remove Selected")
    remove_all_btn = QPushButton("Remove All")
    sel_buttons.addWidget(widget.remove_column_button)
    sel_buttons.addWidget(remove_all_btn)
    sel_layout.addLayout(sel_buttons)
    widget.remove_column_button.clicked.connect(widget.remove_selected_columns)
    remove_all_btn.clicked.connect(widget._remove_all_columns)
    widget.add_column_button = QPushButton("Add Column…")
    widget.add_column_button.clicked.connect(widget.show_add_column_menu)
    sel_layout.addWidget(widget.add_column_button)
    col_splitter.addWidget(selected_panel)
    col_splitter.setStretchFactor(0, 1)
    col_splitter.setStretchFactor(1, 1)
    col_layout.addWidget(col_splitter)
    widget.wizard_tabs.addTab(columns_tab, "Columns")

    # ---- Tab 2: Filters ----
    filters_tab = QWidget()
    ft_layout = QVBoxLayout(filters_tab)
    filters_group = QGroupBox("Filters")
    filters_layout = QVBoxLayout(filters_group)
    filter_logic_row = QHBoxLayout()
    filter_logic_row.addWidget(QLabel("Combine with:"))
    widget.filter_logic_combo = QComboBox()
    widget.filter_logic_combo.addItems(["AND", "OR"])
    widget.filter_logic_combo.currentTextChanged.connect(widget._schedule_preview)
    filter_logic_row.addWidget(widget.filter_logic_combo)
    filter_logic_row.addStretch()
    filters_layout.addLayout(filter_logic_row)
    filters_help = QLabel("Each row: [Field] [Operator] [Value]. Property names: alias, ip_address, status, tags, etc.")
    filters_help.setWordWrap(True)
    filters_layout.addWidget(filters_help)
    widget.filters_table = QTableWidget(0, 3)
    widget.filters_table.setHorizontalHeaderLabels(["Property", "Operator", "Value"])
    widget.filters_table.horizontalHeader().setStretchLastSection(True)
    widget.filters_table.installEventFilter(widget._scroll_wheel_blocker)
    if widget.filters_table.viewport():
        widget.filters_table.viewport().installEventFilter(widget._scroll_wheel_blocker)
    widget.filters_table.itemChanged.connect(widget._schedule_preview)
    filters_layout.addWidget(widget.filters_table)
    filter_buttons = QHBoxLayout()
    widget.add_filter_button = QPushButton("+ Add Filter")
    widget.remove_filter_button = QPushButton("Remove Selected")
    filter_buttons.addWidget(widget.add_filter_button)
    filter_buttons.addWidget(widget.remove_filter_button)
    filters_layout.addLayout(filter_buttons)
    widget.add_filter_button.clicked.connect(widget.add_filter_row)
    widget.remove_filter_button.clicked.connect(widget.remove_selected_rows)
    ft_layout.addWidget(filters_group)
    widget.wizard_tabs.addTab(filters_tab, "Filters")

    # ---- Tab 3: Sorting ----
    sort_tab = QWidget()
    st_layout = QVBoxLayout(sort_tab)
    widget.sort_group = QGroupBox("Sort Rules")
    sort_layout = QVBoxLayout(widget.sort_group)
    sort_help = QLabel("Order: 1, 2, 3… Drag or use Move Up/Down to change priority.")
    sort_help.setWordWrap(True)
    sort_layout.addWidget(sort_help)
    widget.sorts_table = QTableWidget(0, 3)
    widget.sorts_table.setHorizontalHeaderLabels(["#", "Column", "Direction"])
    widget.sorts_table.horizontalHeader().setStretchLastSection(True)
    widget.sorts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
    widget.sorts_table.setSelectionMode(QAbstractItemView.SingleSelection)
    widget.sorts_table.installEventFilter(widget._scroll_wheel_blocker)
    if widget.sorts_table.viewport():
        widget.sorts_table.viewport().installEventFilter(widget._scroll_wheel_blocker)
    sort_layout.addWidget(widget.sorts_table)
    sort_buttons = QHBoxLayout()
    widget.add_sort_button = QPushButton("+ Add Sort Level")
    widget.remove_sort_button = QPushButton("Remove Selected")
    widget.sort_up_button = QPushButton("Move Up")
    widget.sort_down_button = QPushButton("Move Down")
    sort_buttons.addWidget(widget.add_sort_button)
    sort_buttons.addWidget(widget.remove_sort_button)
    sort_buttons.addWidget(widget.sort_up_button)
    sort_buttons.addWidget(widget.sort_down_button)
    sort_layout.addLayout(sort_buttons)
    widget.add_sort_button.clicked.connect(widget.add_sort_row)
    widget.remove_sort_button.clicked.connect(widget.remove_selected_sorts)
    widget.sort_up_button.clicked.connect(lambda: widget._move_sort_rows(-1))
    widget.sort_down_button.clicked.connect(lambda: widget._move_sort_rows(1))
    st_layout.addWidget(widget.sort_group)
    widget.wizard_tabs.addTab(sort_tab, "Sorting")

    wizard_layout.addWidget(widget.wizard_tabs)
    form_layout.addWidget(widget.table_controls_group)

    widget.template_group = QGroupBox("Template Settings")
    template_layout = QVBoxLayout(widget.template_group)
    widget.template_header_edit = QTextEdit()
    widget.template_item_edit = QTextEdit()
    widget.template_footer_edit = QTextEdit()
    for te in (widget.template_header_edit, widget.template_item_edit, widget.template_footer_edit):
        te.installEventFilter(widget._scroll_wheel_blocker)
    widget.template_header_edit.setPlaceholderText("Optional header text")
    widget.template_item_edit.setPlaceholderText("e.g. {{alias}} ({{ip_address}})")
    widget.template_footer_edit.setPlaceholderText("Optional footer text")
    widget.template_header_edit.textChanged.connect(widget._schedule_preview)
    widget.template_item_edit.textChanged.connect(widget._schedule_preview)
    widget.template_footer_edit.textChanged.connect(widget._schedule_preview)
    tl_form = QFormLayout()
    tl_form.addRow("Header:", widget.template_header_edit)
    tl_form.addRow("Item:", widget.template_item_edit)
    tl_form.addRow("Footer:", widget.template_footer_edit)
    template_layout.addLayout(tl_form)
    props_help = QLabel("Available properties (use {{property_name}} in templates):")
    props_help.setWordWrap(True)
    template_layout.addWidget(props_help)
    widget.template_properties_label = QLabel()
    widget.template_properties_label.setWordWrap(True)
    widget.template_properties_label.setStyleSheet("color: var(--text-muted, #666); font-size: 0.95em;")
    template_layout.addWidget(widget.template_properties_label)
    form_layout.addWidget(widget.template_group)

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
    widget.format_combo = QComboBox()
    widget.format_combo.addItems(EXPORT_FORMATS)
    widget.format_combo.currentTextChanged.connect(widget._schedule_preview)
    widget.filename_template_edit = QLineEdit()
    widget.filename_template_edit.setPlaceholderText("{name}_{date}_{time}")
    widget.filename_template_edit.setText("{name}_{date}_{time}")
    widget.path_edit = QLineEdit()
    widget.path_edit.setPlaceholderText("Choose where to save the exported report")
    widget.browse_button = QPushButton("Browse")
    path_row = QHBoxLayout()
    path_row.addWidget(widget.path_edit)
    path_row.addWidget(widget.browse_button)
    output_layout.addRow("Format:", widget.format_combo)
    output_layout.addRow("Filename Template:", widget.filename_template_edit)
    output_layout.addRow("File:", path_row)
    output_help = QLabel("Filename variables: {name}, {date}, {time}. Preview shows export content.")
    output_help.setWordWrap(True)
    output_layout.addRow("", output_help)
    widget.browse_button.clicked.connect(widget.browse_output_path)

    output_actions = QHBoxLayout()
    widget.save_button = QPushButton("Save Report")
    widget.preview_button = QPushButton("Generate Preview")
    widget.export_button = QPushButton("Export Report")
    output_actions.addWidget(widget.save_button)
    output_actions.addWidget(widget.preview_button)
    output_actions.addWidget(widget.export_button)
    output_layout.addRow("", output_actions)
    preview_layout.addWidget(output_group)

    preview_group = QGroupBox("Preview")
    preview_group_layout = QVBoxLayout(preview_group)
    widget.preview_text = QTextEdit()
    widget.preview_text.setReadOnly(True)
    widget.preview_text.setLineWrapMode(QTextEdit.NoWrap)
    widget.preview_text.installEventFilter(widget._scroll_wheel_blocker)
    preview_group_layout.addWidget(widget.preview_text)
    preview_layout.addWidget(preview_group)

    widget.save_button.clicked.connect(widget.save_report)
    widget.preview_button.clicked.connect(widget.generate_preview)
    widget.export_button.clicked.connect(widget.export_report)

    splitter.addWidget(form_panel)
    splitter.addWidget(preview_panel)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([740, 520])

    widget._on_mode_changed(widget.mode_combo.currentText())
    widget._on_source_changed(widget.source_combo.currentText())
