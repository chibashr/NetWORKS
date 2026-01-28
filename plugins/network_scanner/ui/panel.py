#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Scan panel layout for the Network Scanner plugin.
Builds the dock panel (Quick Scan controls, progress, Results).
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QSplitter,
    QProgressBar,
    QTextEdit,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer

from src.ui.plugin_widgets import CollapsibleSection
from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES


def build_scan_panel(plugin):
    """Build the scan dock panel. Sets plugin.main_widget and widget refs (interface_combo, etc.)."""
    plugin.main_widget = QWidget()
    mark_plugin_ui(plugin.main_widget)
    plugin.main_layout = QVBoxLayout(plugin.main_widget)
    grid = PLUGIN_UI_SIZES["grid"]
    pad = PLUGIN_UI_SIZES["section_padding"]
    plugin.main_layout.setContentsMargins(pad, pad, pad, pad)
    plugin.main_layout.setSpacing(grid)

    top_section = QWidget()
    top_layout = QVBoxLayout(top_section)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(grid)

    quick_scan_section = CollapsibleSection("Quick Scan", expanded=True)
    plugin.control_group = quick_scan_section.content_frame
    control_layout = quick_scan_section.content_layout

    interface_layout = QHBoxLayout()
    interface_layout.setSpacing(grid)
    interface_layout.addWidget(QLabel("Interface:"))
    plugin.interface_combo = QComboBox()
    plugin.interface_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    if not plugin.settings["preferred_interface"]["choices"]:
        plugin._update_interface_choices()
    plugin.interface_combo.addItems(plugin.settings["preferred_interface"]["choices"])
    current_interface = plugin.settings["preferred_interface"]["value"]
    if current_interface and current_interface in plugin.settings["preferred_interface"]["choices"]:
        plugin.interface_combo.setCurrentText(current_interface)
    plugin.refresh_interfaces_button = QPushButton("Refresh")
    plugin.refresh_interfaces_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    plugin.refresh_interfaces_button.setToolTip("Refresh network interface list")
    plugin.refresh_interfaces_button.clicked.connect(plugin._update_interface_choices_and_refresh_ui)
    interface_layout.addWidget(plugin.interface_combo, 1)
    interface_layout.addWidget(plugin.refresh_interfaces_button)
    control_layout.addLayout(interface_layout)

    target_layout = QHBoxLayout()
    target_layout.setSpacing(8)
    target_layout.addWidget(QLabel("Target:"))
    plugin.target_combo = QComboBox()
    plugin.target_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    plugin.target_combo.addItem("Interface Subnet", "interface")
    plugin.target_combo.addItem("Custom Range", "custom")
    plugin.target_combo.addItem("Selected Devices", "devices")
    plugin.target_combo.addItem("Group", "group")
    target_layout.addWidget(plugin.target_combo, 1)
    control_layout.addLayout(target_layout)

    plugin.selected_devices_label = QLabel("No devices selected")
    plugin.selected_devices_label.setProperty("plugin_ui_muted", "true")
    plugin.selected_devices_label.setVisible(False)
    control_layout.addWidget(plugin.selected_devices_label)

    group_row = QHBoxLayout()
    group_row.setSpacing(grid)
    group_row.addWidget(QLabel("Group:"))
    plugin.group_combo = QComboBox()
    plugin.group_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    plugin.group_combo.setToolTip("Select a group to scan")
    group_row.addWidget(plugin.group_combo, 1)
    plugin.panel_group_container = QWidget()
    plugin.panel_group_container.setLayout(group_row)
    plugin.panel_group_container.setVisible(False)
    control_layout.addWidget(plugin.panel_group_container)

    range_layout = QHBoxLayout()
    range_layout.setSpacing(8)
    range_layout.addWidget(QLabel("Range:"))
    plugin.network_range_edit = QLineEdit()
    plugin.network_range_edit.setPlaceholderText("e.g., 192.168.1.0/24 or 10.0.0.1-10.0.0.254")
    plugin.network_range_edit.setEnabled(False)
    range_layout.addWidget(plugin.network_range_edit, 1)
    control_layout.addLayout(range_layout)

    def update_target_ui_state():
        target = plugin.target_combo.currentData() if plugin.target_combo.currentData() is not None else "interface"
        plugin.network_range_edit.setEnabled(target == "custom")
        plugin.selected_devices_label.setVisible(target == "devices")
        plugin.panel_group_container.setVisible(target == "group")
        if target == "group":
            plugin._refresh_group_choices()

    plugin.target_combo.currentIndexChanged.connect(update_target_ui_state)
    update_target_ui_state()
    QTimer.singleShot(100, plugin._update_selected_devices_ui)
    plugin.interface_combo.currentIndexChanged.connect(plugin._update_network_range_from_interface)
    plugin._update_network_range_from_interface(plugin.interface_combo.currentIndex())

    scan_type_layout = QHBoxLayout()
    scan_type_layout.setSpacing(grid)
    scan_type_layout.addWidget(QLabel("Scan Type:"))
    plugin.scan_type_combo = QComboBox()
    plugin.scan_type_combo.addItems(plugin.settings["scan_type"]["choices"])
    plugin.scan_type_combo.setCurrentText(plugin.settings["scan_type"]["value"])
    scan_type_layout.addWidget(plugin.scan_type_combo, 1)
    plugin.scan_type_manager_button = QPushButton("Manage")
    plugin.scan_type_manager_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    plugin.scan_type_manager_button.setToolTip("Manage scan profiles and types")
    plugin.scan_type_manager_button.clicked.connect(plugin.on_scan_type_manager_action)
    scan_type_layout.addWidget(plugin.scan_type_manager_button)
    control_layout.addLayout(scan_type_layout)

    button_grid = QGridLayout()
    button_grid.setSpacing(4)
    button_grid.setHorizontalSpacing(4)
    button_grid.setVerticalSpacing(4)
    plugin.scan_button = QPushButton("Start Scan")
    plugin.scan_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    plugin.scan_button.clicked.connect(plugin.on_scan_stop_button_clicked)
    plugin.scan_button.setToolTip("Start a scan, or stop the current scan")
    button_grid.addWidget(plugin.scan_button, 0, 0)
    plugin.advanced_scan_button = QPushButton("Advanced...")
    plugin.advanced_scan_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    plugin.advanced_scan_button.clicked.connect(plugin.on_advanced_scan_button_clicked)
    plugin.advanced_scan_button.setToolTip("Open the advanced scan configuration dialog")
    button_grid.addWidget(plugin.advanced_scan_button, 0, 1)
    control_layout.addLayout(button_grid)
    top_layout.addWidget(plugin.control_group)

    progress_widget = QWidget()
    plugin.progress_layout = QVBoxLayout(progress_widget)
    plugin.progress_layout.setContentsMargins(4, 4, 4, 4)
    plugin.progress_layout.setSpacing(4)
    plugin.status_label = QLabel("Ready")
    plugin.progress_layout.addWidget(plugin.status_label)
    plugin.progress_bar = QProgressBar()
    plugin.progress_bar.setRange(0, 100)
    plugin.progress_bar.setValue(0)
    plugin.progress_layout.addWidget(plugin.progress_bar)
    top_layout.addWidget(progress_widget)

    results_section = CollapsibleSection("Results", expanded=True)
    plugin.results_group = results_section.content_frame
    plugin.results_layout = results_section.content_layout
    plugin.results_text = QTextEdit()
    plugin.results_text.setReadOnly(True)
    plugin.results_text.setPlaceholderText("No scan results yet. Click Start Scan to begin.")
    plugin.results_layout.addWidget(plugin.results_text)
    mark_plugin_ui(plugin.results_text)
    plugin.results_footer = QLabel("Ready | 0 devices")
    plugin.results_footer.setProperty("plugin_ui_muted", "true")
    plugin.results_layout.addWidget(plugin.results_footer)

    plugin.main_splitter = QSplitter(Qt.Vertical)
    plugin.main_splitter.addWidget(top_section)
    plugin.main_splitter.addWidget(results_section)
    plugin.main_splitter.setStretchFactor(0, 0)
    plugin.main_splitter.setStretchFactor(1, 1)
    plugin.main_splitter.setSizes([200, 400])
    plugin.main_layout.addWidget(plugin.main_splitter)

    mark_plugin_ui(plugin.main_widget)
    return plugin.main_widget
