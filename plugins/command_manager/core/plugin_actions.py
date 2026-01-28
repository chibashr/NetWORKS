#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin action handlers for Command Manager context menus and toolbar.
Open-dialog logic for devices/groups/subnets; called from the plugin.
"""

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from plugins.command_manager.ui.command_dialog import CommandDialog
from plugins.command_manager.ui.credential_manager import CredentialManager


def on_device_context_run_commands(plugin, devices):
    """Handle run commands context menu item for devices."""
    if not isinstance(devices, list):
        devices = [devices]
    dialog = CommandDialog(plugin, devices, parent=plugin.main_window)
    dialog.exec()


def on_device_context_credentials(plugin, devices):
    """Handle credential manager context menu action for devices."""
    logger.debug(f"Opening credential manager for {len(devices)} devices")
    try:
        dialog = CredentialManager(plugin, devices=devices, parent=plugin.main_window)
        dialog.exec()
    except Exception as e:
        logger.error(f"Error opening credential manager: {e}")
        logger.exception("Exception details:")
        QMessageBox.critical(
            plugin.main_window,
            "Error",
            f"An error occurred while opening the credential manager: {str(e)}",
        )


def on_group_context_run_commands(plugin, groups):
    """Handle run commands on group context menu action."""
    logger.debug(f"Opening command dialog for {len(groups)} device groups")
    try:
        all_devices = []
        for group in groups:
            try:
                if hasattr(group, "get_all_devices"):
                    group_devices = group.get_all_devices()
                elif hasattr(group, "devices"):
                    group_devices = group.devices
                else:
                    logger.warning(f"Unknown group structure, cannot get devices: {group}")
                    continue
                for device in group_devices:
                    if device not in all_devices:
                        all_devices.append(device)
            except Exception as e:
                logger.error(f"Error getting devices from group: {e}")

        if not all_devices:
            logger.warning("No devices found in selected groups")
            QMessageBox.warning(
                plugin.main_window,
                "No Devices",
                "No devices found in the selected groups.",
            )
            return

        logger.debug(f"Found {len(all_devices)} unique devices in selected groups")
        plugin.command_dialog = CommandDialog(
            plugin, devices=all_devices, parent=plugin.main_window
        )
        plugin.command_dialog.show()
    except Exception as e:
        logger.error(f"Error opening command dialog for group: {e}")
        logger.exception("Exception details:")
        QMessageBox.critical(
            plugin.main_window,
            "Error",
            f"An error occurred while opening the command dialog: {str(e)}",
        )


def on_group_context_credentials(plugin, groups):
    """Handle credential manager context menu action for groups."""
    logger.debug(f"Opening credential manager for {len(groups)} device groups")
    try:
        dialog = CredentialManager(plugin, groups=groups, parent=plugin.main_window)
        dialog.exec()
    except Exception as e:
        logger.error(f"Error opening credential manager for groups: {e}")
        logger.exception("Exception details:")
        QMessageBox.critical(
            plugin.main_window,
            "Error",
            f"An error occurred while opening the credential manager: {str(e)}",
        )


def on_subnet_context_run_commands(plugin, subnets):
    """Handle run commands on subnet context menu action."""
    logger.debug(f"Opening command dialog for {len(subnets)} subnets")
    try:
        all_devices = []
        for subnet in subnets:
            if "devices" in subnet:
                for device in subnet["devices"]:
                    if device not in all_devices:
                        all_devices.append(device)

        if not all_devices:
            QMessageBox.warning(
                plugin.main_window,
                "No Devices",
                "The selected subnets do not contain any devices.",
            )
            return

        if not getattr(plugin, "command_dialog", None) or not plugin.command_dialog:
            plugin.command_dialog = CommandDialog(
                plugin, all_devices, plugin.main_window
            )
        else:
            plugin.command_dialog.set_selected_devices(all_devices)

        plugin.command_dialog.show()
        plugin.command_dialog.raise_()
        plugin.command_dialog.activateWindow()
        plugin.command_dialog.target_tabs.setCurrentIndex(2)
        plugin.command_dialog.subnet_table.clearSelection()
        for row in range(plugin.command_dialog.subnet_table.rowCount()):
            subnet_item = plugin.command_dialog.subnet_table.item(row, 0)
            if subnet_item and subnet_item.data(Qt.UserRole)["subnet"] in [
                s["subnet"] for s in subnets
            ]:
                plugin.command_dialog.subnet_table.selectRow(row)
    except Exception as e:
        logger.error(f"Error opening command dialog for subnets: {e}")
        logger.exception("Exception details:")
        QMessageBox.critical(
            plugin.main_window,
            "Error",
            f"An error occurred while opening the command dialog: {str(e)}",
        )


def on_subnet_context_credentials(plugin, subnets):
    """Handle credential manager context menu action for subnets."""
    logger.debug(f"Opening credential manager for {len(subnets)} subnets")
    try:
        dialog = CredentialManager(plugin, subnets=subnets, parent=plugin.main_window)
        dialog.exec()
    except Exception as e:
        logger.error(f"Error opening credential manager for subnets: {e}")
        logger.exception("Exception details:")
        QMessageBox.critical(
            plugin.main_window,
            "Error",
            f"An error occurred while opening the credential manager: {str(e)}",
        )
