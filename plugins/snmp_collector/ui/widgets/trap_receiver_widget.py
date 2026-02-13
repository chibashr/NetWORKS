#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Reusable Trap Receiver widget for SNMP Collector.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)
from PySide6.QtCore import Qt

from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES


class TrapReceiverWidget(QWidget):
    """Widget for trap receiver bind/port and start/stop controls."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.plugin = plugin

        layout = QVBoxLayout(self)
        layout.setSpacing(PLUGIN_UI_SIZES["grid"])
        layout.setContentsMargins(0, 0, 0, 0)

        trap_host_row = QHBoxLayout()
        trap_host_row.addWidget(QLabel("Bind:"))
        self.trap_host_edit = QLineEdit()
        self.trap_host_edit.setPlaceholderText("0.0.0.0")
        self.trap_host_edit.setText(plugin.settings["trap_host"]["value"])
        self.trap_host_edit.setMaximumWidth(120)
        trap_host_row.addWidget(self.trap_host_edit)
        trap_host_row.addWidget(QLabel("Port:"))
        self.trap_port_spin = QSpinBox()
        self.trap_port_spin.setRange(1, 65535)
        self.trap_port_spin.setValue(plugin.settings["trap_port"]["value"])
        self.trap_port_spin.setMaximumWidth(80)
        trap_host_row.addWidget(self.trap_port_spin)
        layout.addLayout(trap_host_row)

        trap_btn_row = QHBoxLayout()
        self.start_trap_btn = QPushButton("Start")
        self.start_trap_btn.setToolTip("Start listening for SNMP traps")
        self.start_trap_btn.clicked.connect(lambda: plugin._on_start_trap_clicked(self))
        self.stop_trap_btn = QPushButton("Stop")
        self.stop_trap_btn.setToolTip("Stop trap receiver")
        self.stop_trap_btn.clicked.connect(lambda: plugin._on_stop_trap_clicked(self))
        self.stop_trap_btn.setEnabled(False)
        trap_btn_row.addWidget(self.start_trap_btn)
        trap_btn_row.addWidget(self.stop_trap_btn)
        trap_btn_row.addStretch()
        layout.addLayout(trap_btn_row)

        self.trap_status_label = QLabel("Stopped")
        self.trap_status_label.setProperty("plugin_ui_muted", "true")
        layout.addWidget(self.trap_status_label)

        plugin.trap_receiver_started.connect(self._on_receiver_started)
        plugin.trap_receiver_stopped.connect(self._on_receiver_stopped)

        if plugin.is_trap_receiver_running():
            port = plugin.settings["trap_port"]["value"]
            self._on_receiver_started(port)

    def _on_receiver_started(self, port: int):
        """Update UI when trap receiver starts."""
        self.start_trap_btn.setEnabled(False)
        self.stop_trap_btn.setEnabled(True)
        self.trap_status_label.setText(f"Listening on :{port}")

    def _on_receiver_stopped(self):
        """Update UI when trap receiver stops."""
        self.start_trap_btn.setEnabled(True)
        self.stop_trap_btn.setEnabled(False)
        self.trap_status_label.setText("Stopped")
