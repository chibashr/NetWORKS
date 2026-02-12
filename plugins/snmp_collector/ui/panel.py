#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SNMP Collector panel layout.
"""

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
    QTabWidget,
    QSizePolicy,
    QHeaderView,
    QSplitter,
)
from PySide6.QtCore import Qt

from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES
from src.ui.plugin_widgets import CollapsibleSection


def _format_trap_for_display(trap: dict) -> str:
    """Format trap as readable text."""
    lines = []
    for k, v in trap.items():
        if k.startswith("_"):
            continue
        if isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    sub = " | ".join(f"{x}={y}" for x, y in item.items())
                    lines.append(f"  [{i}] {sub}")
                else:
                    lines.append(f"  [{i}] {item}")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)


def build_snmp_panel(plugin):
    """Build the SNMP Collector dock panel. Returns widget only; main window creates dock."""
    container = QWidget()
    mark_plugin_ui(container)
    layout = QVBoxLayout(container)
    grid = PLUGIN_UI_SIZES["grid"]
    pad = PLUGIN_UI_SIZES["section_padding"]
    layout.setContentsMargins(pad, pad, pad, pad)
    layout.setSpacing(grid)

    # Trap Receiver section
    trap_section = CollapsibleSection("Trap Receiver", expanded=True)
    trap_layout = trap_section.content_layout
    trap_host_row = QHBoxLayout()
    trap_host_row.addWidget(QLabel("Bind:"))
    plugin.trap_host_edit = QLineEdit()
    plugin.trap_host_edit.setPlaceholderText("0.0.0.0")
    plugin.trap_host_edit.setText(plugin.settings["trap_host"]["value"])
    plugin.trap_host_edit.setMaximumWidth(120)
    trap_host_row.addWidget(plugin.trap_host_edit)
    trap_host_row.addWidget(QLabel("Port:"))
    plugin.trap_port_spin = QSpinBox()
    plugin.trap_port_spin.setRange(1, 65535)
    plugin.trap_port_spin.setValue(plugin.settings["trap_port"]["value"])
    plugin.trap_port_spin.setMaximumWidth(80)
    trap_host_row.addWidget(plugin.trap_port_spin)
    trap_layout.addLayout(trap_host_row)
    trap_btn_row = QHBoxLayout()
    plugin.start_trap_btn = QPushButton("Start")
    plugin.start_trap_btn.setToolTip("Start listening for SNMP traps")
    plugin.start_trap_btn.clicked.connect(plugin._on_start_trap_clicked)
    plugin.stop_trap_btn = QPushButton("Stop")
    plugin.stop_trap_btn.setToolTip("Stop trap receiver")
    plugin.stop_trap_btn.clicked.connect(plugin._on_stop_trap_clicked)
    plugin.stop_trap_btn.setEnabled(False)
    trap_btn_row.addWidget(plugin.start_trap_btn)
    trap_btn_row.addWidget(plugin.stop_trap_btn)
    trap_btn_row.addStretch()
    trap_layout.addLayout(trap_btn_row)
    plugin.trap_status_label = QLabel("Stopped")
    plugin.trap_status_label.setProperty("plugin_ui_muted", "true")
    trap_layout.addWidget(plugin.trap_status_label)
    layout.addWidget(trap_section)

    # Poll section
    poll_section = CollapsibleSection("SNMP Poll", expanded=True)
    poll_layout = poll_section.content_layout
    poll_form = QFormLayout()
    plugin.poll_host_edit = QLineEdit()
    plugin.poll_host_edit.setPlaceholderText("192.168.1.1")
    poll_form.addRow("Host:", plugin.poll_host_edit)
    plugin.poll_oid_edit = QLineEdit()
    plugin.poll_oid_edit.setPlaceholderText("1.3.6.1.2.1.1.1.0 or comma-separated OIDs")
    poll_form.addRow("OID(s):", plugin.poll_oid_edit)
    plugin.poll_community_edit = QLineEdit()
    plugin.poll_community_edit.setText(plugin.settings["community"]["value"])
    plugin.poll_community_edit.setEchoMode(QLineEdit.Password)
    poll_form.addRow("Community:", plugin.poll_community_edit)
    poll_layout.addLayout(poll_form)
    poll_btn_row = QHBoxLayout()
    plugin.poll_get_btn = QPushButton("GET")
    plugin.poll_get_btn.setToolTip("SNMP GET")
    plugin.poll_get_btn.clicked.connect(plugin._on_poll_get_clicked)
    plugin.poll_getnext_btn = QPushButton("GETNEXT")
    plugin.poll_getnext_btn.setToolTip("SNMP GETNEXT")
    plugin.poll_getnext_btn.clicked.connect(plugin._on_poll_getnext_clicked)
    poll_btn_row.addWidget(plugin.poll_get_btn)
    poll_btn_row.addWidget(plugin.poll_getnext_btn)
    poll_layout.addLayout(poll_btn_row)
    plugin.poll_result_edit = QTextEdit()
    plugin.poll_result_edit.setReadOnly(True)
    plugin.poll_result_edit.setMaximumHeight(100)
    plugin.poll_result_edit.setPlaceholderText("Poll results appear here")
    poll_layout.addWidget(plugin.poll_result_edit)
    layout.addWidget(poll_section)

    # Ingestion (testing) section
    ingest_section = CollapsibleSection("Ingestion (Testing)", expanded=True)
    ingest_layout = ingest_section.content_layout
    ingest_layout.addWidget(QLabel("Paste JSON trap(s) to simulate:"))
    plugin.ingest_edit = QTextEdit()
    plugin.ingest_edit.setPlaceholderText('{"agent_address": "192.168.1.1", "varbinds": [{"oid": "1.1.1", "value": "test"}]}')
    plugin.ingest_edit.setMaximumHeight(80)
    ingest_layout.addWidget(plugin.ingest_edit)
    plugin.ingest_btn = QPushButton("Ingest")
    plugin.ingest_btn.setToolTip("Add pasted JSON as simulated trap(s)")
    plugin.ingest_btn.clicked.connect(plugin._on_ingest_clicked)
    ingest_layout.addWidget(plugin.ingest_btn)
    layout.addWidget(ingest_section)

    # Traps table
    traps_section = CollapsibleSection("Collected Traps", expanded=True)
    traps_layout = traps_section.content_layout
    plugin.traps_table = QTableWidget()
    plugin.traps_table.setColumnCount(4)
    plugin.traps_table.setHorizontalHeaderLabels(["Time", "Source", "OID/Type", "Value"])
    plugin.traps_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    plugin.traps_table.setAlternatingRowColors(True)
    plugin.traps_table.setMaximumHeight(200)
    traps_layout.addWidget(plugin.traps_table)
    clear_btn = QPushButton("Clear")
    clear_btn.clicked.connect(plugin._on_clear_traps_clicked)
    traps_layout.addWidget(clear_btn)
    layout.addWidget(traps_section)

    layout.addStretch()

    return container


def _add_trap_to_table(plugin, trap: dict):
    """Append trap to the traps table."""
    tbl = plugin.traps_table
    row = tbl.rowCount()
    tbl.insertRow(row)
    ts = trap.get("_received_at", "")[:19] if "_received_at" in trap else ""
    addr = trap.get("transport_address", trap.get("agent_address", ""))
    varbinds = trap.get("varbinds", [])
    oid_str = varbinds[0]["oid"] if varbinds else trap.get("enterprise", "")
    val_str = varbinds[0]["value"] if varbinds else ""
    tbl.setItem(row, 0, QTableWidgetItem(ts))
    tbl.setItem(row, 1, QTableWidgetItem(str(addr)))
    tbl.setItem(row, 2, QTableWidgetItem(str(oid_str)))
    tbl.setItem(row, 3, QTableWidgetItem(str(val_str)[:80]))
