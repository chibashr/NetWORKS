# -*- coding: utf-8 -*-
"""
Device Connector Plugin for NetWORKS.

Adds a "Connect" submenu to the device table context menu (SSH, Telnet, VNC, RDP, HTTP, HTTPS, FTP).
Opens protocol URLs so the system decides how to open them (like FTP).
"""

import os
import sys
import json
from loguru import logger
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QMenu, QMessageBox, QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QDialogButtonBox, QLabel,
)
from PySide6.QtGui import QIcon

# Ensure project root is on path when loaded as plugin entry point
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.core.plugin_interface import PluginInterface

# Load connection_runner from same directory as this module (avoids path/cache issues)
import importlib.util
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_runner_path = os.path.join(_plugin_dir, "connection_runner.py")
_runner_spec = importlib.util.spec_from_file_location("device_connector_connection_runner", _runner_path)
_connection_runner = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(_connection_runner)

CONNECTION_SSH = _connection_runner.CONNECTION_SSH
CONNECTION_TELNET = _connection_runner.CONNECTION_TELNET
CONNECTION_VNC = _connection_runner.CONNECTION_VNC
CONNECTION_RDP = _connection_runner.CONNECTION_RDP
CONNECTION_HTTP = _connection_runner.CONNECTION_HTTP
CONNECTION_HTTPS = _connection_runner.CONNECTION_HTTPS
CONNECTION_FTP = _connection_runner.CONNECTION_FTP
launch_ssh = _connection_runner.launch_ssh
launch_telnet = _connection_runner.launch_telnet
launch_vnc = _connection_runner.launch_vnc
launch_rdp = _connection_runner.launch_rdp
launch_http = _connection_runner.launch_http
launch_https = _connection_runner.launch_https
launch_ftp = _connection_runner.launch_ftp
DEFAULT_SSH_PORT = _connection_runner.DEFAULT_SSH_PORT
DEFAULT_TELNET_PORT = _connection_runner.DEFAULT_TELNET_PORT
DEFAULT_VNC_PORT = _connection_runner.DEFAULT_VNC_PORT
DEFAULT_RDP_PORT = _connection_runner.DEFAULT_RDP_PORT

PLUGIN_ID = "device_connector"
CONFIG_FILENAME = "config.json"


def _normalize_devices(devices):
    """Normalize to list of devices; handle None and single device."""
    if devices is None:
        return []
    if isinstance(devices, list):
        return [d for d in devices if d is not None]
    return [devices] if devices else []


def _show_credentials_dialog(parent, connection_label):
    """
    Show a dialog for username and password. Returns (username, password) or (None, None) if cancelled.
    password may be empty string if user leaves it blank.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"{connection_label} — Username & Password")
    layout = QVBoxLayout(dialog)
    form = QFormLayout()
    username_edit = QLineEdit()
    username_edit.setPlaceholderText("e.g. admin")
    username_edit.setClearButtonEnabled(True)
    form.addRow(QLabel("Username:"), username_edit)
    password_edit = QLineEdit()
    password_edit.setEchoMode(QLineEdit.Password)
    password_edit.setPlaceholderText("Optional; leave blank to be prompted by the app")
    password_edit.setClearButtonEnabled(True)
    form.addRow(QLabel("Password:"), password_edit)
    layout.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return (username_edit.text().strip(), password_edit.text())
    return (None, None)


class DeviceConnectorPlugin(PluginInterface):
    """
    Plugin that adds a Connect submenu to the device table context menu
    and launches external programs (SSH, Telnet, VNC, Web) for selected devices.
    """

    def __init__(self):
        super().__init__()
        self._device_table = None
        self._context_menu_connected = False
        self._settings = {}

    def _settings_schema(self):
        """Default settings and types. Values may be overwritten by saved config."""
        return {
            "default_ssh_port": {
                "name": "Default SSH port",
                "description": "Default port for SSH connections.",
                "type": "int",
                "default": DEFAULT_SSH_PORT,
                "value": DEFAULT_SSH_PORT,
            },
            "default_telnet_port": {
                "name": "Default Telnet port",
                "description": "Default port for Telnet connections.",
                "type": "int",
                "default": DEFAULT_TELNET_PORT,
                "value": DEFAULT_TELNET_PORT,
            },
            "default_vnc_port": {
                "name": "Default VNC port",
                "description": "Default port for VNC connections.",
                "type": "int",
                "default": DEFAULT_VNC_PORT,
                "value": DEFAULT_VNC_PORT,
            },
            "default_rdp_port": {
                "name": "Default RDP port",
                "description": "Default port for RDP connections.",
                "type": "int",
                "default": DEFAULT_RDP_PORT,
                "value": DEFAULT_RDP_PORT,
            },
        }

    def _config_path(self):
        if not self.plugin_info or not getattr(self.plugin_info, "path", None):
            return None
        return os.path.join(self.plugin_info.path, CONFIG_FILENAME)

    def _load_settings(self):
        """Load settings from config.json; merge with schema defaults."""
        self._settings = self._settings_schema()
        path = self._config_path()
        if not path or not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, val in data.items():
                if key in self._settings:
                    self._settings[key]["value"] = val
        except Exception as e:
            logger.warning(f"[{PLUGIN_ID}] Failed to load config: {e}")

    def _save_settings(self):
        """Persist current setting values to config.json."""
        path = self._config_path()
        if not path:
            return
        try:
            data = {k: v["value"] for k, v in self._settings.items()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"[{PLUGIN_ID}] Failed to save config: {e}")

    def initialize(self, app, plugin_info):
        self.app = app
        self.device_manager = app.device_manager
        self.main_window = app.main_window
        self.config = app.config
        self.plugin_info = plugin_info

        self._load_settings()

        # Defer context menu connection so device table is ready (match Network Scanner pattern)
        if hasattr(self.main_window, "device_table"):
            self._device_table = self.main_window.device_table
            if hasattr(self._device_table, "context_menu_requested"):
                QTimer.singleShot(500, self._connect_context_menu)
        else:
            logger.warning(f"[{PLUGIN_ID}] Main window has no device_table")

        self._initialized = True
        return True

    def _connect_context_menu(self):
        if not self._device_table or self._context_menu_connected:
            return
        try:
            self._device_table.context_menu_requested.connect(self._on_context_menu_requested)
            self._context_menu_connected = True
            logger.debug(f"[{PLUGIN_ID}] Context menu Connect submenu connected")
        except Exception as e:
            logger.exception(f"[{PLUGIN_ID}] Failed to connect context menu: {e}")

    def _on_context_menu_requested(self, devices, menu):
        """Add Connect submenu and SSH / Telnet / VNC / Web actions."""
        devices = _normalize_devices(devices)
        if not devices:
            return
        connect_menu = menu.addMenu("Connect")
        icon_path = None
        if self.plugin_info and getattr(self.plugin_info, "path", None):
            icon_path = os.path.join(
                self.plugin_info.path, "resources", "icons", "connect.svg"
            )
        if icon_path and os.path.isfile(icon_path):
            connect_menu.setIcon(QIcon(icon_path))
        # SSH
        connect_menu.addAction("SSH", lambda: self._launch_connection(devices, CONNECTION_SSH))
        connect_menu.addAction("Telnet", lambda: self._launch_connection(devices, CONNECTION_TELNET))
        connect_menu.addAction("VNC", lambda: self._launch_connection(devices, CONNECTION_VNC))
        connect_menu.addAction("RDP", lambda: self._launch_connection(devices, CONNECTION_RDP))
        connect_menu.addAction("HTTP", lambda: self._launch_connection(devices, CONNECTION_HTTP))
        connect_menu.addAction("HTTPS", lambda: self._launch_connection(devices, CONNECTION_HTTPS))
        connect_menu.addAction("FTP", lambda: self._launch_connection(devices, CONNECTION_FTP))

    def _launch_connection(self, devices, connection_type):
        devices = _normalize_devices(devices)
        if not devices:
            if self.main_window:
                QMessageBox.information(
                    self.main_window,
                    "Device Connector",
                    "No devices selected.",
                )
            return
        no_host = [d for d in devices if not (d.get_property("ip_address") or "").strip() and not (d.get_property("hostname") or "").strip()]
        if no_host:
            if self.main_window:
                QMessageBox.warning(
                    self.main_window,
                    "Device Connector",
                    "Some selected devices have no IP address or hostname. They will be skipped.",
                )
        parent_win = self.main_window if self.main_window else None
        if connection_type == CONNECTION_SSH:
            username, password = _show_credentials_dialog(parent_win, "SSH")
            if username is None:
                return
            success, err = launch_ssh(
                devices,
                int(self._settings.get("default_ssh_port", {}).get("value", DEFAULT_SSH_PORT)),
                PLUGIN_ID,
                username=username,
                password=password or None,
            )
        elif connection_type == CONNECTION_TELNET:
            username, password = _show_credentials_dialog(parent_win, "Telnet")
            if username is None:
                return
            success, err = launch_telnet(
                devices,
                int(self._settings.get("default_telnet_port", {}).get("value", DEFAULT_TELNET_PORT)),
                PLUGIN_ID,
                username=username,
                password=password or None,
            )
        elif connection_type == CONNECTION_VNC:
            success, err = launch_vnc(
                devices,
                int(self._settings.get("default_vnc_port", {}).get("value", DEFAULT_VNC_PORT)),
                PLUGIN_ID,
            )
        elif connection_type == CONNECTION_RDP:
            success, err = launch_rdp(
                devices,
                int(self._settings.get("default_rdp_port", {}).get("value", DEFAULT_RDP_PORT)),
                PLUGIN_ID,
            )
        elif connection_type == CONNECTION_HTTP:
            success, err = launch_http(devices, PLUGIN_ID)
        elif connection_type == CONNECTION_HTTPS:
            success, err = launch_https(devices, PLUGIN_ID)
        elif connection_type == CONNECTION_FTP:
            success, err = launch_ftp(devices, PLUGIN_ID)
        else:
            success, err = 0, "Unknown connection type"
        if err and self.main_window:
            QMessageBox.warning(self.main_window, "Device Connector", err)
        elif success:
            logger.info(f"[{PLUGIN_ID}] Opened {connection_type} for {success} device(s)")

    def cleanup(self):
        if self._device_table and self._context_menu_connected:
            try:
                self._device_table.context_menu_requested.disconnect(self._on_context_menu_requested)
            except Exception:
                pass
            self._context_menu_connected = False
        self._device_table = None
        return super().cleanup()

    def get_settings(self):
        return dict(self._settings)

    def update_setting(self, setting_id, value):
        if setting_id not in self._settings:
            return False
        s = self._settings[setting_id]
        if s["type"] == "int":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return False
        s["value"] = value
        self._save_settings()
        return True


# Plugin manager discovers a class in this module with initialize()
__all__ = ["DeviceConnectorPlugin"]
