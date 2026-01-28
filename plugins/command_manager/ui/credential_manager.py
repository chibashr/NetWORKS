#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Credential Manager for Command Manager plugin
"""

import os
import json
import ipaddress
from loguru import logger

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, 
    QLineEdit, QCheckBox, QFormLayout, QDialogButtonBox,
    QTabWidget, QWidget, QMessageBox, QGroupBox, QListWidget,
    QListWidgetItem
)
from PySide6.QtGui import QIcon, QPalette

from src.ui.plugin_ui_theme import mark_plugin_ui


class CredentialManager(QDialog):
    """Dialog for managing device credentials"""
    
    def __init__(self, plugin, devices=None, groups=None, subnets=None, parent=None):
        """Initialize the dialog
        
        Args:
            plugin: The command manager plugin
            devices: Optional list of devices to select
            groups: Optional list of device groups to select
            subnets: Optional list of subnets to select
            parent: Parent widget
        """
        super().__init__(parent)
        mark_plugin_ui(self)
        
        self.plugin = plugin
        self.devices = devices or []
        self.selected_groups = groups or []
        self.selected_subnets = subnets or []
        
        # Set dialog properties
        self.setWindowTitle("Credential Manager")
        self.resize(600, 500)
        
        # Create UI components
        self._create_ui()
        
        # Load credential data
        self._load_data()
        
        # Select the appropriate tab based on what was provided
        if self.selected_groups:
            self.tabs.setCurrentIndex(1)  # Group tab
        elif self.selected_subnets:
            self.tabs.setCurrentIndex(2)  # Subnet tab
        else:
            self.tabs.setCurrentIndex(0)  # Device tab
        
    def _create_ui(self):
        """Create the UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Add title label at the top
        title_label = QLabel("Device Credential Manager")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Add description
        desc_label = QLabel("Configure access credentials for devices, groups, and subnets")
        desc_label.setStyleSheet("font-size: 10pt; margin-bottom: 15px;")
        layout.addWidget(desc_label)
        
        # Tabbed interface
        self.tabs = QTabWidget()
        
        # Create tabs
        self._create_device_tab()
        self._create_group_tab()
        self._create_subnet_tab()
        
        # Add tabs to layout
        layout.addWidget(self.tabs)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Add help text (use palette for theme consistency)
        help_label = QLabel("Note: Credentials are stored securely and used for device access.")
        _pal = help_label.palette()
        help_label.setStyleSheet(
            f"font-style: italic; color: {_pal.color(QPalette.PlaceholderText).name()};"
        )
        
        layout.addWidget(help_label)
        layout.addWidget(button_box)
        
    def _create_device_tab(self):
        """Create the device credentials tab"""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Device list panel
        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 10, 0)
        
        # Add header and explanation
        list_layout.addWidget(QLabel("<b>Devices:</b>"))
        list_layout.addWidget(QLabel("Select a device to configure its credentials"))
        
        # Device list with search box
        self.device_list = QListWidget()
        self.device_list.setAlternatingRowColors(True)
        self.device_list.currentItemChanged.connect(self._on_device_selected)
        list_layout.addWidget(self.device_list)
        
        # Form panel
        form_panel = QWidget()
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(10, 0, 0, 0)
        
        # Add header
        form_layout.addWidget(QLabel("<b>Device Credentials:</b>"))
        form_layout.addWidget(QLabel("Configure connection settings for the selected device"))
        
        # Credential form
        cred_group = QGroupBox()
        cred_group.setStyleSheet("QGroupBox { padding-top: 15px; }")
        self.device_form = QFormLayout(cred_group)
        
        # Connection type
        self.device_conn_type = QComboBox()
        self.device_conn_type.addItems(["SSH", "Telnet"])
        self.device_form.addRow("Connection Type:", self.device_conn_type)
        
        # Username
        self.device_username = QLineEdit()
        self.device_username.setPlaceholderText("Enter username")
        self.device_form.addRow("Username:", self.device_username)
        
        # Password
        self.device_password = QLineEdit()
        self.device_password.setEchoMode(QLineEdit.Password)
        self.device_password.setPlaceholderText("Enter password")
        self.device_form.addRow("Password:", self.device_password)
        
        # Enable password
        self.device_enable = QLineEdit()
        self.device_enable.setEchoMode(QLineEdit.Password)
        self.device_enable.setPlaceholderText("Enter enable password (optional)")
        self.device_form.addRow("Enable Password:", self.device_enable)
        
        form_layout.addWidget(cred_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.device_save_btn = QPushButton("Save Credentials")
        self.device_save_btn.clicked.connect(self._on_save_device)
        self.device_save_btn.setEnabled(False)
        
        self.device_delete_btn = QPushButton("Delete Credentials")
        self.device_delete_btn.clicked.connect(self._on_delete_device)
        self.device_delete_btn.setEnabled(False)
        
        button_layout.addWidget(self.device_save_btn)
        button_layout.addWidget(self.device_delete_btn)
        button_layout.addStretch()
        
        form_layout.addLayout(button_layout)
        form_layout.addStretch()
        
        # Add panels to main layout
        layout.addWidget(list_panel, 1)
        layout.addWidget(form_panel, 2)
        
        # Add tab
        self.tabs.addTab(tab, "Device Credentials")
        
    def _create_group_tab(self):
        """Create the group credentials tab"""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Group list panel
        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 10, 0)
        
        # Add header and explanation
        list_layout.addWidget(QLabel("<b>Device Groups:</b>"))
        list_layout.addWidget(QLabel("Select a device group to configure its credentials"))
        
        # Group list with improved styling
        self.group_list = QListWidget()
        self.group_list.setAlternatingRowColors(True)
        self.group_list.currentItemChanged.connect(self._on_group_selected)
        list_layout.addWidget(self.group_list)
        
        # Form panel
        form_panel = QWidget()
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(10, 0, 0, 0)
        
        # Add header
        form_layout.addWidget(QLabel("<b>Group Credentials:</b>"))
        form_layout.addWidget(QLabel("Configure connection settings for the selected group"))
        
        # Credential form
        cred_group = QGroupBox()
        cred_group.setStyleSheet("QGroupBox { padding-top: 15px; }")
        self.group_form = QFormLayout(cred_group)
        
        # Connection type
        self.group_conn_type = QComboBox()
        self.group_conn_type.addItems(["SSH", "Telnet"])
        self.group_form.addRow("Connection Type:", self.group_conn_type)
        
        # Username
        self.group_username = QLineEdit()
        self.group_username.setPlaceholderText("Enter username")
        self.group_form.addRow("Username:", self.group_username)
        
        # Password
        self.group_password = QLineEdit()
        self.group_password.setEchoMode(QLineEdit.Password)
        self.group_password.setPlaceholderText("Enter password")
        self.group_form.addRow("Password:", self.group_password)
        
        # Enable password
        self.group_enable = QLineEdit()
        self.group_enable.setEchoMode(QLineEdit.Password)
        self.group_enable.setPlaceholderText("Enter enable password (optional)")
        self.group_form.addRow("Enable Password:", self.group_enable)
        
        form_layout.addWidget(cred_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.group_save_btn = QPushButton("Save Credentials")
        self.group_save_btn.clicked.connect(self._on_save_group)
        self.group_save_btn.setEnabled(False)
        
        self.group_delete_btn = QPushButton("Delete Credentials")
        self.group_delete_btn.clicked.connect(self._on_delete_group)
        self.group_delete_btn.setEnabled(False)
        
        button_layout.addWidget(self.group_save_btn)
        button_layout.addWidget(self.group_delete_btn)
        button_layout.addStretch()
        
        form_layout.addLayout(button_layout)
        form_layout.addStretch()
        
        # Add panels to main layout
        layout.addWidget(list_panel, 1)
        layout.addWidget(form_panel, 2)
        
        # Add tab
        self.tabs.addTab(tab, "Group Credentials")
        
    def _create_subnet_tab(self):
        """Create the subnet credentials tab"""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Subnet list panel
        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 10, 0)
        
        # Add header and explanation
        list_layout.addWidget(QLabel("<b>Subnets:</b>"))
        list_layout.addWidget(QLabel("Manage subnet credentials for automatic device connection"))
        
        # Subnet list with improved styling
        self.subnet_list = QListWidget()
        self.subnet_list.setAlternatingRowColors(True)
        self.subnet_list.currentItemChanged.connect(self._on_subnet_selected)
        list_layout.addWidget(self.subnet_list)
        
        # Add subnet section
        add_subnet_layout = QHBoxLayout()
        self.new_subnet = QLineEdit()
        self.new_subnet.setPlaceholderText("e.g. 192.168.1.0/24")
        
        add_btn = QPushButton("Add Subnet")
        add_btn.clicked.connect(self._on_add_subnet)
        
        add_subnet_layout.addWidget(self.new_subnet)
        add_subnet_layout.addWidget(add_btn)
        
        list_layout.addLayout(add_subnet_layout)
        
        # Form panel
        form_panel = QWidget()
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(10, 0, 0, 0)
        
        # Add header
        form_layout.addWidget(QLabel("<b>Subnet Credentials:</b>"))
        form_layout.addWidget(QLabel("Configure default connection settings for this subnet"))
        
        # Credential form
        cred_group = QGroupBox()
        cred_group.setStyleSheet("QGroupBox { padding-top: 15px; }")
        self.subnet_form = QFormLayout(cred_group)
        
        # Connection type
        self.subnet_conn_type = QComboBox()
        self.subnet_conn_type.addItems(["SSH", "Telnet"])
        self.subnet_form.addRow("Connection Type:", self.subnet_conn_type)
        
        # Username
        self.subnet_username = QLineEdit()
        self.subnet_username.setPlaceholderText("Enter username")
        self.subnet_form.addRow("Username:", self.subnet_username)
        
        # Password
        self.subnet_password = QLineEdit()
        self.subnet_password.setEchoMode(QLineEdit.Password)
        self.subnet_password.setPlaceholderText("Enter password")
        self.subnet_form.addRow("Password:", self.subnet_password)
        
        # Enable password
        self.subnet_enable = QLineEdit()
        self.subnet_enable.setEchoMode(QLineEdit.Password)
        self.subnet_enable.setPlaceholderText("Enter enable password (optional)")
        self.subnet_form.addRow("Enable Password:", self.subnet_enable)
        
        form_layout.addWidget(cred_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.subnet_save_btn = QPushButton("Save Credentials")
        self.subnet_save_btn.clicked.connect(self._on_save_subnet)
        self.subnet_save_btn.setEnabled(False)
        
        self.subnet_delete_btn = QPushButton("Delete Credentials")
        self.subnet_delete_btn.clicked.connect(self._on_delete_subnet)
        self.subnet_delete_btn.setEnabled(False)
        
        button_layout.addWidget(self.subnet_save_btn)
        button_layout.addWidget(self.subnet_delete_btn)
        button_layout.addStretch()
        
        form_layout.addLayout(button_layout)
        form_layout.addStretch()
        
        # Add panels to main layout
        layout.addWidget(list_panel, 1)
        layout.addWidget(form_panel, 2)
        
        # Add tab
        self.tabs.addTab(tab, "Subnet Credentials")
    
    def _load_data(self):
        """Load credential data"""
        self._load_devices()
        self._load_groups()
        self._load_subnets()
        
    def _load_devices(self):
        """Load devices into the list"""
        self.device_list.clear()
        
        # All devices from device manager
        if self.plugin.device_manager:
            all_devices = self.plugin.device_manager.get_devices()
            
            # If specific devices were provided, only show those
            display_devices = self.devices if self.devices else all_devices
            
            for device in display_devices:
                # Get device properties for display
                alias = device.get_property("alias", device.get_property("hostname", "Unnamed"))
                ip = device.get_property("ip_address", "")
                
                # Create list item with device info
                item = QListWidgetItem(f"{alias} ({ip})")
                item.setData(Qt.UserRole, device)
                
                # Check if credentials exist for this device (device-specific only, not fallback)
                device_creds = self.plugin.credential_store.get_device_credentials(device.id)
                has_creds = bool(device_creds and device_creds.get("username"))
                
                # Set font weight based on credential status
                font = item.font()
                font.setBold(has_creds)
                item.setFont(font)
                
                # Add to list
                self.device_list.addItem(item)
            
            # If specific devices were provided, select all of them
            if self.devices:
                # Clear any existing selection
                self.device_list.clearSelection()
                
                # Find and select all provided devices
                selected_count = 0
                for i in range(self.device_list.count()):
                    item = self.device_list.item(i)
                    device = item.data(Qt.UserRole)
                    # Check if this device is in the provided devices list
                    if device in self.devices:
                        item.setSelected(True)
                        selected_count += 1
                        # Set the first selected device as current
                        if selected_count == 1:
                            self.device_list.setCurrentItem(item)
                
                # If we selected devices, scroll to the first one
                if selected_count > 0:
                    first_selected = None
                    for i in range(self.device_list.count()):
                        item = self.device_list.item(i)
                        if item.isSelected():
                            first_selected = item
                            break
                    if first_selected:
                        self.device_list.scrollToItem(first_selected)
            else:
                # Select the first device if any are available
                if self.device_list.count() > 0:
                    self.device_list.setCurrentRow(0)
    
    def _load_groups(self):
        """Load device groups into the list"""
        self.group_list.clear()
        
        # Get all device groups if available
        try:
            device_groups = self.plugin.device_manager.get_groups()
            logger.debug(f"Retrieved {len(device_groups)} device groups")
            
            for group in device_groups:
                try:
                    # Handle different possible group structures
                    group_name = None
                    device_count = 0
                    
                    # Try to get group name
                    if isinstance(group, dict) and 'name' in group:
                        group_name = group['name']
                    elif hasattr(group, 'name'):
                        group_name = group.name
                    elif hasattr(group, 'get_name'):
                        group_name = group.get_name()
                    else:
                        # Use string representation as fallback
                        group_name = str(group)
                        logger.warning(f"Group missing name attribute, using {group_name}")
                    
                    # Try to get device count
                    if isinstance(group, dict) and 'devices' in group:
                        device_count = len(group['devices'])
                    elif hasattr(group, 'devices'):
                        device_count = len(group.devices)
                    elif hasattr(group, 'get_devices'):
                        device_count = len(group.get_devices())
                    elif hasattr(group, 'device_count'):
                        device_count = group.device_count
                    elif hasattr(group, 'get_device_count'):
                        device_count = group.get_device_count()
                    else:
                        logger.warning(f"Could not determine device count for group {group_name}")
                    
                    # Create list item with group info
                    item = QListWidgetItem(f"{group_name} ({device_count} devices)")
                    item.setData(Qt.UserRole, group)
                    
                    # Check if credentials exist for this group
                    has_creds = bool(self.plugin.credential_store.get_group_credentials(group_name))
                    
                    # Set font weight based on credential status
                    font = item.font()
                    font.setBold(has_creds)
                    item.setFont(font)
                    
                    # Add to list
                    self.group_list.addItem(item)
                except Exception as e:
                    logger.error(f"Error processing group: {e}")
            
            # Select the first group if any are available
            if self.group_list.count() > 0 and not self.selected_groups:
                self.group_list.setCurrentRow(0)
            
            # If specific groups were provided, select the first one
            if self.selected_groups and isinstance(self.selected_groups, (list, tuple)):
                # Find and select the item
                for i in range(self.group_list.count()):
                    item = self.group_list.item(i)
                    group_data = item.data(Qt.UserRole)
                    
                    # Compare based on group name which is more reliable than object reference
                    selected_group = self.selected_groups[0]
                    selected_group_name = None
                    
                    if isinstance(selected_group, dict) and 'name' in selected_group:
                        selected_group_name = selected_group['name']
                    elif hasattr(selected_group, 'name'):
                        selected_group_name = selected_group.name
                    elif hasattr(selected_group, 'get_name'):
                        selected_group_name = selected_group.get_name()
                        
                    # Get name of the current group item
                    current_group = group_data
                    current_group_name = None
                    
                    if isinstance(current_group, dict) and 'name' in current_group:
                        current_group_name = current_group['name']
                    elif hasattr(current_group, 'name'):
                        current_group_name = current_group.name
                    elif hasattr(current_group, 'get_name'):
                        current_group_name = current_group.get_name()
                        
                    # Compare names
                    if selected_group_name and current_group_name and selected_group_name == current_group_name:
                        self.group_list.setCurrentItem(item)
                        break
        except Exception as e:
            logger.error(f"Error loading device groups: {e}")
            logger.exception("Exception details:")
    
    def _load_subnets(self):
        """Load subnets into the list"""
        self.subnet_list.clear()
        
        # Get all devices and group by subnet
        if self.plugin.device_manager:
            try:
                all_devices = self.plugin.device_manager.get_devices()
                subnets = {}
                
                # Group devices by subnet
                for device in all_devices:
                    ip = device.get_property("ip_address", "")
                    if ip:
                        # Extract subnet (first three octets)
                        parts = ip.split('.')
                        if len(parts) == 4:
                            subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                            if subnet not in subnets:
                                subnets[subnet] = []
                            subnets[subnet].append(device)
                
                # Add subnets to the list
                for subnet, devices in subnets.items():
                    item = QListWidgetItem(f"{subnet} ({len(devices)} devices)")
                    item.setData(Qt.UserRole, {'subnet': subnet, 'devices': devices})
                    
                    # Check if credentials exist for this subnet
                    has_creds = bool(self.plugin.credential_store.get_subnet_credentials(subnet))
                    
                    # Set font weight based on credential status
                    font = item.font()
                    font.setBold(has_creds)
                    item.setFont(font)
                    
                    # Add to list
                    self.subnet_list.addItem(item)
                
                # Select the first subnet if any are available and no specific ones were provided
                if self.subnet_list.count() > 0 and not self.selected_subnets:
                    self.subnet_list.setCurrentRow(0)
                
                # If specific subnets were provided, select the first one
                if self.selected_subnets:
                    # Find and select the item
                    for i in range(self.subnet_list.count()):
                        item = self.subnet_list.item(i)
                        subnet_data = item.data(Qt.UserRole)
                        if subnet_data['subnet'] == self.selected_subnets[0]['subnet']:
                            self.subnet_list.setCurrentItem(item)
                            break
            except Exception as e:
                logger.error(f"Error loading subnets: {e}")
        
    def _on_device_selected(self, current, previous):
        """Handle device selection"""
        if not current:
            self.device_save_btn.setEnabled(False)
            self.device_delete_btn.setEnabled(False)
            return
            
        # Get device object and extract ID
        device = current.data(Qt.UserRole)
        if hasattr(device, 'id'):
            device_id = device.id
        else:
            # Fallback: assume it's already a device ID string
            device_id = device
            
        # Get device-specific credentials only (not fallback to group/subnet)
        # This ensures we only show/edit device-specific credentials in the device tab
        credentials = self.plugin.credential_store.get_device_credentials(device_id)
        
        # Fill form
        if credentials:
            # Set connection type
            conn_type = credentials.get("connection_type", "ssh").upper()
            index = self.device_conn_type.findText(conn_type)
            if index >= 0:
                self.device_conn_type.setCurrentIndex(index)
                
            # Set username
            self.device_username.setText(credentials.get("username", ""))
            
            # Set password
            self.device_password.setText(credentials.get("password", ""))
            
            # Set enable password
            self.device_enable.setText(credentials.get("enable_password", ""))
            
            # Enable delete button
            self.device_delete_btn.setEnabled(True)
        else:
            # Clear form
            self.device_conn_type.setCurrentIndex(0)
            self.device_username.clear()
            self.device_password.clear()
            self.device_enable.clear()
            
            # Disable delete button
            self.device_delete_btn.setEnabled(False)
            
        # Enable save button
        self.device_save_btn.setEnabled(True)
        
    def _on_group_selected(self, current, previous):
        """Handle group selection"""
        if not current:
            self.group_save_btn.setEnabled(False)
            self.group_delete_btn.setEnabled(False)
            return
            
        # Get group object
        group = current.data(Qt.UserRole)
        
        # Extract group name based on structure
        group_name = None
        if isinstance(group, dict) and 'name' in group:
            group_name = group['name']
        elif hasattr(group, 'name'):
            group_name = group.name
        elif hasattr(group, 'get_name'):
            group_name = group.get_name()
        else:
            group_name = str(group)
            
        logger.debug(f"Getting credentials for group: {group_name}")
        
        # Get credentials
        group_credentials = self.plugin.get_all_group_credentials()
        credentials = group_credentials.get(group_name, {})
        
        # Fill form
        if credentials:
            # Set connection type
            conn_type = credentials.get("connection_type", "ssh").upper()
            index = self.group_conn_type.findText(conn_type)
            if index >= 0:
                self.group_conn_type.setCurrentIndex(index)
                
            # Set username
            self.group_username.setText(credentials.get("username", ""))
            
            # Set password
            self.group_password.setText(credentials.get("password", ""))
            
            # Set enable password
            self.group_enable.setText(credentials.get("enable_password", ""))
            
            # Enable delete button
            self.group_delete_btn.setEnabled(True)
        else:
            # Clear form
            self.group_conn_type.setCurrentIndex(0)
            self.group_username.clear()
            self.group_password.clear()
            self.group_enable.clear()
            
            # Disable delete button
            self.group_delete_btn.setEnabled(False)
            
        # Enable save button
        self.group_save_btn.setEnabled(True)
        
    def _on_subnet_selected(self, current, previous):
        """Handle subnet selection"""
        if not current:
            self.subnet_save_btn.setEnabled(False)
            self.subnet_delete_btn.setEnabled(False)
            return
            
        # Get subnet
        subnet_data = current.data(Qt.UserRole)
        subnet = subnet_data['subnet'] if isinstance(subnet_data, dict) and 'subnet' in subnet_data else subnet_data
        
        # Get credentials
        subnet_credentials = self.plugin.get_all_subnet_credentials()
        credentials = subnet_credentials.get(subnet, {})
        
        # Fill form
        if credentials:
            # Set connection type
            conn_type = credentials.get("connection_type", "ssh").upper()
            index = self.subnet_conn_type.findText(conn_type)
            if index >= 0:
                self.subnet_conn_type.setCurrentIndex(index)
                
            # Set username
            self.subnet_username.setText(credentials.get("username", ""))
            
            # Set password
            self.subnet_password.setText(credentials.get("password", ""))
            
            # Set enable password
            self.subnet_enable.setText(credentials.get("enable_password", ""))
            
            # Enable delete button
            self.subnet_delete_btn.setEnabled(True)
        else:
            # Clear form
            self.subnet_conn_type.setCurrentIndex(0)
            self.subnet_username.clear()
            self.subnet_password.clear()
            self.subnet_enable.clear()
            
            # Disable delete button
            self.subnet_delete_btn.setEnabled(False)
            
        # Enable save button
        self.subnet_save_btn.setEnabled(True)
        
    def _on_save_device(self):
        """Handle save device button"""
        # Get selected device
        current = self.device_list.currentItem()
        if not current:
            return
            
        # Get device object and extract ID
        device = current.data(Qt.UserRole)
        if hasattr(device, 'id'):
            device_id = device.id
        else:
            # Fallback: assume it's already a device ID string
            device_id = device
        
        # Validate form
        username = self.device_username.text().strip()
        if not username:
            QMessageBox.warning(
                self,
                "Missing Username",
                "Please enter a username."
            )
            return
            
        # Create credentials
        credentials = {
            "connection_type": self.device_conn_type.currentText().lower(),
            "username": username,
            "password": self.device_password.text(),
            "enable_password": self.device_enable.text()
        }
        
        # Save credentials
        result = self.plugin.set_device_credentials(device_id, credentials)
        if not result:
            logger.warning(f"Failed to save credentials for device {device_id}")
            QMessageBox.warning(
                self,
                "Save Failed",
                "Failed to save credentials. Please check the console for details."
            )
            return
        
        # Refresh the device list to show updated credential status
        self._load_devices()
        
        # Re-select the device that was just saved
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            item_device = item.data(Qt.UserRole)
            if hasattr(item_device, 'id') and item_device.id == device_id:
                self.device_list.setCurrentItem(item)
                break
        
        # Show success message
        device_alias = device.get_property("alias", device.get_property("hostname", "Device"))
        QMessageBox.information(
            self,
            "Credentials Saved",
            f"Credentials for {device_alias} saved successfully."
        )
        
    def _on_delete_device(self):
        """Handle delete device button"""
        # Get selected device
        current = self.device_list.currentItem()
        if not current:
            return
            
        # Get device object and extract ID
        device = current.data(Qt.UserRole)
        if hasattr(device, 'id'):
            device_id = device.id
        else:
            # Fallback: assume it's already a device ID string
            device_id = device
        
        # Confirm deletion
        result = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete these credentials?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # Delete credentials
        self.plugin.delete_device_credentials(device_id)
        
        # Refresh UI
        self._on_device_selected(current, None)
        
    def _on_save_group(self):
        """Handle save group button"""
        # Get selected group
        current = self.group_list.currentItem()
        if not current:
            return
            
        # Get group object and extract name
        group = current.data(Qt.UserRole)
        
        # Extract group name based on structure
        group_name = None
        if isinstance(group, dict) and 'name' in group:
            group_name = group['name']
        elif hasattr(group, 'name'):
            group_name = group.name
        elif hasattr(group, 'get_name'):
            group_name = group.get_name()
        else:
            group_name = str(group)
        
        # Validate form
        username = self.group_username.text().strip()
        if not username:
            QMessageBox.warning(
                self,
                "Missing Username",
                "Please enter a username."
            )
            return
            
        # Create credentials
        credentials = {
            "connection_type": self.group_conn_type.currentText().lower(),
            "username": username,
            "password": self.group_password.text(),
            "enable_password": self.group_enable.text()
        }
        
        # Save credentials
        self.plugin.set_group_credentials(group_name, credentials)
        
        # Show success message
        QMessageBox.information(
            self,
            "Credentials Saved",
            f"Credentials for group saved successfully."
        )
        
    def _on_delete_group(self):
        """Handle delete group button"""
        # Get selected group
        current = self.group_list.currentItem()
        if not current:
            return
            
        # Get group object and extract name
        group = current.data(Qt.UserRole)
        
        # Extract group name based on structure
        group_name = None
        if isinstance(group, dict) and 'name' in group:
            group_name = group['name']
        elif hasattr(group, 'name'):
            group_name = group.name
        elif hasattr(group, 'get_name'):
            group_name = group.get_name()
        else:
            group_name = str(group)
        
        # Confirm deletion
        result = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete these credentials?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # Delete credentials
        self.plugin.delete_group_credentials(group_name)
        
        # Refresh UI
        self._on_group_selected(current, None)
        
    def _on_add_subnet(self):
        """Handle add subnet button"""
        # Get subnet
        subnet = self.new_subnet.text().strip()
        
        # Validate subnet
        if not subnet:
            QMessageBox.warning(
                self,
                "Missing Subnet",
                "Please enter a subnet."
            )
            return
            
        try:
            # Validate subnet format
            subnet_obj = ipaddress.ip_network(subnet, strict=False)
            subnet = str(subnet_obj)
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Subnet",
                "Please enter a valid subnet in CIDR notation (e.g. 192.168.1.0/24)."
            )
            return
            
        # Check if subnet already exists
        for i in range(self.subnet_list.count()):
            if self.subnet_list.item(i).data(Qt.UserRole) == subnet:
                # Select existing subnet
                self.subnet_list.setCurrentRow(i)
                return
                
        # Add subnet to list
        item = QListWidgetItem(subnet)
        item.setData(Qt.UserRole, subnet)
        self.subnet_list.addItem(item)
        
        # Select new subnet
        self.subnet_list.setCurrentItem(item)
        
        # Clear input field
        self.new_subnet.clear()
        
    def _on_save_subnet(self):
        """Handle save subnet button"""
        # Get selected subnet
        current = self.subnet_list.currentItem()
        if not current:
            return
            
        # Get subnet
        subnet_data = current.data(Qt.UserRole)
        subnet = subnet_data['subnet'] if isinstance(subnet_data, dict) and 'subnet' in subnet_data else subnet_data
        
        # Validate form
        username = self.subnet_username.text().strip()
        if not username:
            QMessageBox.warning(
                self,
                "Missing Username",
                "Please enter a username."
            )
            return
            
        # Create credentials
        credentials = {
            "connection_type": self.subnet_conn_type.currentText().lower(),
            "username": username,
            "password": self.subnet_password.text(),
            "enable_password": self.subnet_enable.text()
        }
        
        # Save credentials
        self.plugin.set_subnet_credentials(subnet, credentials)
        
        # Show success message
        QMessageBox.information(
            self,
            "Credentials Saved",
            f"Credentials for subnet saved successfully."
        )
        
    def _on_delete_subnet(self):
        """Handle delete subnet button"""
        # Get selected subnet
        current = self.subnet_list.currentItem()
        if not current:
            return
            
        # Get subnet
        subnet_data = current.data(Qt.UserRole)
        subnet = subnet_data['subnet'] if isinstance(subnet_data, dict) and 'subnet' in subnet_data else subnet_data
        
        # Confirm deletion
        result = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete these credentials?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # Delete credentials
        self.plugin.delete_subnet_credentials(subnet)
        
        # Remove from list
        row = self.subnet_list.currentRow()
        self.subnet_list.takeItem(row)
        
        # Clear form
        self.subnet_conn_type.setCurrentIndex(0)
        self.subnet_username.clear()
        self.subnet_password.clear()
        self.subnet_enable.clear()
        
        # Disable buttons
        self.subnet_save_btn.setEnabled(False)
        self.subnet_delete_btn.setEnabled(False) 