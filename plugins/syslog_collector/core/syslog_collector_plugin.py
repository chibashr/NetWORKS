#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Syslog Collector Plugin for NetWORKS.

Collects syslog messages over UDP/TCP with configurable parsing
(RFC 3164, RFC 5424, or raw) for testing and monitoring.
"""

import os
import sys
import csv
import json
from datetime import datetime
from typing import List, Optional

from loguru import logger

from PySide6.QtWidgets import QMessageBox, QStyle, QFileDialog
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _root not in sys.path:
    sys.path.insert(0, _root)
from src.core.plugin_interface import PluginInterface
from src.ui.material_icons import material_icon

from .syslog_receiver import SyslogReceiverThread
from .syslog_parser import parse_syslog
from ..ui.panel import build_syslog_panel
from ..ui.dialogs.receiver_config_dialog import ReceiverConfigDialog
from ..ui.dialogs.collected_logs_dialog import CollectedLogsDialog


class SyslogCollectorPlugin(PluginInterface):
    """
    Syslog Collector plugin: live UDP/TCP receiver with configurable parsing.
    """

    log_received = Signal(dict)
    logs_cleared = Signal()
    receiver_started = Signal(int, str)
    receiver_stopped = Signal()

    def __init__(self):
        super().__init__()
        self.name = "Syslog"
        self.version = "1.0.0"
        self._receiver: Optional[SyslogReceiverThread] = None
        self._logs: List[dict] = []
        self._max_logs = 500
        self.settings = {
            "port": {
                "name": "Port",
                "description": "UDP/TCP port for syslog (default 1514, non-privileged)",
                "type": "int",
                "default": 1514,
                "value": 1514,
            },
            "host": {
                "name": "Bind Host",
                "description": "Host to bind receiver (0.0.0.0 for all interfaces)",
                "type": "string",
                "default": "0.0.0.0",
                "value": "0.0.0.0",
            },
            "transport": {
                "name": "Transport",
                "description": "UDP, TCP, or both",
                "type": "string",
                "default": "udp",
                "value": "udp",
            },
            "parse_mode": {
                "name": "Parse Mode",
                "description": "RFC 3164, RFC 5424, or raw",
                "type": "string",
                "default": "rfc3164",
                "value": "rfc3164",
            },
            "max_logs": {
                "name": "Max Logs",
                "description": "Maximum in-memory log entries",
                "type": "int",
                "default": 500,
                "value": 500,
            },
        }

    def initialize(self, app, plugin_info):
        """Initialize the plugin."""
        self.app = app
        self.device_manager = app.device_manager
        self.main_window = app.main_window
        self.config = app.config
        self.plugin_info = plugin_info
        self._initialized = True
        return True

    def _on_message(self, text: str, source_addr: str):
        """Handle received syslog message."""
        mode = self.settings["parse_mode"]["value"]
        parsed = parse_syslog(text, mode=mode)
        parsed["_received_at"] = datetime.now().isoformat()
        parsed["_source_addr"] = source_addr
        self._logs.append(parsed)
        if len(self._logs) > self._max_logs:
            self._logs.pop(0)
        self.log_received.emit(parsed)

    def start_receiver(self) -> bool:
        """Start the syslog receiver."""
        if self._receiver and self._receiver.is_running:
            return True
        port = self.settings["port"]["value"]
        host = self.settings["host"]["value"]
        transport = self.settings["transport"]["value"]
        self._max_logs = self.settings["max_logs"]["value"]
        self._receiver = SyslogReceiverThread(
            host=host,
            port=port,
            transport=transport,
            on_message=self._on_message,
        )
        if self._receiver.start():
            self.receiver_started.emit(port, transport)
            return True
        return False

    def stop_receiver(self):
        """Stop the syslog receiver."""
        if self._receiver:
            self._receiver.stop()
            self._receiver = None
        self.receiver_stopped.emit()

    def is_receiver_running(self) -> bool:
        """Return True if receiver is running."""
        return bool(self._receiver and self._receiver.is_running)

    def get_logs(self) -> List[dict]:
        """Return collected logs."""
        return list(self._logs)

    def clear_logs(self):
        """Clear collected logs."""
        self._logs.clear()
        self.logs_cleared.emit()

    def export_csv(self, filepath: str) -> Optional[str]:
        """Export logs to CSV. Returns None on success, error message on failure."""
        try:
            logs = self.get_logs()
            if not logs:
                return "No logs to export"
            keys = ["_received_at", "facility_name", "severity_name", "host", "message", "raw"]
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                for log in logs:
                    row = {k: log.get(k, "") for k in keys}
                    writer.writerow(row)
            return None
        except Exception as e:
            return str(e)

    def export_json(self, filepath: str) -> Optional[str]:
        """Export logs to JSON. Returns None on success, error message on failure."""
        try:
            logs = self.get_logs()
            if not logs:
                return "No logs to export"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
            return None
        except Exception as e:
            return str(e)

    @Slot()
    def _on_start_receiver_clicked(self, widget=None):
        """Start receiver from UI."""
        if widget:
            self.settings["port"]["value"] = widget.port_spin.value()
            self.settings["host"]["value"] = widget.host_edit.text().strip() or "0.0.0.0"
            self.settings["transport"]["value"] = widget.transport_combo.currentText().lower()
            self.settings["parse_mode"]["value"] = widget.parse_mode_combo.currentData() or "rfc3164"
            self.settings["max_logs"]["value"] = widget.max_logs_spin.value()
        if self.start_receiver():
            port = self.settings["port"]["value"]
            transport = self.settings["transport"]["value"]
            self.receiver_started.emit(port, transport)
        else:
            QMessageBox.warning(
                self.main_window,
                "Syslog Collector",
                "Failed to start syslog receiver.",
            )

    @Slot()
    def _on_stop_receiver_clicked(self, widget=None):
        """Stop receiver from UI."""
        self.stop_receiver()

    @Slot()
    def _on_clear_logs_clicked(self, widget=None):
        """Clear collected logs."""
        self.clear_logs()

    @Slot()
    def _on_export_clicked(self):
        """Show export dialog and export logs."""
        logs = self.get_logs()
        if not logs:
            QMessageBox.information(
                self.main_window,
                "Syslog Collector",
                "No logs to export.",
            )
            return
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Syslog",
            "",
            "CSV (*.csv);;JSON (*.json);;All Files (*)",
        )
        if not filepath:
            return
        if "json" in selected_filter.lower() or filepath.endswith(".json"):
            err = self.export_json(filepath)
        else:
            err = self.export_csv(filepath)
        if err:
            QMessageBox.warning(
                self.main_window,
                "Syslog Collector",
                f"Export failed: {err}",
            )
        else:
            QMessageBox.information(
                self.main_window,
                "Syslog Collector",
                f"Exported {len(logs)} log(s) to {filepath}",
            )

    def get_toolbar_actions(self):
        """Provide toolbar actions: Receiver, View Logs, Export."""
        mw = self.main_window
        icon = material_icon("dns", mw, QStyle.SP_ComputerIcon) if mw else None

        receiver_action = QAction("Receiver", mw or self)
        receiver_action.setToolTip("Open Receiver Config dialog")
        receiver_action.triggered.connect(self._show_receiver_config_dialog)
        if icon and not icon.isNull():
            receiver_action.setIcon(icon)

        logs_action = QAction("View Logs", mw or self)
        logs_action.setToolTip("Open Collected Logs dialog")
        logs_action.triggered.connect(self._show_collected_logs_dialog)

        export_action = QAction("Export", mw or self)
        export_action.setToolTip("Export logs to CSV or JSON")
        export_action.triggered.connect(self._on_export_clicked)

        return [receiver_action, logs_action, export_action]

    def _show_receiver_config_dialog(self):
        dlg = ReceiverConfigDialog(self, self.main_window)
        dlg.exec()

    def _show_collected_logs_dialog(self):
        dlg = CollectedLogsDialog(self, self.main_window)
        dlg.exec()

    def get_dock_widgets(self):
        """Provide the Syslog dock panel."""
        widget = build_syslog_panel(self)
        return [("Syslog", widget, Qt.RightDockWidgetArea)]

    def cleanup(self):
        """Clean up when plugin is unloaded."""
        self.stop_receiver()
        return super().cleanup()
