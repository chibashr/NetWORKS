#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Target selection tabs (Devices/Groups/Subnets) for the Command Dialog.
Builds tab widgets and provides refresh logic.
"""

import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)


def safe_str(value, default=""):
    """Safely convert a value to string, handling None, NaN, and other edge cases."""
    if value is None:
        return default
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return default
    try:
        result = str(value).strip()
        return result if result else default
    except (ValueError, OverflowError):
        return default


def build_target_tabs(parent):
    """Build Devices/Groups/Subnets tab widget and tables.

    Returns:
        tuple: (target_tabs, device_table, group_table, subnet_table)
    """
    target_tabs = QTabWidget()

    device_tab = QWidget()
    device_tab_layout = QVBoxLayout(device_tab)
    device_tab_layout.setContentsMargins(5, 5, 5, 5)
    device_label = QLabel("Devices:")
    device_table = QTableWidget()
    device_table.setColumnCount(2)
    device_table.setHorizontalHeaderLabels(["Device", "IP Address"])
    device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    device_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    device_table.setSelectionBehavior(QTableWidget.SelectRows)
    device_table.setSelectionMode(QTableWidget.MultiSelection)
    device_tab_layout.addWidget(device_label)
    device_tab_layout.addWidget(device_table)

    group_tab = QWidget()
    group_tab_layout = QVBoxLayout(group_tab)
    group_tab_layout.setContentsMargins(5, 5, 5, 5)
    group_label = QLabel("Device Groups:")
    group_table = QTableWidget()
    group_table.setColumnCount(2)
    group_table.setHorizontalHeaderLabels(["Group Name", "Device Count"])
    group_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    group_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    group_table.setSelectionBehavior(QTableWidget.SelectRows)
    group_table.setSelectionMode(QTableWidget.MultiSelection)
    group_tab_layout.addWidget(group_label)
    group_tab_layout.addWidget(group_table)

    subnet_tab = QWidget()
    subnet_tab_layout = QVBoxLayout(subnet_tab)
    subnet_tab_layout.setContentsMargins(5, 5, 5, 5)
    subnet_label = QLabel("Subnets:")
    subnet_table = QTableWidget()
    subnet_table.setColumnCount(2)
    subnet_table.setHorizontalHeaderLabels(["Subnet", "Device Count"])
    subnet_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    subnet_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    subnet_table.setSelectionBehavior(QTableWidget.SelectRows)
    subnet_table.setSelectionMode(QTableWidget.MultiSelection)
    subnet_tab_layout.addWidget(subnet_label)
    subnet_tab_layout.addWidget(subnet_table)

    target_tabs.addTab(device_tab, "Devices")
    target_tabs.addTab(group_tab, "Groups")
    target_tabs.addTab(subnet_tab, "Subnets")

    return target_tabs, device_table, group_table, subnet_table


def refresh_target_tables(dialog):
    """Populate device_table, group_table, subnet_table from dialog.plugin."""
    from loguru import logger

    logger.debug("Refreshing device list")
    dialog.device_table.setRowCount(0)
    dialog.group_table.setRowCount(0)
    dialog.subnet_table.setRowCount(0)

    if not dialog.plugin.device_manager:
        logger.error("Device manager not available")
        return

    devices = dialog.plugin.device_manager.get_devices()
    dialog.device_table.setRowCount(len(devices))
    for i, device in enumerate(devices):
        alias = device.get_property("alias", "")
        hostname = device.get_property("hostname", "")
        name = safe_str(alias) or safe_str(hostname) or "Unknown Device"
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.UserRole, device)
        dialog.device_table.setItem(i, 0, name_item)
        ip = device.get_property("ip_address", "")
        ip_item = QTableWidgetItem(safe_str(ip))
        dialog.device_table.setItem(i, 1, ip_item)

    try:
        device_groups = dialog.plugin.device_manager.get_groups()
        logger.debug(f"Retrieved {len(device_groups)} device groups")
        if device_groups:
            dialog.group_table.setRowCount(len(device_groups))
            for i, group in enumerate(device_groups):
                try:
                    group_name = None
                    device_count = 0
                    if isinstance(group, dict) and "name" in group:
                        group_name = group["name"]
                    elif hasattr(group, "name"):
                        group_name = group.name
                    elif hasattr(group, "get_name"):
                        group_name = group.get_name()
                    else:
                        group_name = safe_str(group, "Unknown Group")
                        logger.warning(f"Group missing name attribute, using {group_name}")
                    if isinstance(group, dict) and "devices" in group:
                        device_count = len(group["devices"])
                    elif hasattr(group, "devices"):
                        device_count = len(group.devices)
                    elif hasattr(group, "get_devices"):
                        device_count = len(group.get_devices())
                    elif hasattr(group, "device_count"):
                        device_count = group.device_count
                    elif hasattr(group, "get_device_count"):
                        device_count = group.get_device_count()
                    else:
                        logger.warning(f"Could not determine device count for group {group_name}")
                    name_item = QTableWidgetItem(safe_str(group_name, "Unknown Group"))
                    name_item.setData(Qt.UserRole, group)
                    dialog.group_table.setItem(i, 0, name_item)
                    dialog.group_table.setItem(i, 1, QTableWidgetItem(str(device_count)))
                except Exception as e:
                    logger.error(f"Error processing group at index {i}: {e}")
        else:
            logger.debug("No device groups found")
    except Exception as e:
        logger.error(f"Error getting device groups: {e}")
        logger.exception("Exception details:")

    try:
        subnets = {}
        for device in devices:
            ip = device.get_property("ip_address", "")
            ip_str = safe_str(ip)
            if ip_str:
                parts = ip_str.split(".")
                if len(parts) == 4:
                    try:
                        int(parts[0])
                        int(parts[1])
                        int(parts[2])
                        subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                        if subnet not in subnets:
                            subnets[subnet] = []
                        subnets[subnet].append(device)
                    except (ValueError, IndexError):
                        continue
        dialog.subnet_table.setRowCount(len(subnets))
        for i, (subnet, subnet_devices) in enumerate(subnets.items()):
            subnet_item = QTableWidgetItem(subnet)
            subnet_item.setData(Qt.UserRole, {"subnet": subnet, "devices": subnet_devices})
            dialog.subnet_table.setItem(i, 0, subnet_item)
            dialog.subnet_table.setItem(i, 1, QTableWidgetItem(str(len(subnet_devices))))
    except Exception as e:
        logger.error(f"Error grouping devices by subnet: {e}")


def get_selected_devices_from_dialog(dialog):
    """Return the list of selected devices from the dialog's target tab (Devices/Groups/Subnets)."""
    current_tab = dialog.target_tabs.currentWidget()
    selected_devices = []
    if current_tab == dialog.target_tabs.widget(0):
        for item in dialog.device_table.selectedItems():
            row = item.row()
            device_item = dialog.device_table.item(row, 0)
            if device_item and device_item.data(Qt.UserRole) not in selected_devices:
                selected_devices.append(device_item.data(Qt.UserRole))
    elif current_tab == dialog.target_tabs.widget(1):
        for item in dialog.group_table.selectedItems():
            row = item.row()
            group_item = dialog.group_table.item(row, 0)
            if group_item:
                group = group_item.data(Qt.UserRole)
                if group:
                    try:
                        group_devices = (
                            group.get_all_devices()
                            if hasattr(group, "get_all_devices")
                            else getattr(group, "devices", [])
                        )
                        for device in group_devices:
                            if device not in selected_devices:
                                selected_devices.append(device)
                    except Exception as e:
                        from loguru import logger
                        logger.error(f"Error extracting devices from group: {e}")
    elif current_tab == dialog.target_tabs.widget(2):
        for item in dialog.subnet_table.selectedItems():
            row = item.row()
            subnet_item = dialog.subnet_table.item(row, 0)
            if subnet_item:
                info = subnet_item.data(Qt.UserRole)
                if info and "devices" in info:
                    for device in info["devices"]:
                        if device not in selected_devices:
                            selected_devices.append(device)
    return selected_devices
