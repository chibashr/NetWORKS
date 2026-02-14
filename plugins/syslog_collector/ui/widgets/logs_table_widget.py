#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Logs table widget for Syslog Collector.
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


def add_log_to_table(table, log: dict) -> None:
    """Append log to the logs table."""
    row = table.rowCount()
    table.insertRow(row)
    ts = log.get("_received_at", "")[:19] if "_received_at" in log else ""
    facility = log.get("facility_name", "")
    severity = log.get("severity_name", "")
    host = log.get("host", log.get("_source_addr", ""))
    msg = log.get("message", log.get("raw", ""))[:120]
    table.setItem(row, 0, QTableWidgetItem(ts))
    table.setItem(row, 1, QTableWidgetItem(str(facility)))
    table.setItem(row, 2, QTableWidgetItem(str(severity)))
    table.setItem(row, 3, QTableWidgetItem(str(host)))
    table.setItem(row, 4, QTableWidgetItem(str(msg)))


class LogsTableWidget(QWidget):
    """Widget showing collected syslog table with Clear button."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.plugin = plugin

        layout = QVBoxLayout(self)
        layout.setSpacing(PLUGIN_UI_SIZES["grid"])
        layout.setContentsMargins(0, 0, 0, 0)

        self.logs_table = QTableWidget()
        self.logs_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plugin.log_received.connect(self._on_log_received)
        plugin.logs_cleared.connect(self._on_logs_cleared)
        self.logs_table.setColumnCount(5)
        self.logs_table.setHorizontalHeaderLabels(
            ["Time", "Facility", "Severity", "Host", "Message"]
        )
        self.logs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.logs_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.logs_table.setAlternatingRowColors(True)
        self.logs_table.setMinimumHeight(120)
        layout.addWidget(self.logs_table)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: plugin._on_clear_logs_clicked(self))
        layout.addWidget(clear_btn)

        for log in plugin.get_logs():
            add_log_to_table(self.logs_table, log)

    def _on_log_received(self, log: dict):
        """Append log to table when received."""
        add_log_to_table(self.logs_table, log)

    def _on_logs_cleared(self):
        """Clear table when logs are cleared."""
        self.logs_table.setRowCount(0)
