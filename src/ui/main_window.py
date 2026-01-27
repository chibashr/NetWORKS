#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main window for NetWORKS
"""

import os
from loguru import logger
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QStatusBar, QMenuBar, QMenu,
    QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeView, QFrame, QLabel, QToolButton, QPushButton, QTableView,
    QHeaderView, QAbstractItemView, QSizePolicy, QInputDialog, QLineEdit, QMessageBox, QDialog, QListWidget, QTableWidget, QTableWidgetItem, QTextBrowser,
    QApplication, QFileDialog
)
from PySide6.QtGui import QIcon, QAction, QFont, QKeySequence, QBrush, QColor
from PySide6.QtCore import Qt, QSize, Signal, Slot, QModelIndex, QSettings, QTimer, QByteArray, QPoint
from PySide6.QtWidgets import QStyle
import html
import re

from .device_table import DeviceTableModel, DeviceTableView, QAbstractItemView
from .device_tree import DeviceTreeModel, DeviceTreeView, DeviceTreePanel
from .main_window_actions import create_actions
from .plugin_manager_dialog import PluginManagerDialog
from .plugin_ui_theme import mark_plugin_ui
from .log_panel import LogPanel
from .responsive_toolbar import ResponsiveToolbar
from .scalable_toolbar import ScalableToolbar
from .material_icons import material_icon


class MainWindow(QMainWindow):
    """Main window for NetWORKS"""
    
    def __init__(self, app):
        """Initialize the main window"""
        super().__init__()
        logger.debug("Initializing main window")
        
        self.app = app
        self.device_manager = app.device_manager
        self.plugin_manager = app.plugin_manager
        self.config = app.config
        
        # Track plugin loading for layout restoration
        self._pending_plugin_layout_restore = False
        self._layout_restore_timer = QTimer(self)
        self._layout_restore_timer.setSingleShot(True)
        self._layout_restore_timer.timeout.connect(self._restore_plugin_layout_after_load)
        
        # Debounced layout save timer (save 500ms after last change)
        self._layout_save_timer = QTimer(self)
        self._layout_save_timer.setSingleShot(True)
        self._layout_save_timer.timeout.connect(self._save_workspace_layout)
        
        # Set window properties
        self.updateWindowTitle()
        self.resize(1200, 800)
        
        # Initialize UI components
        create_actions(self)
        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()
        self._create_central_widget()
        self._create_dock_widgets()
        
        # Connect signals
        self._connect_signals()
        
        # Initialize autosave
        self._setup_autosave()
        
        # Restore window state, size and position if available
        self._restore_window_state()
        
        # Initialize update checker
        self._setup_update_checker()
        
        logger.info("Main window initialized")
        
    def updateWindowTitle(self):
        """Update the window title to include current workspace"""
        app_version = self.app.get_version()
        workspace = self.device_manager.current_workspace
        self.setWindowTitle(f"NetWORKS v{app_version} - Workspace: {workspace}")
        
    def refresh_workspace_ui(self):
        """Refresh all UI components after workspace change"""
        logger.debug(f"Refreshing UI for workspace: {self.device_manager.current_workspace}")
        
        # Update window title
        self.updateWindowTitle()
        
        # Update status bar
        self.status_workspace.setText(f"Workspace: {self.device_manager.current_workspace}")
        self.status_bar.showMessage(f"Loaded workspace: {self.device_manager.current_workspace}", 3000)
        
        # Refresh device table
        if hasattr(self, "device_table"):
            self.device_table.refresh()
            self.device_table.restore_workspace_state()
            
        # Refresh device panel
        if hasattr(self, "device_panel"):
            self.device_panel.refresh()
            
        # Refresh device tree
        if hasattr(self, "device_tree"):
            self.device_tree.refresh()
        if hasattr(self, "device_tree_panel"):
            self.device_tree_panel.restore_state()
            
        # Update device count in status bar
        self.update_status_bar()
        
        # Restore the UI layout for this workspace
        self._restore_window_state()
        
        # Check if there are any enabled plugins that might be loading
        # If plugins are already loaded or none are enabled, restore layout immediately
        enabled_plugins = [p for p in self.plugin_manager.plugins.values() 
                         if p.state.is_enabled and not p.state.is_loaded]
        
        if enabled_plugins:
            # Mark that we need to restore plugin layouts after plugins are loaded
            self._pending_plugin_layout_restore = True
            logger.debug(f"Waiting for {len(enabled_plugins)} plugins to load before restoring layout")
        else:
            # All plugins are already loaded or none enabled, restore layout now
            self._restore_plugin_layout_after_load()
        
        logger.debug("UI refresh complete")
        
    def _create_menus(self):
        """Create menu bar and menus"""
        self.menu_bar = self.menuBar()
        
        # File menu
        self.menu_file = self.menu_bar.addMenu("File")
        self.menu_file.addAction(self.action_new_device)
        self.menu_file.addAction(self.action_new_group)
        self.menu_file.addAction(self.action_import_devices)
        self.menu_file.addSeparator()
        
        # Workspace submenu (open/new handled by workspace manager)
        self.menu_workspaces = self.menu_file.addMenu("Workspaces")
        self.menu_workspaces.addAction(self.action_save_workspace)
        self.menu_workspaces.addAction(self.action_manage_workspaces)
        
        # Add recycle bin action to the file menu
        self.menu_file.addAction(self.action_recycle_bin)
        
        self.menu_file.addAction(self.action_save)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.action_exit)
        
        # Edit menu
        self.menu_edit = self.menu_bar.addMenu("Edit")
        self.menu_edit.addAction(self.action_select_all)
        self.menu_edit.addAction(self.action_deselect_all)
        self.menu_edit.addSeparator()
        self.menu_edit.addAction(self.action_delete)
        
        # View menu
        self.menu_view = self.menu_bar.addMenu("View")
        self.menu_view.addAction(self.action_refresh)
        
        # Tools menu
        self.menu_tools = self.menu_bar.addMenu("Tools")
        self.menu_tools.addAction(self.action_plugin_manager)
        self.menu_tools.addAction(self.action_settings)
        
        # Help menu
        self.menu_help = self.menu_bar.addMenu("Help")
        self.menu_help.addAction(self.action_documentation)
        self.menu_help.addAction(self.action_report_issue)
        self.menu_help.addAction(self.action_check_updates)
        self.menu_help.addAction(self.action_about)
        
        # Plugin menus (will be populated by plugins)
        self.plugin_menus = {}
        
    def _create_toolbar(self):
        """Create toolbar"""
        self.toolbar = ScalableToolbar("Main Toolbar")
        self.toolbar.setObjectName("MainToolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        
        self.addToolBar(self.toolbar)

        self.addToolBarBreak(Qt.TopToolBarArea)
        self.plugin_toolbar = ScalableToolbar("Plugin Toolbar")
        self.plugin_toolbar.setObjectName("PluginToolbar")
        self.plugin_toolbar.setMovable(False)
        self.plugin_toolbar.setIconSize(QSize(24, 24))
        self.plugin_toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.plugin_toolbar.setVisible(False)

        self.addToolBar(Qt.TopToolBarArea, self.plugin_toolbar)
        
        # Add actions to toolbar
        self.toolbar.add_toolbar_action(self.action_new_device, priority=100)
        self.toolbar.add_toolbar_action(self.action_new_group, priority=95)
        self.toolbar.add_toolbar_action(self.action_import_devices, priority=90)
        self.toolbar.add_toolbar_separator()
        self.toolbar.add_toolbar_action(self.action_save, priority=85)
        self.toolbar.add_toolbar_separator()
        self.toolbar.add_toolbar_action(self.action_refresh, priority=80)
        
    def _create_statusbar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Workspace indicator
        self.status_workspace = QLabel(f"Workspace: {self.device_manager.current_workspace}")
        self.status_bar.addWidget(self.status_workspace)
        
        # Spacer
        spacer_label = QLabel()
        spacer_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.status_bar.addWidget(spacer_label)
        
        self.status_device_count = QLabel("0 devices")
        self.status_bar.addPermanentWidget(self.status_device_count)
        
        self.status_selection = QLabel("0 selected")
        self.status_bar.addPermanentWidget(self.status_selection)
        
        self.status_bar.showMessage("Ready")
        
    def _create_central_widget(self):
        """Create central widget with device table"""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Create device table (without splitter now)
        self.device_table = DeviceTableView(self.device_manager)
        self.main_layout.addWidget(self.device_table.get_container_widget())
        if self.device_table.selectionModel():
            self.device_table.selectionModel().selectionChanged.connect(
                self._on_table_highlight_changed
            )
        
    def _create_dock_widgets(self):
        """Create dock widgets"""
        # Device tree dock widget (left panel)
        self.dock_device_tree = QDockWidget("Devices", self)
        self.dock_device_tree.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Create device tree panel
        self.device_tree_panel = DeviceTreePanel(self.device_manager)
        self.device_tree = self.device_tree_panel.view
        self.device_tree_model = self.device_tree_panel.model
        
        self.dock_device_tree.setWidget(self.device_tree_panel)
        self.dock_device_tree.setObjectName("DeviceTreeDock")
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_device_tree)
        # Connect signals to save layout when dock widget changes
        self.dock_device_tree.topLevelChanged.connect(self._on_dock_widget_changed)
        self.dock_device_tree.dockLocationChanged.connect(self._on_dock_widget_changed)
        
        # Properties dock widget (right panel)
        self.dock_properties = QDockWidget("Properties", self)
        self.dock_properties.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_properties.setObjectName("PropertiesDock")
        
        # Create properties panel
        self.properties_widget = QTabWidget()
        
        # Details tab
        self.details_tab = QWidget()
        self.details_layout = QVBoxLayout(self.details_tab)
        self.details_layout.setContentsMargins(4, 4, 4, 4)
        
        # Create a table for properties instead of a form layout
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QMenu
        
        # Property table
        self.properties_table = QTableWidget()
        self.properties_table.setColumnCount(2)
        self.properties_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.properties_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.properties_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.properties_table.setColumnWidth(0, 180)
        self.properties_table.setAlternatingRowColors(True)
        self.properties_table.verticalHeader().setVisible(False)
        self.properties_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.properties_table.setWordWrap(False)
        self.properties_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.properties_table.customContextMenuRequested.connect(self._show_property_context_menu)
        # Add double click handler
        self.properties_table.cellDoubleClicked.connect(self._handle_property_double_click)
        
        # Use global theme styling for properties table
        
        # Toolbar for property actions
        toolbar_container = ResponsiveToolbar()
        toolbar_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        export_btn = QPushButton("Export")
        export_btn.setToolTip("Export properties to clipboard or file")
        export_btn.clicked.connect(self._export_properties)
        export_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        filter_edit = QLineEdit()
        filter_edit.setPlaceholderText("Filter properties...")
        filter_edit.textChanged.connect(self._filter_properties)
        filter_edit.setClearButtonEnabled(True)
        filter_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        toolbar_container.addWidget(filter_edit, 1)
        toolbar_container.addWidget(export_btn)
        
        self.details_layout.addWidget(toolbar_container)
        self.details_layout.addWidget(self.properties_table)
        
        self.properties_widget.addTab(self.details_tab, "Details")
        
        # Additional tabs will be added by plugins
        
        self.dock_properties.setWidget(self.properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_properties)
        # Connect signals to save layout when dock widget changes
        self.dock_properties.topLevelChanged.connect(self._on_dock_widget_changed)
        self.dock_properties.dockLocationChanged.connect(self._on_dock_widget_changed)
        
        # Log dock widget (bottom panel)
        self.dock_log = QDockWidget("Log", self)
        self.dock_log.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.dock_log.setObjectName("LogDock")
        
        # Use LogPanel in the dock widget
        self.log_panel = LogPanel()
        self.dock_log.setWidget(self.log_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_log)
        # Connect signals to save layout when dock widget changes
        self.dock_log.topLevelChanged.connect(self._on_dock_widget_changed)
        self.dock_log.dockLocationChanged.connect(self._on_dock_widget_changed)
        
    def _connect_signals(self):
        """Connect signals from device manager and plugin manager"""
        # Device manager signals
        self.device_manager.device_added.connect(self.on_device_added)
        self.device_manager.device_removed.connect(self.on_device_removed)
        self.device_manager.device_changed.connect(self.on_device_changed)
        self.device_manager.group_added.connect(self.on_group_added)
        self.device_manager.group_removed.connect(self.on_group_removed)
        self.device_manager.selection_changed.connect(self.on_selection_changed)
        
        if hasattr(self, "device_tree"):
            self.device_tree.group_selection_changed.connect(self.on_group_selection_changed)
            self.device_tree.group_filter_requested.connect(self.on_group_filter_requested)
        
        # Plugin manager signals
        self.plugin_manager.plugin_loaded.connect(self.on_plugin_loaded)
        self.plugin_manager.plugin_unloaded.connect(self.on_plugin_unloaded)
        
    def update_status_bar(self):
        """Update status bar with current counts"""
        device_count = len(self.device_manager.get_devices())
        self.status_device_count.setText(f"{device_count} device{'s' if device_count != 1 else ''}")
        
        selection_count = len(self.device_manager.get_selected_devices())
        self.status_selection.setText(f"{selection_count} selected")
        
    def add_plugin_ui_components(self, plugin_info):
        """Add UI components from a plugin"""
        if not plugin_info.instance:
            return
            
        plugin = plugin_info.instance
        
        # Add toolbar actions
        toolbar_actions = plugin.get_toolbar_actions()
        if toolbar_actions:
            if not hasattr(plugin_info, 'ui_components'):
                plugin_info.ui_components = {}
            if 'toolbar_actions' not in plugin_info.ui_components:
                plugin_info.ui_components['toolbar_actions'] = []
            existing_actions = [
                action for action in self.plugin_toolbar.actions()
                if action is not self.plugin_toolbar._overflow_action
            ]
            if existing_actions:
                separator = self.plugin_toolbar.add_toolbar_separator()
                plugin_info.ui_components['toolbar_actions'].append(separator)
            for action in toolbar_actions:
                if action.property("toolbar_priority") is None:
                    action.setProperty("toolbar_priority", 10)
                self.plugin_toolbar.add_toolbar_action(action)
                plugin_info.ui_components['toolbar_actions'].append(action)
            self.plugin_toolbar.setVisible(True)
                
        # Add menu actions
        menu_actions = plugin.get_menu_actions()
        for menu_name, actions in menu_actions.items():
            # Check if it's an existing menu or a new plugin menu
            existing_menu = self.findMenu(menu_name)
            if existing_menu:
                # Add actions to existing menu
                for action in actions:
                    existing_menu.addAction(action)
                    # Store the menu and action for later removal
                    if not hasattr(plugin_info, 'ui_components'):
                        plugin_info.ui_components = {}
                    if 'menu_actions' not in plugin_info.ui_components:
                        plugin_info.ui_components['menu_actions'] = []
                    plugin_info.ui_components['menu_actions'].append((menu_name, action))
            else:
                # Create a new plugin menu if it doesn't exist
                if menu_name not in self.plugin_menus:
                    self.plugin_menus[menu_name] = self.menu_bar.addMenu(menu_name)
                    
                # Add actions to the plugin menu
                for action in actions:
                    self.plugin_menus[menu_name].addAction(action)
                    # Store the menu and action for later removal
                    if not hasattr(plugin_info, 'ui_components'):
                        plugin_info.ui_components = {}
                    if 'plugin_menu_actions' not in plugin_info.ui_components:
                        plugin_info.ui_components['plugin_menu_actions'] = []
                    plugin_info.ui_components['plugin_menu_actions'].append((menu_name, action))
                
        # Add device panels to properties widget
        device_panels = plugin.get_device_panels()
        for panel_name, widget in device_panels:
            mark_plugin_ui(widget)
            self.properties_widget.addTab(widget, panel_name)
            # Store for later removal
            if not hasattr(plugin_info, 'ui_components'):
                plugin_info.ui_components = {}
            if 'device_panels' not in plugin_info.ui_components:
                plugin_info.ui_components['device_panels'] = []
            plugin_info.ui_components['device_panels'].append((panel_name, widget))
            
        # Add dock widgets
        dock_widgets = plugin.get_dock_widgets()
        for widget_name, widget, area in dock_widgets:
            # If widget is already a QDockWidget, use it directly
            if isinstance(widget, QDockWidget):
                dock = widget
            else:
                dock = QDockWidget(widget_name, self)
                dock.setWidget(widget)

            plugin_title = getattr(plugin_info, "name", None) or getattr(plugin_info, "id", "")
            current_title = dock.windowTitle() or widget_name
            if plugin_title and plugin_title.lower() not in current_title.lower():
                dock.setWindowTitle(f"{plugin_title} - {current_title}")

            mark_plugin_ui(dock)
            if dock.widget():
                mark_plugin_ui(dock.widget())
            
            # Set unique object name for proper layout restoration
            if not dock.objectName():
                dock.setObjectName(f"{plugin_info.id}_{widget_name.replace(' ', '_')}_Dock")
            
            self.addDockWidget(area, dock)
            
            # Connect signals to save layout when dock widget changes
            dock.topLevelChanged.connect(self._on_dock_widget_changed)
            dock.dockLocationChanged.connect(self._on_dock_widget_changed)
            
            # Store for later removal
            if not hasattr(plugin_info, 'ui_components'):
                plugin_info.ui_components = {}
            if 'dock_widgets' not in plugin_info.ui_components:
                plugin_info.ui_components['dock_widgets'] = []
            plugin_info.ui_components['dock_widgets'].append((widget_name, dock))
            
    def remove_plugin_ui_components(self, plugin_info):
        """Remove UI components from a plugin"""
        logger.debug(f"Removing UI components for plugin: {plugin_info}")
        
        if not hasattr(plugin_info, 'ui_components'):
            logger.debug(f"No UI components to remove for plugin: {plugin_info}")
            return
            
        # Remove menu actions from existing menus
        if 'menu_actions' in plugin_info.ui_components:
            for menu_name, action in plugin_info.ui_components['menu_actions']:
                menu = self.findMenu(menu_name)
                if menu and action in menu.actions():
                    menu.removeAction(action)
                    
        # Remove actions from plugin menus
        if 'plugin_menu_actions' in plugin_info.ui_components:
            for menu_name, action in plugin_info.ui_components['plugin_menu_actions']:
                if menu_name in self.plugin_menus:
                    menu = self.plugin_menus[menu_name]
                    menu.removeAction(action)
                    # Remove menu if it's empty
                    if len(menu.actions()) == 0:
                        self.menu_bar.removeAction(menu.menuAction())
                        del self.plugin_menus[menu_name]
        
        # Remove device panels
        if 'device_panels' in plugin_info.ui_components:
            for panel_name, widget in plugin_info.ui_components['device_panels']:
                index = self.properties_widget.indexOf(widget)
                if index >= 0:
                    self.properties_widget.removeTab(index)

        # Remove toolbar actions
        if 'toolbar_actions' in plugin_info.ui_components:
            for action in plugin_info.ui_components['toolbar_actions']:
                self.plugin_toolbar.removeAction(action)
            remaining_actions = [
                action for action in self.plugin_toolbar.actions()
                if action is not self.plugin_toolbar._overflow_action
            ]
            if not remaining_actions:
                self.plugin_toolbar.setVisible(False)
                    
        # Remove dock widgets
        if 'dock_widgets' in plugin_info.ui_components:
            for widget_name, dock in plugin_info.ui_components['dock_widgets']:
                self.removeDockWidget(dock)
                dock.deleteLater()
                
        # Clear the components
        plugin_info.ui_components = {}
        
    def update_property_panel(self, devices=None):
        """Update property panel with device info
        
        Args:
            devices: A list of selected devices or None if no selection
        """
        # Clear table
        self.properties_table.setRowCount(0)
                
        # Convert single device to list for consistent handling
        if devices and not isinstance(devices, list):
            devices = [devices]
                
        # Early return if no devices selected
        no_selection = not devices or len(devices) == 0
        if no_selection:
            # Show placeholder text
            self.properties_table.setRowCount(1)
            item = QTableWidgetItem("No devices selected")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(Qt.AlignCenter)
            self.properties_table.setSpan(0, 0, 1, 2)
            self.properties_table.setItem(0, 0, item)
            logger.debug("No devices selected, cleared property panel")
            return
            
        # Store all properties for filtering
        self.current_properties = {}
            
        if len(devices) == 1:
            # Single device selection - show all properties
            device = devices[0]
            logger.debug(f"Showing properties for single device: {device.get_property('alias', 'Unnamed')}")
            
            # Get all properties
            device_props = device.get_properties()
            
            # Get loaded plugin IDs for property categorization
            plugin_ids = []
            if hasattr(self.app, 'plugin_manager'):
                for plugin_info in self.app.plugin_manager.get_plugins():
                    if plugin_info.state and plugin_info.state.is_loaded and plugin_info.id:
                        plugin_ids.append(plugin_info.id)
            
            # Add core properties first (in a specific order)
            core_props = ["id", "alias", "hostname", "ip_address", "mac_address", "status", "notes", "tags"]
            for prop in core_props:
                if prop in device_props:
                    value = device_props[prop]
                    formatted_value = self._format_property_value(value)
                    self._add_property_row(prop, value, formatted_value)
            
            # Separate remaining properties into plugin and custom
            plugin_props = {}
            custom_props = {}
            
            # Identify plugin properties using common separators (plugin_id:prop, plugin_id.prop, plugin_id_prop)
            for key in sorted([k for k in device_props.keys() if k not in core_props]):
                is_plugin_prop = False
                for plugin_id in plugin_ids:
                    # Check common separator patterns
                    if (key.startswith(f"{plugin_id}:") or 
                        key.startswith(f"{plugin_id}.") or 
                        key.startswith(f"{plugin_id}_")):
                        plugin_props[key] = device_props[key]
                        is_plugin_prop = True
                        break
                
                # If not a plugin property, it's a custom property
                if not is_plugin_prop:
                    custom_props[key] = device_props[key]
            
            # Add plugin properties if any exist
            if plugin_props:
                self._add_separator_row("Plugin Properties")
                for key in sorted(plugin_props.keys()):
                    value = plugin_props[key]
                    formatted_value = self._format_property_value(value)
                    self._add_property_row(key, value, formatted_value)
            
            # Add custom properties
            if custom_props:
                self._add_separator_row("Custom Properties")
                for key in sorted(custom_props.keys()):
                    value = custom_props[key]
                    formatted_value = self._format_property_value(value)
                    self._add_property_row(key, value, formatted_value)
                
        else:
            # Multiple device selection - show common properties
            logger.debug(f"Showing properties for {len(devices)} devices")
            
            # Get device names for better logging
            device_names = [str(d.get_property('alias', f'Device {d.id}')) for d in devices]
            logger.debug(f"Multiple devices selected: {', '.join(device_names[:5])}" + 
                       (f" and {len(device_names) - 5} more" if len(device_names) > 5 else ""))
            
            # Collect all properties from all devices
            all_properties = {}
            core_props = ["id", "alias", "hostname", "ip_address", "mac_address", "status", "notes", "tags"]
            
            # First, gather all properties and their values
            for device in devices:
                for key, value in device.get_properties().items():
                    if key not in all_properties:
                        all_properties[key] = []
                    
                    all_properties[key].append(value)
            
            # Add a header row with device count
            self._add_separator_row(f"{len(devices)} Devices Selected")
            
            # Add core properties first
            for prop in core_props:
                if prop in all_properties:
                    values = all_properties[prop]
                    # Check if all values are the same
                    if len(set(str(v) for v in values)) == 1:
                        formatted_value = self._format_property_value(values[0])
                        self._add_property_row(prop, values[0], formatted_value)
                    else:
                        self._add_property_row(prop, values, "<Multiple values>")
            
            # Get loaded plugin IDs for property categorization
            plugin_ids = []
            if hasattr(self.app, 'plugin_manager'):
                for plugin_info in self.app.plugin_manager.get_plugins():
                    if plugin_info.state and plugin_info.state.is_loaded and plugin_info.id:
                        plugin_ids.append(plugin_info.id)
            
            # Separate remaining properties into plugin and custom
            plugin_props = {}
            custom_props = {}
            
            # Identify plugin properties
            for key in sorted([k for k in all_properties.keys() if k not in core_props]):
                is_plugin_prop = False
                for plugin_id in plugin_ids:
                    # Check common separator patterns
                    if (key.startswith(f"{plugin_id}:") or 
                        key.startswith(f"{plugin_id}.") or 
                        key.startswith(f"{plugin_id}_")):
                        plugin_props[key] = all_properties[key]
                        is_plugin_prop = True
                        break
                
                # If not a plugin property, it's a custom property
                if not is_plugin_prop:
                    custom_props[key] = all_properties[key]
            
            # Add plugin properties if any exist
            if plugin_props:
                self._add_separator_row("Plugin Properties")
                for key in sorted(plugin_props.keys()):
                    values = plugin_props[key]
                    if len(set(str(v) for v in values)) == 1:
                        formatted_value = self._format_property_value(values[0])
                        self._add_property_row(key, values[0], formatted_value)
                    else:
                        self._add_property_row(key, values, "<Multiple values>")
            
            # Add custom properties
            if custom_props:
                self._add_separator_row("Custom Properties")
                for key in sorted(custom_props.keys()):
                    values = custom_props[key]
                    if len(set(str(v) for v in values)) == 1:
                        formatted_value = self._format_property_value(values[0])
                        self._add_property_row(key, values[0], formatted_value)
                    else:
                        self._add_property_row(key, values, "<Multiple values>")
                    
        # Resize rows to contents
        self.properties_table.resizeRowsToContents()

    def update_group_panel(self, groups=None):
        """Update property panel with group info"""
        self.properties_table.setRowCount(0)
        
        if groups and not isinstance(groups, list):
            groups = [groups]
            
        if not groups:
            self.properties_table.setRowCount(1)
            item = QTableWidgetItem("No groups selected")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(Qt.AlignCenter)
            self.properties_table.setSpan(0, 0, 1, 2)
            self.properties_table.setItem(0, 0, item)
            return
            
        if len(groups) == 1:
            group = groups[0]
            self._add_separator_row(f"Group: {group.name}")
            self._add_property_row("Name", group.name, group.name)
            self._add_property_row("Description", group.description, group.description or "")
            self._add_property_row("Devices (Direct)", len(group.devices), str(len(group.devices)))
            all_devices = group.get_all_devices()
            unique_devices = {d.id for d in all_devices}
            self._add_property_row("Devices (Total)", len(unique_devices), str(len(unique_devices)))
            self._add_property_row("Subgroups", len(group.subgroups), str(len(group.subgroups)))
        else:
            unique_devices = set()
            subgroup_count = 0
            for group in groups:
                subgroup_count += len(group.subgroups)
                for device in group.get_all_devices():
                    unique_devices.add(device.id)
            
            self._add_separator_row(f"{len(groups)} Groups Selected")
            self._add_property_row("Groups", len(groups), str(len(groups)))
            self._add_property_row("Unique Devices", len(unique_devices), str(len(unique_devices)))
            self._add_property_row("Total Subgroups", subgroup_count, str(subgroup_count))
        
        self.properties_table.resizeRowsToContents()
    
    def _add_property_row(self, key, raw_value, formatted_value):
        """Add a property row to the table
        
        Args:
            key: Property name
            raw_value: The raw value (stored for context menu)
            formatted_value: The formatted display value
        """
        row = self.properties_table.rowCount()
        self.properties_table.insertRow(row)
        
        # Property name (with title case formatting)
        name_item = QTableWidgetItem(key.replace('_', ' ').title())
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_item.setToolTip(key)
        self.properties_table.setItem(row, 0, name_item)
        
        # Property value
        value_item = QTableWidgetItem(formatted_value)
        value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
        value_item.setData(Qt.UserRole, raw_value)  # Store raw value for context menu
        
        # Apply styling based on data type
        # If it's a URL, make it look like a link
        if isinstance(raw_value, str) and (raw_value.startswith('http://') or raw_value.startswith('https://')):
            value_item.setForeground(QBrush(QColor("blue")))
            font = value_item.font()
            font.setUnderline(True)
            value_item.setFont(font)
            value_item.setToolTip("Double-click to open in browser")
        # If it's a complex data type that can be expanded, style accordingly
        elif isinstance(raw_value, (dict, list)) or (isinstance(raw_value, str) and len(raw_value) > 100):
            if isinstance(raw_value, dict):
                value_item.setToolTip(f"Double-click to view dictionary details ({len(raw_value)} items)")
            elif isinstance(raw_value, list):
                value_item.setToolTip(f"Double-click to view list details ({len(raw_value)} items)")
            else:
                value_item.setToolTip("Double-click to view full text")
            
            # Use a slightly different style to indicate it's interactive
            value_item.setForeground(QBrush(QColor("#505050")))
            font = value_item.font()
            font.setBold(True)
            value_item.setFont(font)
            
            # Add a visual indicator for expandable items
            if isinstance(raw_value, dict):
                value_item.setText(f"📋 {formatted_value}")
            elif isinstance(raw_value, list):
                value_item.setText(f"📋 {formatted_value}")
            elif isinstance(raw_value, str) and len(raw_value) > 100:
                value_item.setText(f"📝 {formatted_value}")
        else:
            value_item.setToolTip(formatted_value)
            
        self.properties_table.setItem(row, 1, value_item)
        
        # Store for filtering
        self.current_properties[key] = {
            'raw': raw_value,
            'formatted': formatted_value,
            'row': row
        }
    
    def _add_separator_row(self, text):
        """Add a separator/header row to the table
        
        Args:
            text: Text to display in the separator
        """
        row = self.properties_table.rowCount()
        self.properties_table.insertRow(row)
        
        # Create a header-style item spanning both columns
        separator_item = QTableWidgetItem(text)
        separator_item.setFlags(separator_item.flags() & ~Qt.ItemIsEditable)
        separator_item.setBackground(QBrush(QColor("#F0F0F0")))
        font = separator_item.font()
        font.setBold(True)
        separator_item.setFont(font)
        
        self.properties_table.setSpan(row, 0, 1, 2)
        self.properties_table.setItem(row, 0, separator_item)
    
    def _filter_properties(self, filter_text):
        """Filter properties based on user input
        
        Args:
            filter_text: Text to filter by
        """
        filter_text = filter_text.lower()
        
        # Show/hide rows based on filter
        for key, prop_data in self.current_properties.items():
            row = prop_data['row']
            matches = (
                filter_text in key.lower() or
                filter_text in str(prop_data['formatted']).lower()
            )
            self.properties_table.setRowHidden(row, not matches)
    
    def _show_property_context_menu(self, position):
        """Show context menu for property table
        
        Args:
            position: Position where the menu should be shown
        """
        menu = QMenu()
        
        copy_action = menu.addAction("Copy Value")
        copy_name_action = menu.addAction("Copy Property Name")
        copy_both_action = menu.addAction("Copy Name and Value")
        menu.addSeparator()
        copy_all_action = menu.addAction("Copy All Properties")
        
        # Get selected items
        selected_indexes = self.properties_table.selectedIndexes()
        if not selected_indexes:
            return
            
        # If a URL is selected, add open link action
        for index in selected_indexes:
            if index.column() == 1:  # Value column
                item = self.properties_table.item(index.row(), index.column())
                raw_value = item.data(Qt.UserRole)
                if isinstance(raw_value, str) and (raw_value.startswith('http://') or raw_value.startswith('https://')):
                    menu.addSeparator()
                    open_url_action = menu.addAction("Open URL")
                    break
                    
        # If complex data is selected, add view details action
        for index in selected_indexes:
            if index.column() == 1:  # Value column
                item = self.properties_table.item(index.row(), index.column())
                raw_value = item.data(Qt.UserRole)
                if isinstance(raw_value, (dict, list)) or (isinstance(raw_value, str) and len(raw_value) > 100):
                    menu.addSeparator()
                    view_details_action = menu.addAction("View Details")
                    break
        
        # Show the menu and get the selected action
        action = menu.exec_(self.properties_table.mapToGlobal(position))
        
        if not action:
            return
            
        # Handle actions
        if action == copy_action:
            self._copy_selected_values()
        elif action == copy_name_action:
            self._copy_selected_names()
        elif action == copy_both_action:
            self._copy_selected_pairs()
        elif action == copy_all_action:
            self._copy_all_properties()
        elif 'open_url_action' in locals() and action == open_url_action:
            self._open_selected_url()
        elif 'view_details_action' in locals() and action == view_details_action:
            self._view_selected_details()
    
    def _copy_selected_values(self):
        """Copy selected property values to clipboard"""
        values = []
        for index in self.properties_table.selectedIndexes():
            if index.column() == 1:  # Value column
                values.append(self.properties_table.item(index.row(), index.column()).text())
                
        if values:
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(values))
            self.status_bar.showMessage("Values copied to clipboard", 2000)
    
    def _copy_selected_names(self):
        """Copy selected property names to clipboard"""
        names = []
        for index in self.properties_table.selectedIndexes():
            if index.column() == 0:  # Name column
                names.append(self.properties_table.item(index.row(), index.column()).text())
                
        if names:
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(names))
            self.status_bar.showMessage("Property names copied to clipboard", 2000)
    
    def _copy_selected_pairs(self):
        """Copy selected property name-value pairs to clipboard"""
        pairs = []
        selected_rows = set()
        
        # Get all selected rows
        for index in self.properties_table.selectedIndexes():
            selected_rows.add(index.row())
            
        # For each row, get the name and value
        for row in selected_rows:
            name_item = self.properties_table.item(row, 0)
            value_item = self.properties_table.item(row, 1)
            
            if name_item and value_item:
                name = name_item.text()
                value = value_item.text()
                pairs.append(f"{name}: {value}")
                
        if pairs:
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(pairs))
            self.status_bar.showMessage("Properties copied to clipboard", 2000)
    
    def _copy_all_properties(self):
        """Copy all properties to clipboard"""
        pairs = []
        
        # Get all rows except separators
        for row in range(self.properties_table.rowCount()):
            # Skip rows that span columns (separators)
            if self.properties_table.columnSpan(row, 0) > 1:
                continue
                
            name_item = self.properties_table.item(row, 0)
            value_item = self.properties_table.item(row, 1)
            
            if name_item and value_item:
                name = name_item.text()
                value = value_item.text()
                pairs.append(f"{name}: {value}")
                
        if pairs:
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(pairs))
            self.status_bar.showMessage("All properties copied to clipboard", 2000)
    
    def _open_selected_url(self):
        """Open the selected URL in the default browser"""
        for index in self.properties_table.selectedIndexes():
            if index.column() == 1:  # Value column
                item = self.properties_table.item(index.row(), index.column())
                raw_value = item.data(Qt.UserRole)
                if isinstance(raw_value, str) and (raw_value.startswith('http://') or raw_value.startswith('https://')):
                    import webbrowser
                    webbrowser.open(raw_value)
                    break
    
    def _view_selected_details(self):
        """Show details for complex data types"""
        for index in self.properties_table.selectedIndexes():
            if index.column() == 1:  # Value column
                item = self.properties_table.item(index.row(), index.column())
                raw_value = item.data(Qt.UserRole)
                name_item = self.properties_table.item(index.row(), 0)
                key = name_item.text() if name_item else "Property"
                self._show_detailed_property(key, raw_value)
                break
    
    def _export_properties(self):
        """Export properties to clipboard or file"""
        menu = QMenu()
        copy_clipboard = menu.addAction("Copy to Clipboard")
        menu.addSeparator()
        export_csv = menu.addAction("Export as CSV")
        export_json = menu.addAction("Export as JSON")
        
        # Get position to show menu
        button = self.sender()
        action = menu.exec_(button.mapToGlobal(QPoint(0, button.height())))
        
        if action == copy_clipboard:
            self._copy_all_properties()
        elif action == export_csv:
            self._export_as_csv()
        elif action == export_json:
            self._export_as_json()
    
    def _export_as_csv(self):
        """Export properties as CSV file"""
        from PySide6.QtWidgets import QFileDialog
        import csv
        
        # Get filename from user
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Properties", "", "CSV Files (*.csv)"
        )
        
        if not filename:
            return
            
        try:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Property", "Value"])
                
                # Write all rows except separators
                for row in range(self.properties_table.rowCount()):
                    # Skip rows that span columns (separators)
                    if self.properties_table.columnSpan(row, 0) > 1:
                        continue
                        
                    name_item = self.properties_table.item(row, 0)
                    value_item = self.properties_table.item(row, 1)
                    
                    if name_item and value_item:
                        writer.writerow([name_item.text(), value_item.text()])
                        
            self.status_bar.showMessage(f"Properties exported to {filename}", 3000)
        except Exception as e:
            logger.error(f"Failed to export properties as CSV: {e}")
            self.status_bar.showMessage("Failed to export properties", 3000)
    
    def _export_as_json(self):
        """Export properties as JSON file"""
        from PySide6.QtWidgets import QFileDialog
        import json
        
        # Get filename from user
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Properties", "", "JSON Files (*.json)"
        )
        
        if not filename:
            return
            
        try:
            properties = {}
            
            # Get all rows except separators
            for row in range(self.properties_table.rowCount()):
                # Skip rows that span columns (separators)
                if self.properties_table.columnSpan(row, 0) > 1:
                    continue
                    
                name_item = self.properties_table.item(row, 0)
                value_item = self.properties_table.item(row, 1)
                
                if name_item and value_item:
                    # Use original key format (not title case)
                    name = name_item.toolTip() or name_item.text().lower().replace(' ', '_')
                    # Use raw value if available
                    value = value_item.data(Qt.UserRole)
                    if value is None:
                        value = value_item.text()
                    properties[name] = value
                    
            with open(filename, 'w') as jsonfile:
                json.dump(properties, jsonfile, indent=2)
                        
            self.status_bar.showMessage(f"Properties exported to {filename}", 3000)
        except Exception as e:
            logger.error(f"Failed to export properties as JSON: {e}")
            self.status_bar.showMessage("Failed to export properties", 3000)
    
    # Event handlers
    
    @Slot()
    def on_new_device(self):
        """Create a new device"""
        logger.debug("Creating new device")
        
        # Use the device table's properties dialog to add a new device
        device_table = self.findChild(DeviceTableView)
        if device_table:
            device_table._on_action_add_device(None)
        else:
            # Fallback if the device table is not found
            from ..core.device_manager import Device
            device = Device(name="New Device")
            self.device_manager.add_device(device)
        
    @Slot()
    def on_new_group(self):
        """Create a new device group"""
        logger.debug("Creating new group")
        self.device_manager.create_group("New Group")
        
    @Slot()
    def on_import_devices(self):
        """Import devices from a file"""
        logger.debug("Importing devices")
        from .import_wizard import run_device_import_wizard
        
        run_device_import_wizard(self.device_manager, self)
        
    @Slot()
    def on_save(self):
        """Save all devices"""
        logger.debug("Saving devices")
        self.device_manager.save_devices()
        self.status_bar.showMessage("Devices saved", 3000)
        
    @Slot()
    def on_select_all(self):
        """Select all devices"""
        logger.debug("Selecting all devices")
        devices = self.device_manager.get_devices()
        if devices:
            for device in devices:
                self.device_manager.select_device(device, exclusive=False)
                
    @Slot()
    def on_deselect_all(self):
        """Deselect all devices"""
        logger.debug("Deselecting all devices")
        self.device_manager.clear_selection()
        
    @Slot()
    def on_delete(self):
        """Delete selected devices"""
        selected_devices = self.device_manager.get_selected_devices()
        logger.debug(f"Deleting {len(selected_devices)} selected devices")
        
        for device in selected_devices.copy():
            self.device_manager.remove_device(device)
            
    @Slot()
    def on_refresh(self):
        """Refresh device status"""
        logger.debug("Refreshing devices")
        self.device_manager.refresh_devices()
        self.status_bar.showMessage("Devices refreshed", 3000)
        
    @Slot()
    def on_plugin_manager(self):
        """Open plugin manager dialog"""
        logger.debug("Opening plugin manager")
        dialog = PluginManagerDialog(self.plugin_manager, self)
        dialog.exec()
        
    @Slot()
    def on_settings(self):
        """Open settings dialog"""
        logger.debug("Opening settings dialog")
        from .settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.config, self)
        dialog.exec()
        
    @Slot()
    def on_save_workspace(self):
        """Save current workspace"""
        logger.debug("Saving workspace")
        success = self.device_manager.save_workspace()
        if success:
            self.status_bar.showMessage(f"Workspace saved: {self.device_manager.current_workspace}", 3000)
        else:
            self.status_bar.showMessage("Failed to save workspace", 3000)
    
    @Slot()
    def on_manage_workspaces(self):
        """Manage workspaces"""
        logger.debug("Managing workspaces")
        self.app.show_workspace_selection(is_startup=False)
        
    @Slot()
    def on_recycle_bin(self):
        """Handle recycle bin action"""
        logger.debug("Opening recycle bin")
        
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
            QTableWidgetItem, QHeaderView, QPushButton, QMessageBox
        )
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Recycle Bin")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Get devices from recycle bin
        recycled_devices = self.device_manager.get_recycle_bin_devices()
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel(f"Recycle Bin - {len(recycled_devices)} deleted device(s)")
        header_layout.addWidget(header_label)
        
        # Add a spacer to push buttons to the right
        from PySide6.QtWidgets import QSpacerItem, QSizePolicy
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        header_layout.addItem(spacer)
        
        # Add refresh button
        refresh_button = QPushButton("Refresh")
        header_layout.addWidget(refresh_button)
        
        layout.addLayout(header_layout)
        
        # Create table for devices
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Alias", "Hostname", "IP Address", "Status", "Groups"])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(table)
        
        # Add devices to table (coerce all values to str to avoid shiboken overflow when
        # a property holds an int like -9223372036854775808, which Qt marshals as 32-bit)
        def _cell_text(val, default=""):
            return str(val) if val is not None else default

        table.setRowCount(len(recycled_devices))
        for row, device in enumerate(recycled_devices):
            table.setItem(row, 0, QTableWidgetItem(_cell_text(device.get_property("alias", ""))))
            table.setItem(row, 1, QTableWidgetItem(_cell_text(device.get_property("hostname", ""))))
            table.setItem(row, 2, QTableWidgetItem(_cell_text(device.get_property("ip_address", ""))))
            table.setItem(row, 3, QTableWidgetItem(_cell_text(device.get_property("status", ""))))
            groups = device.get_property("_recycled_groups", [])
            table.setItem(row, 4, QTableWidgetItem(", ".join(str(g) for g in groups)))
            
            table.item(row, 0).setData(Qt.UserRole, device.id)

        # Buttons
        button_layout = QHBoxLayout()
        
        restore_button = QPushButton("Restore Selected")
        restore_all_button = QPushButton("Restore All")
        delete_button = QPushButton("Delete Selected Permanently")
        empty_button = QPushButton("Empty Recycle Bin")
        
        button_layout.addWidget(restore_button)
        button_layout.addWidget(restore_all_button)
        button_layout.addWidget(delete_button)
        button_layout.addWidget(empty_button)
        
        layout.addLayout(button_layout)
        
        # Enable buttons only if there are devices
        has_devices = len(recycled_devices) > 0
        restore_all_button.setEnabled(has_devices)
        empty_button.setEnabled(has_devices)
        
        # Handle refresh
        def refresh_table():
            recycled_devices = self.device_manager.get_recycle_bin_devices()
            header_label.setText(f"Recycle Bin - {len(recycled_devices)} deleted device(s)")
            table.setRowCount(len(recycled_devices))
            for row, device in enumerate(recycled_devices):
                table.setItem(row, 0, QTableWidgetItem(_cell_text(device.get_property("alias", ""))))
                table.setItem(row, 1, QTableWidgetItem(_cell_text(device.get_property("hostname", ""))))
                table.setItem(row, 2, QTableWidgetItem(_cell_text(device.get_property("ip_address", ""))))
                table.setItem(row, 3, QTableWidgetItem(_cell_text(device.get_property("status", ""))))
                groups = device.get_property("_recycled_groups", [])
                table.setItem(row, 4, QTableWidgetItem(", ".join(str(g) for g in groups)))
                table.item(row, 0).setData(Qt.UserRole, device.id)
                
            # Update button state
            has_devices = len(recycled_devices) > 0
            restore_all_button.setEnabled(has_devices)
            empty_button.setEnabled(has_devices)
        
        # Handle restore button
        def restore_selected():
            selected_rows = table.selectionModel().selectedRows()
            if not selected_rows:
                return
                
            devices_to_restore = []
            for index in selected_rows:
                device = table.item(index.row(), 0).data(Qt.UserRole)
                devices_to_restore.append(device)
                
            if devices_to_restore:
                for device in devices_to_restore:
                    self.device_manager.restore_device(device)
                    
                count = len(devices_to_restore)
                QMessageBox.information(
                    dialog,
                    "Devices Restored",
                    f"{count} device{'s' if count != 1 else ''} restored from the recycle bin."
                )
                refresh_table()
        
        # Handle restore all button
        def restore_all():
            if not recycled_devices:
                return
                
            self.device_manager.restore_all_devices()
            QMessageBox.information(
                dialog,
                "All Devices Restored",
                f"All {len(recycled_devices)} device{'s' if len(recycled_devices) != 1 else ''} restored from the recycle bin."
            )
            refresh_table()
        
        # Handle delete button
        def delete_selected():
            selected_rows = table.selectionModel().selectedRows()
            if not selected_rows:
                return
                
            devices_to_delete = []
            for index in selected_rows:
                device = table.item(index.row(), 0).data(Qt.UserRole)
                devices_to_delete.append(device)
                
            if devices_to_delete:
                count = len(devices_to_delete)
                result = QMessageBox.question(
                    dialog,
                    "Confirm Permanent Deletion",
                    f"Are you sure you want to permanently delete {count} device{'s' if count != 1 else ''}?\nThis action cannot be undone.",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if result == QMessageBox.Yes:
                    for device in devices_to_delete:
                        self.device_manager.permanently_delete_device(device)
                        
                    QMessageBox.information(
                        dialog,
                        "Devices Deleted",
                        f"{count} device{'s' if count != 1 else ''} permanently deleted."
                    )
                    refresh_table()
        
        # Handle empty button
        def empty_recycle_bin():
            if not recycled_devices:
                return
                
            result = QMessageBox.question(
                dialog,
                "Confirm Empty Recycle Bin",
                f"Are you sure you want to permanently delete all {len(recycled_devices)} device{'s' if len(recycled_devices) != 1 else ''} in the recycle bin?\nThis action cannot be undone.",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                self.device_manager.empty_recycle_bin()
                QMessageBox.information(
                    dialog,
                    "Recycle Bin Emptied",
                    "All devices have been permanently deleted."
                )
                refresh_table()
        
        # Connect signals
        refresh_button.clicked.connect(refresh_table)
        restore_button.clicked.connect(restore_selected)
        restore_all_button.clicked.connect(restore_all)
        delete_button.clicked.connect(delete_selected)
        empty_button.clicked.connect(empty_recycle_bin)
        
        # Enable restore and delete buttons only when items are selected
        def on_selection_changed():
            has_selection = len(table.selectionModel().selectedRows()) > 0
            restore_button.setEnabled(has_selection)
            delete_button.setEnabled(has_selection)
        
        table.selectionModel().selectionChanged.connect(on_selection_changed)
        on_selection_changed()  # Initial state
        
        # Show dialog
        dialog.exec()
        
    @Slot()
    def on_documentation(self):
        """Show the documentation dialog"""
        from .documentation_dialog import DocumentationDialog
        dialog = DocumentationDialog(self)
        dialog.exec()
        
    @Slot()
    def on_report_issue(self):
        """Show the report issue dialog"""
        from .report_issue_dialog import ReportIssueDialog
        dialog = ReportIssueDialog(self.app, self)
        dialog.exec()
        
    @Slot()
    def on_about(self):
        """Show the about dialog"""
        from .about_dialog import AboutDialog
        dialog = AboutDialog(self.app, self)
        dialog.exec()
        
    @Slot()
    def on_check_updates(self):
        """Handle check for updates action"""
        logger.debug("Manual check for updates requested")
        # Show message while checking
        self.status_bar.showMessage("Checking for updates...", 3000)
        # Check for updates and show result even if no updates available
        self.check_for_updates(silent=False)
        
    @Slot(str, str, str)
    def on_update_available(self, current_version, new_version, release_notes):
        """Handle update available signal
        
        Args:
            current_version: Current version string
            new_version: New version string
            release_notes: Release notes for the new version
        """
        logger.info(f"Update available: {current_version} -> {new_version}")
        
        # Check if this version has been skipped
        skipped_version = self.config.get("general.skipped_version", "")
        if skipped_version == new_version:
            logger.debug(f"Update {new_version} was previously skipped")
            return
        
        # Show update dialog
        from .update_dialog import UpdateDialog
        dialog = UpdateDialog(current_version, new_version, release_notes, self)
        dialog.exec()
        
    # Signal handlers
    
    @Slot(object)
    def on_device_added(self, device):
        """Handle device added signal"""
        logger.debug(f"Device added: {device}")
        self.update_status_bar()
        
    @Slot(object)
    def on_device_removed(self, device):
        """Handle device removed signal"""
        logger.debug(f"Device removed: {device}")
        self.update_status_bar()
        
    @Slot(object)
    def on_device_changed(self, device):
        """Handle device changed signal"""
        logger.debug(f"Device changed: {device}")
        
    @Slot(object)
    def on_group_added(self, group):
        """Handle group added signal"""
        logger.debug(f"Group added: {group}")
        
    @Slot(object)
    def on_group_removed(self, group):
        """Handle group removed signal"""
        logger.debug(f"Group removed: {group}")
        
    @Slot(list)
    def on_selection_changed(self, devices):
        """Handle selection changed signal"""
        logger.debug(f"Selection changed: {len(devices)} devices selected")
        self.update_status_bar()
        
        # Pass all selected devices to the property panel
        self.update_property_panel(devices)

    @Slot(object, object)
    def _on_table_highlight_changed(self, selected, deselected):
        """Update property panel based on highlights when nothing is checked."""
        if self.device_manager.get_selected_devices():
            return
        if hasattr(self, "device_table") and self.device_table:
            devices = self.device_table.get_selected_devices()
        else:
            devices = []
        self.update_property_panel(devices)

    @Slot(list)
    def on_group_selection_changed(self, groups):
        """Handle group selection from the device tree"""
        if not groups:
            return
            
        self.update_group_panel(groups)

    @Slot(object)
    def on_group_filter_requested(self, group):
        """Apply a group filter to the device table"""
        if hasattr(self, "device_table"):
            self.device_table.set_group_filter(group)
        
    @Slot(object)
    def on_plugin_loaded(self, plugin_info):
        """Handle plugin loaded signal"""
        logger.debug(f"Plugin loaded: {plugin_info}")
        self.add_plugin_ui_components(plugin_info)
        
        # If we're waiting to restore plugin layouts, schedule a restore
        # Use a timer to allow all plugins to finish loading
        if self._pending_plugin_layout_restore:
            self._layout_restore_timer.stop()  # Reset timer
            self._layout_restore_timer.start(500)  # Wait 500ms for other plugins to load
        
    @Slot(object)
    def on_plugin_unloaded(self, plugin_info):
        """Handle plugin unloaded signal"""
        logger.debug(f"Plugin unloaded: {plugin_info}")
        self.remove_plugin_ui_components(plugin_info)
        
    def closeEvent(self, event):
        """Save window state and size on close"""
        # Mark device tree model as shutting down to prevent recursive errors
        if hasattr(self, 'device_tree_model') and self.device_tree_model:
            try:
                self.device_tree_model._is_shutting_down = True
            except Exception:
                pass
        
        # Save window state, position and size
        settings = QSettings(self.app.applicationName(), "WindowState")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.setValue("size", self.size())
        settings.setValue("pos", self.pos())
        logger.debug("Window state and position saved")
        
        # Save the current workspace
        self.device_manager.save_workspace()
        
        # Also save the window layout specifically for this workspace
        self._save_workspace_layout()
        
        # Unload all plugins
        self.plugin_manager.unload_all_plugins()
        
        # Accept the event
        event.accept()
        
    def _save_workspace_layout(self):
        """Save window layout for the current workspace"""
        workspace_name = self.device_manager.current_workspace
        workspace_dir = os.path.join(self.device_manager.workspaces_dir, workspace_name)
        
        # Create workspace settings directory if it doesn't exist
        settings_dir = os.path.join(workspace_dir, "settings")
        os.makedirs(settings_dir, exist_ok=True)
        
        # Save window state to workspace-specific settings
        settings = QSettings(os.path.join(settings_dir, "window_layout.ini"), QSettings.IniFormat)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.setValue("size", self.size())
        settings.setValue("pos", self.pos())
        logger.debug(f"Saved window layout for workspace: {workspace_name}")
        
        if hasattr(self, "device_tree_panel"):
            self.device_tree_panel.save_state()
    
    def _on_dock_widget_changed(self):
        """Handle dock widget changes (moved, resized, etc.)"""
        # Debounce layout saving to avoid excessive file writes
        # Reset timer - will save 500ms after last change
        if hasattr(self, 'device_manager') and hasattr(self.device_manager, 'current_workspace'):
            self._layout_save_timer.stop()
            self._layout_save_timer.start(500)
    
    def _restore_plugin_layout_after_load(self):
        """Restore plugin dock widget layouts after plugins are loaded"""
        if not self._pending_plugin_layout_restore:
            return
        
        try:
            workspace_name = self.device_manager.current_workspace
            workspace_dir = os.path.join(self.device_manager.workspaces_dir, workspace_name)
            settings_dir = os.path.join(workspace_dir, "settings")
            layout_file = os.path.join(settings_dir, "window_layout.ini")
            
            if os.path.exists(layout_file):
                logger.debug(f"Restoring plugin dock widget layouts for workspace: {workspace_name}")
                settings = QSettings(layout_file, QSettings.IniFormat)
                
                if settings.contains("windowState"):
                    # Ensure we have the correct type (QByteArray)
                    state_value = settings.value("windowState")
                    if not isinstance(state_value, QByteArray):
                        state_value = QByteArray(state_value)
                    
                    # Restore state again now that plugin dock widgets exist
                    self.restoreState(state_value)
                    logger.debug("Plugin dock widget layouts restored")
            
            self._pending_plugin_layout_restore = False
        except Exception as e:
            logger.error(f"Failed to restore plugin layout: {e}", exc_info=True)
            self._pending_plugin_layout_restore = False
        
    def _restore_window_state(self):
        """Restore window state from settings"""
        try:
            # First try to load workspace-specific layout if available
            workspace_name = self.device_manager.current_workspace
            workspace_dir = os.path.join(self.device_manager.workspaces_dir, workspace_name)
            settings_dir = os.path.join(workspace_dir, "settings")
            layout_file = os.path.join(settings_dir, "window_layout.ini")
            
            if os.path.exists(layout_file):
                logger.debug(f"Restoring workspace-specific layout for: {workspace_name}")
                settings = QSettings(layout_file, QSettings.IniFormat)
                
                if settings.contains("geometry"):
                    # Ensure we have the correct type (QByteArray)
                    geometry_value = settings.value("geometry")
                    if not isinstance(geometry_value, QByteArray):
                        geometry_value = QByteArray(geometry_value)
                    
                    self.restoreGeometry(geometry_value)
                    logger.debug("Workspace-specific geometry restored")
                
                if settings.contains("windowState"):
                    # Ensure we have the correct type (QByteArray)
                    state_value = settings.value("windowState")
                    if not isinstance(state_value, QByteArray):
                        state_value = QByteArray(state_value)
                    
                    self.restoreState(state_value)
                    logger.debug("Workspace-specific window state restored")
                    
                return  # Successfully restored workspace-specific layout
            
            # Fall back to application-wide settings if workspace-specific not available
            settings = QSettings(self.app.applicationName(), "WindowState")
            # Restore geometry if available
            if settings.contains("geometry"):
                # Ensure we have the correct type (QByteArray)
                geometry_value = settings.value("geometry")
                if not isinstance(geometry_value, QByteArray):
                    geometry_value = QByteArray(geometry_value)
                
                self.restoreGeometry(geometry_value)
                logger.debug("Window geometry restored")
            
            # Restore window state (dock positions etc.)
            if settings.contains("windowState"):
                # Ensure we have the correct type (QByteArray)
                state_value = settings.value("windowState")
                if not isinstance(state_value, QByteArray):
                    state_value = QByteArray(state_value)
                
                self.restoreState(state_value)
                logger.debug("Window state restored")
                
            # Fallback to size and position if geometry not available
            elif settings.contains("size") and settings.contains("pos"):
                self.resize(settings.value("size"))
                self.move(settings.value("pos"))
                logger.debug("Window size and position restored")
                
        except Exception as e:
            logger.error(f"Failed to restore window state: {e}")
            # If restoration fails, use default size and position
            self.resize(1200, 800)
        
    def findMenu(self, menu_name):
        """Find a menu by name
        
        Args:
            menu_name: The name of the menu to find
            
        Returns:
            QMenu: The menu if found, None otherwise
        """
        logger.debug(f"Looking for menu: {menu_name}")
        
        # Check main menubar
        for menu in self.menuBar().findChildren(QMenu, options=Qt.FindDirectChildrenOnly):
            if menu.title() == menu_name:
                return menu
            
        # Check if we have the menu stored as an attribute
        if hasattr(self, f"menu_{menu_name.lower().replace(' ', '_')}"):
            return getattr(self, f"menu_{menu_name.lower().replace(' ', '_')}")
        
        # Not found
        logger.debug(f"Menu '{menu_name}' not found")
        return None 

    def _setup_autosave(self):
        """Setup autosave functionality"""
        # Create autosave timer
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.on_autosave)
        
        # Track whether changes have been made
        self.workspace_changed = False
        
        # Update autosave settings from config
        self._update_autosave_settings()
        
        # Connect to config changes to update autosave settings
        self.config.config_changed.connect(self._update_autosave_settings)
        
        # Connect to device manager signals to track changes
        self.device_manager.device_added.connect(self._on_workspace_changed)
        self.device_manager.device_removed.connect(self._on_workspace_changed)
        self.device_manager.device_changed.connect(self._on_workspace_changed)
        self.device_manager.group_added.connect(self._on_workspace_changed)
        self.device_manager.group_removed.connect(self._on_workspace_changed)
        
    def _update_autosave_settings(self):
        """Update autosave settings from config"""
        # Check if autosave is enabled
        enabled = self.config.get("autosave.enabled", False)
        
        # If enabled, start the timer with the configured interval
        if enabled:
            interval = self.config.get("autosave.interval", 5)
            self.autosave_timer.setInterval(interval * 60 * 1000)  # Convert minutes to milliseconds
            
            # Start the timer if it's not already running
            if not self.autosave_timer.isActive():
                self.autosave_timer.start()
                logger.debug(f"Autosave enabled with interval {interval} minutes")
        else:
            # Stop the timer if it's running
            if self.autosave_timer.isActive():
                self.autosave_timer.stop()
                logger.debug("Autosave disabled")
        
    def _on_workspace_changed(self, *args):
        """Track that workspace has changed for smart autosave"""
        self.workspace_changed = True
    
    @Slot()
    def on_autosave(self):
        """Handle autosave"""
        # Check if we should only save on changes
        only_on_changes = self.config.get("autosave.only_on_changes", True)
        
        # If only saving on changes and no changes made, skip
        if only_on_changes and not self.workspace_changed:
            logger.debug("Autosave skipped - no changes made")
            return
            
        logger.debug("Autosaving workspace")
        
        # Check if we should create backups
        create_backups = self.config.get("autosave.create_backups", True)
        
        if create_backups:
            self._create_backup()
            
        # Save the workspace
        self.device_manager.save_workspace()
        
        # Reset changed flag
        self.workspace_changed = False
        
        # Show notification if enabled
        show_notification = self.config.get("autosave.show_notification", False)
        if show_notification:
            self.status_bar.showMessage("Workspace autosaved", 3000)
            
    def _create_backup(self):
        """Create a backup of the current workspace"""
        import os
        import shutil
        import datetime
        
        try:
            # Get backup settings
            backup_dir = self.config.get("autosave.backup_directory", "")
            max_backups = self.config.get("autosave.max_backups", 10)
            
            # If no backup directory specified, use default in config directory
            if not backup_dir:
                backup_dir = os.path.join(self.config.config_dir, "backups")
                
            # Ensure backup directory exists
            os.makedirs(backup_dir, exist_ok=True)
            
            # Get workspace directory
            workspace_name = self.device_manager.current_workspace
            workspace_dir = os.path.join(self.device_manager.workspaces_dir, workspace_name)
            
            # Create backup filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{workspace_name}_{timestamp}.zip"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Create zip backup
            import zipfile
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(workspace_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, os.path.dirname(workspace_dir))
                        zipf.write(file_path, arcname)
            
            logger.debug(f"Created workspace backup: {backup_path}")
            
            # Clean up old backups if we have more than max_backups
            self._cleanup_old_backups(backup_dir, workspace_name, max_backups)
            
        except Exception as e:
            logger.error(f"Failed to create workspace backup: {e}")
            
    def _cleanup_old_backups(self, backup_dir, workspace_name, max_backups):
        """Clean up old backups if there are more than max_backups"""
        import os
        import glob
        
        try:
            # Get list of backup files for this workspace
            backup_pattern = os.path.join(backup_dir, f"{workspace_name}_*.zip")
            backup_files = glob.glob(backup_pattern)
            
            # Sort by modification time (oldest first)
            backup_files.sort(key=os.path.getmtime)
            
            # Delete oldest backups if we have too many
            while len(backup_files) > max_backups:
                oldest_backup = backup_files.pop(0)
                os.remove(oldest_backup)
                logger.debug(f"Deleted old workspace backup: {oldest_backup}")
                
        except Exception as e:
            logger.error(f"Failed to clean up old backups: {e}")
        
    def _setup_update_checker(self):
        """Set up the update checker"""
        from src.core.update_checker import UpdateChecker
        
        self.update_checker = UpdateChecker(self.config)
        
        # Connect signals
        self.update_checker.update_available.connect(self.on_update_available)
        
        # Check for updates on startup if enabled
        if self.config.get("general.check_updates", True):
            # Schedule update check after a delay to not slow down startup
            QTimer.singleShot(5000, self.check_for_updates)

    def check_for_updates(self, silent=True):
        """Check for updates
        
        Args:
            silent: If True, don't show message if no updates are available
        """
        logger.debug("Checking for updates")
        
        # Get branch from configuration
        branch = self.update_checker.get_branch()
        
        # Check for updates in the background
        def check_thread():
            result = self.update_checker.check_for_updates(branch)
            
            # Show message if no updates available and not in silent mode
            if not silent and not result[0]:
                # Use invokeMethod to safely update UI from another thread
                QTimer.singleShot(0, lambda: self.status_bar.showMessage("No updates available", 3000))
        
        # Run in another thread to not block UI
        import threading
        thread = threading.Thread(target=check_thread)
        thread.daemon = True
        thread.start() 

    def _format_property_value(self, value):
        """Format a property value for display based on type
        
        Args:
            value: The value to format
            
        Returns:
            str: Formatted value as a string
        """
        # Return placeholder for None values
        if value is None:
            return "--"
            
        # Handle different data types
        if isinstance(value, bool):
            return "Yes" if value else "No"
            
        elif isinstance(value, (int, float)):
            # Format large numbers with commas
            if isinstance(value, int) and abs(value) >= 10000:
                return f"{value:,}"
            # Format floats with appropriate decimal places
            elif isinstance(value, float):
                # Limit to 4 decimal places but trim trailing zeros
                return f"{value:.4f}".rstrip('0').rstrip('.') if '.' in f"{value:.4f}" else f"{value:.0f}"
            return str(value)
            
        elif isinstance(value, list):
            # Format lists as comma-separated values
            if not value:
                return "Empty list"
            return ", ".join(str(item) for item in value)
            
        elif isinstance(value, dict):
            # For dictionaries, show a preview of the content instead of just item count
            if not value:
                return "Empty dictionary"
            
            # Create a preview of dictionary contents
            preview_items = []
            for i, (k, v) in enumerate(value.items()):
                if i >= 3:  # Limit to first 3 key-value pairs
                    preview_items.append("...")
                    break
                # Format the key-value pair
                v_str = str(v)
                if isinstance(v, str) and len(v) > 20:
                    v_str = v[:17] + "..."
                elif isinstance(v, (dict, list)):
                    v_str = f"({type(v).__name__})"
                preview_items.append(f"{k}: {v_str}")
            
            return f"{{{', '.join(preview_items)}}} ({len(value)} items)"
            
        elif isinstance(value, str):
            # Check if it's a date/time string (ISO format or common formats)
            import re
            date_patterns = [
                # ISO date: 2023-10-15 or 2023-10-15T14:30:25
                r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$',
                # Common date: 10/15/2023 or 15/10/2023
                r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})$',
                # Date with time: 2023-10-15 14:30:25 or 10/15/2023 14:30:25
                r'^(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}) \d{1,2}:\d{2}(:\d{2})?$'
            ]
            
            # If it matches a date pattern, try to parse and format it
            for pattern in date_patterns:
                if re.match(pattern, value):
                    try:
                        import datetime
                        # Try different formats
                        for fmt in [
                            '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', 
                            '%m/%d/%Y', '%d/%m/%Y',
                            '%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%d/%m/%Y %H:%M:%S'
                        ]:
                            try:
                                date_obj = datetime.datetime.strptime(value, fmt)
                                # Format with a nice human-readable format
                                return date_obj.strftime('%b %d, %Y %I:%M %p').replace(' 12:00 AM', '')
                            except ValueError:
                                continue
                    except (ValueError, ImportError):
                        pass  # If parsing fails, just use the original string
            
            # For long text, truncate with ellipsis
            if len(value) > 100:
                return value[:97] + "..."
                
        # For all other types, convert to string
        return str(value)

    def _show_detailed_property(self, key, value):
        """Show a property value in detail in a dialog
        
        Args:
            key: The property key
            value: The property value
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Property Details: {key}")
        dialog.resize(600, 450)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Add the property name and basic info
        header_layout = QHBoxLayout()
        
        # Property name
        name_label = QLabel(f"<b>{key}</b>")
        name_label.setStyleSheet("font-size: 14px;")
        header_layout.addWidget(name_label)
        
        # Type information
        type_label = QLabel(f"Type: <code>{type(value).__name__}</code>")
        type_label.setStyleSheet("color: #606060;")
        header_layout.addWidget(type_label, alignment=Qt.AlignRight)
        
        layout.addLayout(header_layout)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Create a view button layout with options for different view modes
        view_options_layout = QHBoxLayout()
        
        # JSON view button
        json_view_btn = QPushButton("JSON View")
        json_view_btn.setCheckable(True)
        json_view_btn.setChecked(True)
        
        # Table view button (for dictionaries and list of dictionaries)
        table_view_btn = QPushButton("Table View")
        table_view_btn.setCheckable(True)
        table_view_btn.setEnabled(self._can_display_as_table(value))
        
        # Raw view button
        raw_view_btn = QPushButton("Raw View")
        raw_view_btn.setCheckable(True)
        
        # Add buttons to layout
        view_options_layout.addWidget(json_view_btn)
        view_options_layout.addWidget(table_view_btn)
        view_options_layout.addWidget(raw_view_btn)
        view_options_layout.addStretch()
        
        # Add view options to main layout
        layout.addLayout(view_options_layout)
        
        # Create a stacked widget to hold different views
        from PySide6.QtWidgets import QStackedWidget, QTableWidget, QTableWidgetItem
        stacked_widget = QStackedWidget()
        
        # JSON View with syntax highlighting for structured data
        json_view = QTextBrowser()
        json_view.setOpenExternalLinks(True)
        json_view.setStyleSheet("""
            QTextBrowser {
                font-family: "Consolas", "Monaco", monospace;
                font-size: 12px;
                background-color: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        # Format content based on the type and create JSON view
        self._format_json_view(json_view, value)
        stacked_widget.addWidget(json_view)
        
        # Table View for dictionaries and lists of dictionaries
        table_view = QTableWidget()
        table_view.setAlternatingRowColors(True)
        table_view.horizontalHeader().setStretchLastSection(True)
        table_view.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #E0E0E0;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #F5F5F5;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #D0D0D0;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 4px;
            }
        """)
        
        # Populate table view if possible
        self._populate_table_view(table_view, value)
        stacked_widget.addWidget(table_view)
        
        # Raw View
        raw_view = QTextBrowser()
        raw_view.setStyleSheet("""
            QTextBrowser {
                font-family: "Consolas", "Monaco", monospace;
                font-size: 12px;
                background-color: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        raw_view.setPlainText(str(value))
        stacked_widget.addWidget(raw_view)
        
        layout.addWidget(stacked_widget)
        
        # Set up button group for view selection
        from PySide6.QtWidgets import QButtonGroup
        view_button_group = QButtonGroup()
        view_button_group.addButton(json_view_btn, 0)
        view_button_group.addButton(table_view_btn, 1)
        view_button_group.addButton(raw_view_btn, 2)
        
        # Connect button group to stacked widget
        view_button_group.buttonClicked.connect(
            lambda button: stacked_widget.setCurrentIndex(view_button_group.id(button))
        )
        
        # Add bottom button row
        button_layout = QHBoxLayout()
        
        # Copy button
        copy_button = QPushButton("Copy")
        copy_button.setToolTip("Copy to clipboard")
        copy_button.clicked.connect(lambda: self._copy_property_value_to_clipboard(value))
        button_layout.addWidget(copy_button)
        
        # Export button for structured data
        if isinstance(value, (dict, list)):
            export_button = QPushButton("Export")
            export_button.setToolTip("Export to file")
            export_button.clicked.connect(lambda: self._export_property_value(key, value))
            button_layout.addWidget(export_button)
        
        # Spacer to push close button to the right
        button_layout.addStretch()
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def _can_display_as_table(self, value):
        """Check if the value can be displayed as a table
        
        Args:
            value: The value to check
            
        Returns:
            bool: True if the value can be displayed as a table
        """
        # Simple dictionary with simple values
        if isinstance(value, dict):
            return True
            
        # List of dictionaries with consistent keys
        if isinstance(value, list) and len(value) > 0 and all(isinstance(item, dict) for item in value):
            # Check if all dictionaries have the same keys
            keys = set(value[0].keys())
            return all(set(item.keys()) == keys for item in value)
        
        # Single level nested dictionary where all second-level values are simple types
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, dict):
                    for inner_k, inner_v in v.items():
                        if isinstance(inner_v, (dict, list)):
                            return False
            return True
            
        return False
    
    def _format_json_view(self, text_browser, value):
        """Format a value for display in the JSON view
        
        Args:
            text_browser: The QTextBrowser to display the content in
            value: The value to format
        """
        if isinstance(value, dict):
            try:
                import json
                formatted_json = json.dumps(value, indent=2, sort_keys=True)
                
                # Apply basic syntax highlighting using HTML
                highlighted_text = self._highlight_json(formatted_json)
                text_browser.setHtml(highlighted_text)
            except Exception:
                # Fallback to plain text if JSON highlighting fails
                text_browser.setPlainText(str(value))
                
        elif isinstance(value, list):
            # Different handling based on list content
            if all(isinstance(item, dict) for item in value) and len(value) > 0:
                # List of dictionaries - format as JSON with syntax highlighting
                try:
                    import json
                    formatted_json = json.dumps(value, indent=2, sort_keys=True)
                    highlighted_text = self._highlight_json(formatted_json)
                    text_browser.setHtml(highlighted_text)
                except Exception:
                    # Fallback to simple list format
                    content = "<ol>\n"
                    for item in value:
                        content += f"<li>{html.escape(str(item))}</li>\n"
                    content += "</ol>"
                    text_browser.setHtml(content)
            else:
                # Simple list with numbered items
                import html
                content = "<ol>\n"
                for item in value:
                    content += f"<li>{html.escape(str(item))}</li>\n"
                content += "</ol>"
                text_browser.setHtml(content)
        else:
            # For strings, handle URLs and multi-line text appropriately
            if isinstance(value, str):
                import html
                if value.startswith('http://') or value.startswith('https://'):
                    text_browser.setHtml(f'<a href="{html.escape(value)}">{html.escape(value)}</a>')
                elif '\n' in value:
                    # For multi-line text, preserve formatting with <pre> tags
                    text_browser.setHtml(f'<pre>{html.escape(value)}</pre>')
                else:
                    text_browser.setPlainText(value)
            else:
                text_browser.setPlainText(str(value))
    
    def _populate_table_view(self, table_widget, value):
        """Populate a table widget with the provided data
        
        Args:
            table_widget: The QTableWidget to populate
            value: The value to display in the table
        """
        table_widget.clear()
        
        # Case 1: Dictionary with simple values
        if isinstance(value, dict) and not any(isinstance(v, (dict, list)) for v in value.values()):
            table_widget.setColumnCount(2)
            table_widget.setHorizontalHeaderLabels(["Key", "Value"])
            table_widget.setRowCount(len(value))
            
            for i, (k, v) in enumerate(sorted(value.items())):
                key_item = QTableWidgetItem(str(k))
                value_item = QTableWidgetItem(str(v))
                key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                
                # Format boolean values
                if isinstance(v, bool):
                    value_item.setText("Yes" if v else "No")
                
                table_widget.setItem(i, 0, key_item)
                table_widget.setItem(i, 1, value_item)
                
            table_widget.resizeColumnsToContents()
            
        # Case 2: List of dictionaries with consistent keys
        elif isinstance(value, list) and len(value) > 0 and all(isinstance(item, dict) for item in value):
            # Get all keys from the first dictionary
            keys = list(value[0].keys())
            
            # Set column count and headers
            table_widget.setColumnCount(len(keys))
            table_widget.setHorizontalHeaderLabels(keys)
            table_widget.setRowCount(len(value))
            
            # Add data
            for row, item in enumerate(value):
                for col, key in enumerate(keys):
                    # Get value or empty string if key is missing
                    val = item.get(key, "")
                    table_item = QTableWidgetItem(str(val))
                    table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                    table_widget.setItem(row, col, table_item)
                    
            table_widget.resizeColumnsToContents()
            
        # Case 3: Nested dictionary (2 levels)
        elif isinstance(value, dict) and any(isinstance(v, dict) for v in value.values()):
            # Collect all second-level keys across all nested dictionaries
            all_inner_keys = set()
            for k, v in value.items():
                if isinstance(v, dict):
                    all_inner_keys.update(v.keys())
            
            # Convert to sorted list for consistent column order
            inner_keys = sorted(all_inner_keys)
            
            # Set column count and headers (first column for the outer key, rest for inner keys)
            table_widget.setColumnCount(1 + len(inner_keys))
            headers = ["Item"] + inner_keys
            table_widget.setHorizontalHeaderLabels(headers)
            
            # Count rows (one for each outer key that has a dictionary value)
            rows = sum(1 for k, v in value.items() if isinstance(v, dict))
            rows = max(1, rows)  # Ensure at least one row
            table_widget.setRowCount(rows)
            
            # Add data
            row = 0
            for outer_key, outer_value in sorted(value.items()):
                if isinstance(outer_value, dict):
                    # Set outer key in first column
                    key_item = QTableWidgetItem(str(outer_key))
                    key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                    table_widget.setItem(row, 0, key_item)
                    
                    # Fill inner values
                    for col, inner_key in enumerate(inner_keys, 1):
                        inner_value = outer_value.get(inner_key, "")
                        value_item = QTableWidgetItem(str(inner_value))
                        value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                        table_widget.setItem(row, col, value_item)
                    
                    row += 1
                    
            table_widget.resizeColumnsToContents()
        
        # If we couldn't make a table view, show a message
        if table_widget.rowCount() == 0:
            table_widget.setRowCount(1)
            table_widget.setColumnCount(1)
            table_widget.setHorizontalHeaderLabels(["Message"])
            message = QTableWidgetItem("Cannot display this data in table format")
            message.setFlags(message.flags() & ~Qt.ItemIsEditable)
            message.setTextAlignment(Qt.AlignCenter)
            table_widget.setItem(0, 0, message)
            
        # Optimize the view
        table_widget.horizontalHeader().setStretchLastSection(True)
        table_widget.resizeRowsToContents()
    
    def _highlight_json(self, json_str):
        """Apply basic syntax highlighting to JSON string
        
        Args:
            json_str: JSON string to highlight
            
        Returns:
            HTML formatted string with syntax highlighting
        """
        import html
        highlighted = html.escape(json_str)
        
        # Highlight strings (anything in quotes)
        highlighted = re.sub(
            r'(".*?")(?=:)', 
            r'<span style="color: #0000CD;">\1</span>', 
            highlighted
        )
        # Highlight values
        highlighted = re.sub(
            r': (".*?")(,|\n|$)', 
            r': <span style="color: #008000;">\1</span>\2', 
            highlighted
        )
        # Highlight numbers
        highlighted = re.sub(
            r'(: |\[)(\d+\.?\d*)(,|\n|$|\])', 
            r'\1<span style="color: #0000FF;">\2</span>\3', 
            highlighted
        )
        # Highlight booleans and null
        highlighted = re.sub(
            r': (true|false|null)(,|\n|$)', 
            r': <span style="color: #B22222;">\1</span>\2', 
            highlighted
        )
        
        # Wrap in pre tag for formatting
        return f'<pre style="margin: 0;">{highlighted}</pre>'
    
    def _copy_property_value_to_clipboard(self, value):
        """Copy property value to clipboard
        
        Args:
            value: The value to copy
        """
        clipboard = QApplication.clipboard()
        
        if isinstance(value, (dict, list)):
            import json
            try:
                # Format as JSON for structured data
                formatted_json = json.dumps(value, indent=2)
                clipboard.setText(formatted_json)
            except:
                clipboard.setText(str(value))
        else:
            clipboard.setText(str(value))
            
        self.status_bar.showMessage("Value copied to clipboard", 2000)
    
    def _export_property_value(self, key, value):
        """Export property value to a file
        
        Args:
            key: The property key/name
            value: The value to export
        """
        if not isinstance(value, (dict, list)):
            return
            
        # Create a file dialog to get the save location
        file_dialog = QFileDialog(self)
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setNameFilter("JSON files (*.json);;All files (*.*)")
        file_dialog.setDefaultSuffix("json")
        file_dialog.selectFile(f"{key}.json")
        
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            
            try:
                with open(file_path, 'w') as f:
                    import json
                    json.dump(value, f, indent=2)
                self.status_bar.showMessage(f"Exported to {file_path}", 3000)
            except Exception as e:
                logger.error(f"Error exporting property value: {e}")
                QMessageBox.critical(
                    self, 
                    "Export Error", 
                    f"An error occurred while exporting: {str(e)}"
                )
    
    def _handle_property_double_click(self, row, column):
        """Handle double click on a property row
        
        Args:
            row: The row that was double-clicked
            column: The column that was double-clicked
        """
        # Only process double clicks on the value column (1) for valid rows
        if column == 1 and row < self.properties_table.rowCount():
            # Skip if it's a separator row (span > 1)
            if self.properties_table.columnSpan(row, 0) > 1:
                return
                
            # Get the property value and name
            value_item = self.properties_table.item(row, 1)
            name_item = self.properties_table.item(row, 0)
            
            if value_item and name_item:
                raw_value = value_item.data(Qt.UserRole)
                key = name_item.text()
                
                # Open detailed view for dictionaries, lists, or long strings
                if isinstance(raw_value, (dict, list)) or (isinstance(raw_value, str) and len(raw_value) > 100):
                    self._show_detailed_property(key, raw_value)
                # For URLs, open in browser
                elif isinstance(raw_value, str) and (raw_value.startswith('http://') or raw_value.startswith('https://')):
                    import webbrowser
                    webbrowser.open(raw_value) 