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

from PySide6.QtWidgets import QMessageBox, QStyle
from PySide6.QtCore import Qt, Signal, Slot, QThread
from PySide6.QtGui import QAction

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _root not in sys.path:
    sys.path.insert(0, _root)
from src.core.plugin_interface import PluginInterface
from src.ui.material_icons import material_icon

from .trap_receiver import TrapReceiverThread, HAS_PYSNMP as HAS_TRAP
from .snmp_poller import snmp_get, snmp_getnext, build_auth_data, _init_pysnmp
from ..ui.panel import build_snmp_panel
from ..ui.dialogs.trap_receiver_dialog import TrapReceiverDialog
from ..ui.dialogs.snmp_poll_dialog import SnmpPollDialog
from ..ui.dialogs.ingestion_dialog import IngestionDialog
from ..ui.dialogs.collected_traps_dialog import CollectedTrapsDialog


class PollerWorker(QThread):
    """Worker thread for SNMP polling."""

    finished = Signal(bool, list, str)  # success, results, error

    def __init__(self, host: str, oids: List[str], mode: str = "get",
                 auth_data=None, port: int = 161):
        super().__init__()
        self.host = host
        self.oids = oids
        self.mode = mode
        self.auth_data = auth_data
        self.port = port

    def run(self):
        if not self.auth_data:
            self.finished.emit(False, [], "Invalid auth configuration")
            return
        if self.mode == "getnext" and len(self.oids) >= 1:
            ok, results, err = snmp_getnext(
                self.host, self.oids[0],
                auth_data=self.auth_data, port=self.port,
            )
        else:
            ok, results, err = snmp_get(
                self.host, self.oids,
                auth_data=self.auth_data, port=self.port,
            )
        self.finished.emit(ok, results, err or "")


class SnmpCollectorPlugin(PluginInterface):
    """
    SNMP Collector plugin: collects traps, supports polling, and ingestion for testing.
    """

    trap_received = Signal(dict)  # parsed trap data
    traps_cleared = Signal()
    trap_receiver_started = Signal(int)  # port
    trap_receiver_stopped = Signal()

    def __init__(self):
        super().__init__()
        self.name = "SNMP"
        self.version = "1.0.3"
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

    def is_trap_receiver_running(self) -> bool:
        """Return True if trap receiver is running."""
        return bool(self._trap_receiver and self._trap_receiver.is_running)

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
    def _on_start_trap_clicked(self, widget=None):
        """Start trap receiver from UI."""
        if widget:
            self.settings["trap_port"]["value"] = widget.trap_port_spin.value()
            self.settings["trap_host"]["value"] = (
                widget.trap_host_edit.text().strip() or "0.0.0.0"
            )
        if self.start_trap_receiver():
            port = self.settings["trap_port"]["value"]
            self.trap_receiver_started.emit(port)
        else:
            QMessageBox.warning(
                self.main_window,
                "SNMP Collector",
                "Failed to start trap receiver. Is pysnmp installed?",
            )

    @Slot()
    def _on_stop_trap_clicked(self, widget=None):
        """Stop trap receiver from UI."""
        self.stop_trap_receiver()
        self.trap_receiver_stopped.emit()

    def _build_auth_from_widget(self, widget):
        """Build auth_data from widget fields."""
        version = widget.poll_version_combo.currentText()
        if version in ("v1", "v2c"):
            community = widget.poll_community_edit.text().strip() or "public"
            return build_auth_data(version=version, community=community)
        user = widget.poll_user_edit.text().strip() or "initial"
        auth_proto = widget.poll_auth_proto_combo.currentText().lower() if widget.poll_auth_pass_edit.text() else ""
        auth_pass = widget.poll_auth_pass_edit.text()
        priv_proto = widget.poll_priv_proto_combo.currentText().lower() if widget.poll_priv_pass_edit.text() else ""
        if priv_proto == "none":
            priv_proto = ""
        priv_pass = widget.poll_priv_pass_edit.text()
        return build_auth_data(
            version="v3",
            user=user,
            auth_protocol=auth_proto,
            auth_password=auth_pass,
            priv_protocol=priv_proto,
            priv_password=priv_pass,
        )

    @Slot()
    def _on_poll_get_clicked(self, widget=None):
        """Run SNMP GET from UI."""
        if not widget:
            return
        host = widget.poll_host_edit.text().strip()
        oid_text = widget.poll_oid_edit.text().strip()
        if not host:
            widget.poll_result_edit.setPlainText("Enter host")
            return
        oids = [o.strip() for o in oid_text.split(",") if o.strip()]
        if not oids:
            widget.poll_result_edit.setPlainText("Enter at least one OID")
            return
        auth_data = self._build_auth_from_widget(widget)
        if not auth_data:
            widget.poll_result_edit.setPlainText("Invalid auth configuration")
            return
        widget.poll_result_edit.setPlainText("Polling...")
        self._poll_widget = widget
        worker = PollerWorker(host, oids, mode="get", auth_data=auth_data)
        worker.finished.connect(self._on_poll_finished)
        self._poll_worker = worker
        worker.start()

    @Slot()
    def _on_poll_getnext_clicked(self, widget=None):
        """Run SNMP GETNEXT from UI."""
        if not widget:
            return
        host = widget.poll_host_edit.text().strip()
        oid_text = widget.poll_oid_edit.text().strip()
        if not host:
            widget.poll_result_edit.setPlainText("Enter host")
            return
        oids = [o.strip() for o in oid_text.split(",") if o.strip()] or ["1.3.6.1.2.1.1"]
        auth_data = self._build_auth_from_widget(widget)
        if not auth_data:
            widget.poll_result_edit.setPlainText("Invalid auth configuration")
            return
        widget.poll_result_edit.setPlainText("Polling...")
        self._poll_widget = widget
        worker = PollerWorker(host, oids, mode="getnext", auth_data=auth_data)
        worker.finished.connect(self._on_poll_finished)
        self._poll_worker = worker
        worker.start()

    @Slot(bool, list, str)
    def _on_poll_finished(self, success: bool, results: list, error: str):
        """Handle poll worker completion."""
        widget = getattr(self, "_poll_widget", None)
        if widget:
            if success:
                lines = [f"{oid} = {val}" for oid, val in results]
                widget.poll_result_edit.setPlainText("\n".join(lines))
            else:
                widget.poll_result_edit.setPlainText(f"Error: {error}")

    @Slot()
    def _on_ingest_clicked(self, widget=None):
        """Ingest pasted JSON as simulated trap(s)."""
        if not widget:
            return
        text = widget.ingest_edit.toPlainText().strip()
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
            widget.ingest_edit.clear()

    @Slot()
    def _on_clear_traps_clicked(self, widget=None):
        """Clear collected traps."""
        self.clear_traps()

    def get_toolbar_actions(self):
        """Provide toolbar actions that open dialogs for each SNMP function."""
        mw = self.main_window
        icon = material_icon("dns", mw, QStyle.SP_ComputerIcon) if mw else None

        trap_action = QAction("Trap Receiver", mw or self)
        trap_action.setToolTip("Open Trap Receiver dialog")
        trap_action.triggered.connect(self._show_trap_receiver_dialog)
        if icon and not icon.isNull():
            trap_action.setIcon(icon)

        poll_action = QAction("SNMP Poll", mw or self)
        poll_action.setToolTip("Open SNMP Poll dialog")
        poll_action.triggered.connect(self._show_snmp_poll_dialog)

        ingest_action = QAction("Ingestion", mw or self)
        ingest_action.setToolTip("Open Ingestion dialog (testing)")
        ingest_action.triggered.connect(self._show_ingestion_dialog)

        traps_action = QAction("View Traps", mw or self)
        traps_action.setToolTip("Open Collected Traps dialog")
        traps_action.triggered.connect(self._show_collected_traps_dialog)

        return [trap_action, poll_action, ingest_action, traps_action]

    def _show_trap_receiver_dialog(self):
        dlg = TrapReceiverDialog(self, self.main_window)
        dlg.exec()

    def _show_snmp_poll_dialog(self):
        dlg = SnmpPollDialog(self, self.main_window)
        dlg.exec()

    def _show_ingestion_dialog(self):
        dlg = IngestionDialog(self, self.main_window)
        dlg.exec()

    def _show_collected_traps_dialog(self):
        dlg = CollectedTrapsDialog(self, self.main_window)
        dlg.exec()

    def get_dock_widgets(self):
        """Provide the SNMP dock panel with tabbed layout."""
        widget = build_snmp_panel(self)
        return [("SNMP", widget, Qt.RightDockWidgetArea)]

    def cleanup(self):
        """Clean up when plugin is unloaded."""
        self.stop_trap_receiver()
        return super().cleanup()
