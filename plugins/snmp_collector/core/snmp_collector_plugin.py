#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SNMP Collector Plugin for NetWORKS.

Collects SNMP traps, supports SNMP polling (GET/GETNEXT), and ingestion
for testing with pasted/simulated trap data.
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Optional

from loguru import logger

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QFormLayout,
    QSpinBox,
    QComboBox,
    QMessageBox,
    QTabWidget,
    QSplitter,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, Slot, QThread
from PySide6.QtGui import QFont

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _root not in sys.path:
    sys.path.insert(0, _root)
from src.core.plugin_interface import PluginInterface
from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES
from src.ui.plugin_widgets import CollapsibleSection

from .trap_receiver import TrapReceiverThread, HAS_PYSNMP as HAS_TRAP
from .snmp_poller import snmp_get, snmp_getnext, _init_pysnmp
from ..ui.panel import build_snmp_panel


class PollerWorker(QThread):
    """Worker thread for SNMP polling."""

    finished = Signal(bool, list, str)  # success, results, error

    def __init__(self, host: str, oids: List[str], mode: str = "get",
                 community: str = "public", port: int = 161):
        super().__init__()
        self.host = host
        self.oids = oids
        self.mode = mode
        self.community = community
        self.port = port

    def run(self):
        if self.mode == "getnext" and len(self.oids) >= 1:
            ok, results, err = snmp_getnext(
                self.host, self.oids[0],
                community=self.community, port=self.port,
            )
        else:
            ok, results, err = snmp_get(
                self.host, self.oids,
                community=self.community, port=self.port,
            )
        self.finished.emit(ok, results, err or "")


class SnmpCollectorPlugin(PluginInterface):
    """
    SNMP Collector plugin: collects traps, supports polling, and ingestion for testing.
    """

    trap_received = Signal(dict)  # parsed trap data

    def __init__(self):
        super().__init__()
        self.name = "SNMP Collector"
        self.version = "1.0.0"
        self._trap_receiver: Optional[TrapReceiverThread] = None
        self._traps: List[dict] = []
        self._max_traps = 500
        self.settings = {
            "trap_port": {
                "name": "Trap Port",
                "description": "UDP port for SNMP trap reception (default 1162 for non-root)",
                "type": "int",
                "default": 1162,
                "value": 1162,
            },
            "trap_host": {
                "name": "Trap Bind Host",
                "description": "Host to bind trap receiver (0.0.0.0 for all interfaces)",
                "type": "string",
                "default": "0.0.0.0",
                "value": "0.0.0.0",
            },
            "community": {
                "name": "SNMP Community",
                "description": "Community string for polling",
                "type": "string",
                "default": "public",
                "value": "public",
            },
        }

    def initialize(self, app, plugin_info):
        """Initialize the plugin."""
        self.app = app
        self.device_manager = app.device_manager
        self.main_window = app.main_window
        self.config = app.config
        self.plugin_info = plugin_info
        _init_pysnmp()
        self._initialized = True
        return True

    def _on_trap(self, trap_data: dict):
        """Handle received trap."""
        trap_data["_received_at"] = datetime.now().isoformat()
        self._traps.append(trap_data)
        if len(self._traps) > self._max_traps:
            self._traps.pop(0)
        self.trap_received.emit(trap_data)

    def start_trap_receiver(self) -> bool:
        """Start the trap receiver."""
        if not HAS_TRAP:
            return False
        if self._trap_receiver and self._trap_receiver.is_running:
            return True
        port = self.settings["trap_port"]["value"]
        host = self.settings["trap_host"]["value"]
        self._trap_receiver = TrapReceiverThread(
            host=host, port=port, on_trap=self._on_trap
        )
        return self._trap_receiver.start()

    def stop_trap_receiver(self):
        """Stop the trap receiver."""
        if self._trap_receiver:
            self._trap_receiver.stop()
            self._trap_receiver = None

    def get_traps(self) -> List[dict]:
        """Return collected traps."""
        return list(self._traps)

    def clear_traps(self):
        """Clear collected traps."""
        self._traps.clear()

    def ingest_trap_json(self, json_str: str) -> Optional[str]:
        """
        Ingest simulated trap from JSON string (for testing).
        Returns None on success, error message on failure.
        """
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                for item in data:
                    self._on_trap(item if isinstance(item, dict) else {"raw": str(item)})
            elif isinstance(data, dict):
                self._on_trap(data)
            else:
                return "Invalid JSON: expected object or array"
            return None
        except json.JSONDecodeError as e:
            return str(e)

    @Slot()
    def _on_start_trap_clicked(self):
        """Start trap receiver from UI."""
        if hasattr(self, "trap_port_spin"):
            self.settings["trap_port"]["value"] = self.trap_port_spin.value()
        if hasattr(self, "trap_host_edit"):
            self.settings["trap_host"]["value"] = self.trap_host_edit.text().strip() or "0.0.0.0"
        if self.start_trap_receiver():
            if hasattr(self, "start_trap_btn"):
                self.start_trap_btn.setEnabled(False)
            if hasattr(self, "stop_trap_btn"):
                self.stop_trap_btn.setEnabled(True)
            if hasattr(self, "trap_status_label"):
                port = self.settings["trap_port"]["value"]
                self.trap_status_label.setText(f"Listening on :{port}")
        else:
            QMessageBox.warning(
                self.main_window,
                "SNMP Collector",
                "Failed to start trap receiver. Is pysnmp installed?",
            )

    @Slot()
    def _on_stop_trap_clicked(self):
        """Stop trap receiver from UI."""
        self.stop_trap_receiver()
        if hasattr(self, "start_trap_btn"):
            self.start_trap_btn.setEnabled(True)
        if hasattr(self, "stop_trap_btn"):
            self.stop_trap_btn.setEnabled(False)
        if hasattr(self, "trap_status_label"):
            self.trap_status_label.setText("Stopped")

    @Slot()
    def _on_poll_get_clicked(self):
        """Run SNMP GET from UI."""
        host = self.poll_host_edit.text().strip() if hasattr(self, "poll_host_edit") else ""
        oid_text = self.poll_oid_edit.text().strip() if hasattr(self, "poll_oid_edit") else ""
        community = self.poll_community_edit.text() or "public" if hasattr(self, "poll_community_edit") else "public"
        if not host:
            self.poll_result_edit.setPlainText("Enter host")
            return
        oids = [o.strip() for o in oid_text.split(",") if o.strip()]
        if not oids:
            self.poll_result_edit.setPlainText("Enter at least one OID")
            return
        self.poll_result_edit.setPlainText("Polling...")
        worker = PollerWorker(host, oids, mode="get", community=community)
        worker.finished.connect(self._on_poll_finished)
        worker.setProperty("_worker", worker)
        self._poll_worker = worker
        worker.start()

    @Slot()
    def _on_poll_getnext_clicked(self):
        """Run SNMP GETNEXT from UI."""
        host = self.poll_host_edit.text().strip() if hasattr(self, "poll_host_edit") else ""
        oid_text = self.poll_oid_edit.text().strip() if hasattr(self, "poll_oid_edit") else ""
        community = self.poll_community_edit.text() or "public" if hasattr(self, "poll_community_edit") else "public"
        if not host:
            self.poll_result_edit.setPlainText("Enter host")
            return
        oids = [o.strip() for o in oid_text.split(",") if o.strip()] or ["1.3.6.1.2.1.1"]
        self.poll_result_edit.setPlainText("Polling...")
        worker = PollerWorker(host, oids, mode="getnext", community=community)
        worker.finished.connect(self._on_poll_finished)
        self._poll_worker = worker
        worker.start()

    @Slot(bool, list, str)
    def _on_poll_finished(self, success: bool, results: list, error: str):
        """Handle poll worker completion."""
        if hasattr(self, "poll_result_edit"):
            if success:
                lines = [f"{oid} = {val}" for oid, val in results]
                self.poll_result_edit.setPlainText("\n".join(lines))
            else:
                self.poll_result_edit.setPlainText(f"Error: {error}")

    @Slot()
    def _on_ingest_clicked(self):
        """Ingest pasted JSON as simulated trap(s)."""
        text = self.ingest_edit.toPlainText().strip() if hasattr(self, "ingest_edit") else ""
        if not text:
            return
        err = self.ingest_trap_json(text)
        if err:
            QMessageBox.warning(
                self.main_window,
                "SNMP Collector",
                f"Invalid JSON: {err}",
            )
        else:
            if hasattr(self, "ingest_edit"):
                self.ingest_edit.clear()

    @Slot()
    def _on_clear_traps_clicked(self):
        """Clear collected traps."""
        self.clear_traps()
        if hasattr(self, "traps_table"):
            self.traps_table.setRowCount(0)

    def get_dock_widgets(self):
        """Provide the SNMP Collector dock panel."""
        widget, dock = build_snmp_panel(self)
        self.trap_received.connect(self._on_trap_received_ui)
        return [("SNMP Collector", widget, Qt.RightDockWidgetArea)]

    @Slot(dict)
    def _on_trap_received_ui(self, trap: dict):
        """Update UI when trap is received."""
        if hasattr(self, "traps_table"):
            from ..ui.panel import _add_trap_to_table
            _add_trap_to_table(self, trap)

    def cleanup(self):
        """Clean up when plugin is unloaded."""
        self.stop_trap_receiver()
        return super().cleanup()
