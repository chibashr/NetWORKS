#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Scan dialog for the Network Scanner plugin.
Shows Basic/Advanced/Scan Profiles tabs and returns scan target data.
"""

import ipaddress
from loguru import logger

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QGroupBox,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QCheckBox,
    QInputDialog,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator

from src.ui.plugin_widgets import PluginDialogBase
from src.ui.plugin_ui_theme import mark_plugin_ui


def show_scan_dialog(plugin, selected_devices=None):
    """Show the scan configuration dialog. Returns dict/str/None as accepted result."""
    if selected_devices and not isinstance(selected_devices, list):
        selected_devices = [selected_devices]

    dialog = PluginDialogBase("Network Scan", plugin.main_window, use_tabs=True)
    dialog.setMinimumWidth(550)
    dialog.setMinimumHeight(450)

    basic_tab = QWidget()
    advanced_tab = QWidget()
    profiles_tab = QWidget()
    dialog.add_tab(basic_tab, "Basic")
    dialog.add_tab(advanced_tab, "Advanced")
    dialog.add_tab(profiles_tab, "Scan Profiles")

    # ==== Basic Tab ====
    basic_layout = QVBoxLayout(basic_tab)
    basic_layout.setContentsMargins(10, 10, 10, 10)
    basic_layout.setSpacing(12)

    target_group = QGroupBox("Scan Target")
    target_layout = QVBoxLayout(target_group)
    target_layout.setContentsMargins(10, 15, 10, 10)
    target_layout.setSpacing(10)

    target_combo = QComboBox()
    target_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    target_combo.setToolTip("Select what to scan")

    selected_devices_list = None
    list_container = None
    add_device_button = None
    remove_device_button = None
    if selected_devices:
        target_combo.addItem(f"Selected Devices ({len(selected_devices)})", "devices")
        list_container = QGroupBox("Devices to Scan")
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(10, 10, 10, 10)
        list_layout.setSpacing(6)
        selected_devices_list = QListWidget()
        for device in selected_devices:
            ip_address = device.get_property("ip_address", "") if hasattr(device, "get_property") else ""
            alias = device.get_property("alias", "") if hasattr(device, "get_property") else ""
            label = f"{alias} ({ip_address})" if alias and ip_address else (ip_address or alias or "Device")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, {"device": device, "ip": ip_address, "label": label})
            selected_devices_list.addItem(item)
        list_layout.addWidget(selected_devices_list)
        list_button_layout = QHBoxLayout()
        add_device_button = QPushButton("Add by IP...")
        remove_device_button = QPushButton("Remove Selected")
        list_button_layout.addWidget(add_device_button)
        list_button_layout.addWidget(remove_device_button)
        list_layout.addLayout(list_button_layout)
        target_layout.addWidget(list_container)

    group_combo = None
    available_groups = [g for g in plugin.device_manager.get_groups() if g != plugin.device_manager.root_group]
    if available_groups:
        target_combo.addItem("Group Devices", "group")
        group_combo = QComboBox()
        group_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        group_combo.setToolTip("Select a group to scan")
        available_groups.sort(key=lambda g: plugin._format_group_path(g).lower())
        for group in available_groups:
            group_combo.addItem(plugin._format_group_path(group), group)
        target_layout.addWidget(group_combo)

    target_combo.addItem("Interface Subnet", "interface")
    target_combo.addItem("Custom Network Range", "custom")

    target_row = QHBoxLayout()
    target_row.addWidget(QLabel("Target:"))
    target_row.addWidget(target_combo, 1)
    target_layout.insertLayout(0, target_row)

    interface_container = QWidget()
    interface_row = QHBoxLayout(interface_container)
    interface_row.setContentsMargins(0, 0, 0, 0)
    interface_row.setSpacing(8)
    interface_row.addWidget(QLabel("Interface:"))
    interface_combo = QComboBox()
    interface_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    if not plugin.settings["preferred_interface"]["choices"]:
        plugin._update_interface_choices()
    interface_combo.addItems(plugin.settings["preferred_interface"]["choices"])
    current_interface = plugin.settings["preferred_interface"]["value"]
    if current_interface and current_interface in plugin.settings["preferred_interface"]["choices"]:
        interface_combo.setCurrentText(current_interface)
    refresh_interfaces_btn = QPushButton("Refresh")
    refresh_interfaces_btn.setToolTip("Refresh network interface list")
    interface_row.addWidget(interface_combo, 1)
    interface_row.addWidget(refresh_interfaces_btn)
    target_layout.addWidget(interface_container)

    custom_range_container = QWidget()
    custom_range_layout = QHBoxLayout(custom_range_container)
    custom_range_layout.setContentsMargins(0, 0, 0, 0)
    custom_range_layout.setSpacing(8)
    network_range_edit = QLineEdit()
    network_range_edit.setPlaceholderText("e.g., 192.168.1.0/24 or 10.0.0.1-10.0.0.254")
    custom_range_layout.addWidget(network_range_edit)
    target_layout.addWidget(custom_range_container)

    if not selected_devices:
        target_combo.setCurrentIndex(target_combo.findData("interface"))
    else:
        target_combo.setCurrentIndex(0)

    def update_ui_state():
        t = target_combo.currentData() if target_combo.currentData() is not None else "interface"
        network_range_edit.setEnabled(t == "custom")
        custom_range_container.setVisible(t == "custom")
        if list_container and selected_devices_list:
            list_container.setVisible(t == "devices")
        if group_combo:
            group_combo.setVisible(t == "group")
        interface_container.setVisible(t == "interface")

    def refresh_interfaces_in_dialog():
        plugin._update_interface_choices()
        interface_combo.clear()
        interface_combo.addItems(plugin.settings["preferred_interface"]["choices"])
        if plugin.settings["preferred_interface"]["value"] in plugin.settings["preferred_interface"]["choices"]:
            interface_combo.setCurrentText(plugin.settings["preferred_interface"]["value"])

    refresh_interfaces_btn.clicked.connect(refresh_interfaces_in_dialog)
    target_combo.currentIndexChanged.connect(update_ui_state)

    if selected_devices_list is not None and add_device_button is not None and remove_device_button is not None:
        def add_device_by_ip():
            ip, ok = QInputDialog.getText(dialog, "Add Device by IP", "Enter IP address or range:")
            if not ok or not ip.strip():
                return
            ip = ip.strip()
            label = ip
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, {"device": None, "ip": ip, "label": label})
            selected_devices_list.addItem(item)
            idx = target_combo.findData("devices")
            if idx >= 0:
                target_combo.setItemText(idx, f"Selected Devices ({selected_devices_list.count()})")

        def remove_selected_devices():
            for item in selected_devices_list.selectedItems():
                selected_devices_list.takeItem(selected_devices_list.row(item))
            idx = target_combo.findData("devices")
            if idx >= 0:
                target_combo.setItemText(idx, f"Selected Devices ({selected_devices_list.count()})")

        add_device_button.clicked.connect(add_device_by_ip)
        remove_device_button.clicked.connect(remove_selected_devices)

    update_ui_state()
    basic_layout.addWidget(target_group)

    profile_group = QGroupBox("Scan Profile")
    profile_layout = QVBoxLayout(profile_group)
    profile_layout.setContentsMargins(10, 15, 10, 10)
    profile_layout.setSpacing(8)
    scan_type_layout = QHBoxLayout()
    scan_type_layout.addWidget(QLabel("Scan Type:"))
    scan_type_combo = QComboBox()
    scan_type_combo.addItems(plugin.settings["scan_type"]["choices"])
    scan_type_combo.setCurrentText(plugin.settings["scan_type"]["value"])
    scan_type_layout.addWidget(scan_type_combo, 1)
    profile_layout.addLayout(scan_type_layout)

    scan_description_label = QLabel()
    scan_description_label.setWordWrap(True)
    scan_description_label.setMinimumHeight(60)
    mark_plugin_ui(scan_description_label)

    def update_scan_description(index):
        scan_type = scan_type_combo.currentText()
        profiles = plugin.settings["scan_profiles"]["value"]
        if scan_type in profiles:
            scan_description_label.setText(profiles[scan_type].get("description", ""))

    scan_type_combo.currentIndexChanged.connect(update_scan_description)
    update_scan_description(0)
    profile_layout.addWidget(scan_description_label)
    basic_layout.addWidget(profile_group)
    basic_layout.addStretch(1)

    # ==== Advanced Tab ====
    advanced_layout = QVBoxLayout(advanced_tab)
    advanced_layout.setContentsMargins(10, 10, 10, 10)
    advanced_layout.setSpacing(12)
    options_group = QGroupBox("Scan Options")
    options_layout = QFormLayout(options_group)
    options_layout.setContentsMargins(10, 15, 10, 10)
    options_layout.setSpacing(10)
    options_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
    elevated_check = QCheckBox()
    elevated_check.setChecked(plugin.settings["use_sudo"]["value"])
    options_layout.addRow("Use Elevated Permissions:", elevated_check)
    timeout_edit = QLineEdit(str(plugin.settings["scan_timeout"]["value"]))
    timeout_edit.setValidator(QIntValidator(10, 1000))
    options_layout.addRow("Timeout (seconds):", timeout_edit)
    custom_args_edit = QLineEdit(plugin.settings["custom_scan_args"]["value"])
    custom_args_edit.setPlaceholderText("e.g., -p 80,443 -sV")
    options_layout.addRow("Custom nmap arguments:", custom_args_edit)
    advanced_layout.addWidget(options_group)
    advanced_layout.addStretch(1)

    # ==== Profiles Tab ====
    profiles_layout = QVBoxLayout(profiles_tab)
    profiles_layout.setContentsMargins(10, 10, 10, 10)
    profiles_layout.setSpacing(12)
    profiles_label = QLabel("Profile Editor")
    profiles_label.setStyleSheet("font-weight: bold; font-size: 13px;")
    profiles_layout.addWidget(profiles_label)
    profile_select_layout = QHBoxLayout()
    profile_select_layout.addWidget(QLabel("Profile:"))
    profile_select_combo = QComboBox()
    profile_keys = list(plugin.settings["scan_profiles"]["value"].keys())
    profile_select_combo.addItems(profile_keys)
    profile_select_layout.addWidget(profile_select_combo, 1)
    profiles_layout.addLayout(profile_select_layout)

    profile_description_display = QLabel()
    profile_description_display.setWordWrap(True)
    profile_description_display.setMinimumHeight(50)
    mark_plugin_ui(profile_description_display)
    profiles_layout.addWidget(profile_description_display)

    editor_group = QGroupBox("Edit Profile")
    editor_layout = QFormLayout(editor_group)
    editor_layout.setContentsMargins(10, 15, 10, 10)
    editor_layout.setSpacing(10)
    profile_name_edit = QLineEdit()
    editor_layout.addRow("Name:", profile_name_edit)
    profile_description_edit = QTextEdit()
    profile_description_edit.setFixedHeight(80)
    editor_layout.addRow("Description:", profile_description_edit)
    profile_arguments_edit = QLineEdit()
    editor_layout.addRow("Arguments:", profile_arguments_edit)
    profile_timeout_edit = QLineEdit()
    profile_timeout_edit.setValidator(QIntValidator(10, 2000))
    editor_layout.addRow("Timeout (seconds):", profile_timeout_edit)
    profiles_layout.addWidget(editor_group)

    profile_button_layout = QHBoxLayout()
    profile_save_button = QPushButton("Save Profile")
    profile_delete_button = QPushButton("Delete Profile")
    profile_button_layout.addWidget(profile_save_button)
    profile_button_layout.addWidget(profile_delete_button)
    profiles_layout.addLayout(profile_button_layout)
    profiles_layout.addStretch(1)

    profiles = plugin.settings["scan_profiles"]["value"]

    def refresh_profile_choices(preferred_key=None):
        keys = list(plugin.settings["scan_profiles"]["value"].keys())
        if not keys:
            return
        current_scan_key = scan_type_combo.currentText()
        current_profile_key = profile_select_combo.currentText()
        scan_type_combo.blockSignals(True)
        scan_type_combo.clear()
        scan_type_combo.addItems(keys)
        if preferred_key and preferred_key in keys:
            scan_type_combo.setCurrentText(preferred_key)
        elif current_scan_key in keys:
            scan_type_combo.setCurrentText(current_scan_key)
        else:
            scan_type_combo.setCurrentText(keys[0])
        scan_type_combo.blockSignals(False)
        profile_select_combo.blockSignals(True)
        profile_select_combo.clear()
        profile_select_combo.addItems(keys)
        if preferred_key and preferred_key in keys:
            profile_select_combo.setCurrentText(preferred_key)
        elif current_profile_key in keys:
            profile_select_combo.setCurrentText(current_profile_key)
        else:
            profile_select_combo.setCurrentText(keys[0])
        profile_select_combo.blockSignals(False)
        plugin.settings["scan_type"]["choices"] = keys

    def load_profile(profile_key):
        profile = profiles.get(profile_key, {})
        profile_name_edit.setText(profile.get("name", profile_key))
        profile_description_edit.setPlainText(profile.get("description", ""))
        profile_arguments_edit.setText(profile.get("arguments", ""))
        profile_timeout_edit.setText(str(profile.get("timeout", 300)))
        profile_description_display.setText(profile.get("description", ""))

    def save_profile():
        profile_key = profile_select_combo.currentText().strip()
        if not profile_key:
            return
        profiles[profile_key] = {
            "name": profile_name_edit.text().strip() or profile_key,
            "description": profile_description_edit.toPlainText().strip(),
            "arguments": profile_arguments_edit.text().strip(),
            "timeout": int(profile_timeout_edit.text() or 300),
        }
        plugin.settings["scan_profiles"]["value"] = profiles
        refresh_profile_choices(preferred_key=profile_key)
        load_profile(profile_key)
        if scan_type_combo.currentText() == profile_key:
            update_scan_description(0)

    def delete_profile():
        profile_key = profile_select_combo.currentText().strip()
        if not profile_key or profile_key not in profiles:
            return
        if len(profiles) <= 1:
            QMessageBox.warning(
                plugin.main_window,
                "Cannot Delete Profile",
                "At least one scan profile must remain.",
            )
            return
        if QMessageBox.question(
            plugin.main_window,
            "Delete Profile",
            f"Delete the scan profile '{profile_key}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        del profiles[profile_key]
        plugin.settings["scan_profiles"]["value"] = profiles
        refresh_profile_choices()
        load_profile(profile_select_combo.currentText())
        update_scan_description(0)

    def on_profile_selection_changed(index):
        profile_key = profile_select_combo.currentText()
        if profile_key:
            load_profile(profile_key)
            if profile_key in plugin.settings["scan_type"]["choices"]:
                scan_type_combo.setCurrentText(profile_key)
                update_scan_description(0)

    def sync_profile_from_scan_type(index):
        profile_key = scan_type_combo.currentText()
        if profile_key in plugin.settings["scan_profiles"]["value"]:
            profile_select_combo.setCurrentText(profile_key)
            load_profile(profile_key)
            profile_description_display.setText(
                plugin.settings["scan_profiles"]["value"][profile_key].get("description", "")
            )

    profile_select_combo.currentIndexChanged.connect(on_profile_selection_changed)
    scan_type_combo.currentIndexChanged.connect(sync_profile_from_scan_type)
    profile_save_button.clicked.connect(save_profile)
    profile_delete_button.clicked.connect(delete_profile)

    if scan_type_combo.currentText() in profile_keys:
        profile_select_combo.setCurrentText(scan_type_combo.currentText())
    elif profile_keys:
        profile_select_combo.setCurrentText(profile_keys[0])
    load_profile(profile_select_combo.currentText())
    sync_profile_from_scan_type(0)

    try:
        if current_interface and current_interface != "Any (default)":
            selected_if = current_interface.split(":")[0].strip()
            subnet = plugin._get_interface_subnet(selected_if)
            if subnet:
                network_range_edit.setText(subnet)
                logger.debug(f"Using subnet {subnet} from interface {selected_if}")
        if not network_range_edit.text():
            import socket
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            network = ipaddress.IPv4Network(f"{ip_address}/24", strict=False)
            network_range_edit.setText(str(network))
            logger.debug(f"Using subnet {network} from local IP {ip_address}")
    except Exception as e:
        logger.debug(f"Error determining default network range: {e}")

    def update_network_range(index):
        if target_combo.currentData() == "interface":
            selected_if_text = interface_combo.currentText()
            if selected_if_text and selected_if_text != "Any (default)":
                subnet = plugin._get_interface_subnet(selected_if_text)
                if subnet:
                    network_range_edit.setText(subnet)

    interface_combo.currentIndexChanged.connect(update_network_range)

    dialog.add_action_button("Cancel", dialog.reject)
    dialog.add_action_button("Scan", dialog.accept)

    if dialog.exec() == QDialog.Accepted:
        selected_scan_type = scan_type_combo.currentText()
        profiles_val = plugin.settings["scan_profiles"]["value"]
        plugin.settings["scan_type"]["value"] = selected_scan_type
        if selected_scan_type in profiles_val:
            profile = profiles_val[selected_scan_type]
            plugin.settings["use_sudo"]["value"] = elevated_check.isChecked()
            plugin.settings["scan_timeout"]["value"] = int(timeout_edit.text())
            custom_args = custom_args_edit.text().strip()
            plugin.settings["custom_scan_args"]["value"] = custom_args if custom_args else profile.get("arguments", "")
        else:
            plugin.settings["use_sudo"]["value"] = elevated_check.isChecked()
            plugin.settings["scan_timeout"]["value"] = int(timeout_edit.text())
            plugin.settings["custom_scan_args"]["value"] = custom_args_edit.text()
        plugin.settings["preferred_interface"]["value"] = interface_combo.currentText()

        t = target_combo.currentData() if target_combo.currentData() is not None else "interface"
        if t == "devices" and selected_devices_list:
            selected_targets = []
            for index in range(selected_devices_list.count()):
                item = selected_devices_list.item(index)
                data = item.data(Qt.UserRole) or {}
                if not data.get("ip") and data.get("device") is None:
                    continue
                selected_targets.append(data)
            return {"target_type": "devices", "selected_devices": selected_targets}
        if t == "group" and group_combo:
            return {"target_type": "group", "group": group_combo.currentData()}
        if t == "interface":
            selected_if_text = interface_combo.currentText()
            if selected_if_text and selected_if_text != "Any (default)":
                subnet = plugin._get_interface_subnet(selected_if_text)
                if subnet:
                    return {"target_type": "interface", "interface": selected_if_text, "network_range": subnet}
            return {"target_type": "interface", "interface": interface_combo.currentText(), "network_range": network_range_edit.text().strip()}
        return network_range_edit.text().strip()

    return None
