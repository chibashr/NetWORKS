#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Reusable Collected Traps table widget for SNMP Collector.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
)
from PySide6.QtCore import Qt

from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES


def add_trap_to_table(table: QTableWidget, trap: dict) -> None:
    """Append trap to the traps table."""
    row = table.rowCount()
    table.insertRow(row)
    ts = trap.get("_received_at", "")[:19] if "_received_at" in trap else ""
    addr = trap.get("transport_address", trap.get("agent_address", ""))
    varbinds = trap.get("varbinds", [])
    oid_str = varbinds[0]["oid"] if varbinds else trap.get("enterprise", "")
    val_str = varbinds[0]["value"] if varbinds else ""
    table.setItem(row, 0, QTableWidgetItem(ts))
    table.setItem(row, 1, QTableWidgetItem(str(addr)))
    table.setItem(row, 2, QTableWidgetItem(str(oid_str)))
    table.setItem(row, 3, QTableWidgetItem(str(val_str)[:80]))


class TrapsTableWidget(QWidget):
    """Widget showing collected traps table with Clear button."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.plugin = plugin

        layout = QVBoxLayout(self)
        layout.setSpacing(PLUGIN_UI_SIZES["grid"])
        layout.setContentsMargins(0, 0, 0, 0)

        self.traps_table = QTableWidget()
        self.traps_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plugin.trap_received.connect(self._on_trap_received)
        plugin.traps_cleared.connect(self._on_traps_cleared)
        self.traps_table.setColumnCount(4)
        self.traps_table.setHorizontalHeaderLabels(["Time", "Source", "OID/Type", "Value"])
        self.traps_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.traps_table.setAlternatingRowColors(True)
        self.traps_table.setMinimumHeight(120)
        layout.addWidget(self.traps_table)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: plugin._on_clear_traps_clicked(self))
        layout.addWidget(clear_btn)

        for trap in plugin.get_traps():
            add_trap_to_table(self.traps_table, trap)

    def _on_trap_received(self, trap: dict):
        """Append trap to table when received."""
        add_trap_to_table(self.traps_table, trap)

    def _on_traps_cleared(self):
        """Clear table when traps are cleared."""
        self.traps_table.setRowCount(0)
