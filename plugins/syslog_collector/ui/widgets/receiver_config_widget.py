#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Receiver Config widget for Syslog Collector.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QComboBox,
)
from PySide6.QtCore import Qt

from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES


class ReceiverConfigWidget(QWidget):
    """Widget for syslog receiver bind/port, transport, parse mode, and start/stop."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.plugin = plugin

        layout = QVBoxLayout(self)
        layout.setSpacing(PLUGIN_UI_SIZES["grid"])
        layout.setContentsMargins(0, 0, 0, 0)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Bind:"))
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("0.0.0.0")
        self.host_edit.setText(plugin.settings["host"]["value"])
        self.host_edit.setMaximumWidth(120)
        row1.addWidget(self.host_edit)
        row1.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(plugin.settings["port"]["value"])
        self.port_spin.setMaximumWidth(80)
        row1.addWidget(self.port_spin)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Transport:"))
        self.transport_combo = QComboBox()
        self.transport_combo.addItems(["udp", "tcp", "both"])
        self.transport_combo.setCurrentText(plugin.settings["transport"]["value"])
        self.transport_combo.setMaximumWidth(100)
        row2.addWidget(self.transport_combo)
        row2.addWidget(QLabel("Parse:"))
        self.parse_mode_combo = QComboBox()
        self.parse_mode_combo.addItem("RFC 3164 (BSD)", "rfc3164")
        self.parse_mode_combo.addItem("RFC 5424 (Structured)", "rfc5424")
        self.parse_mode_combo.addItem("Raw", "raw")
        idx = self.parse_mode_combo.findData(plugin.settings["parse_mode"]["value"])
        self.parse_mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.parse_mode_combo.setMaximumWidth(180)
        row2.addWidget(self.parse_mode_combo)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Max logs:"))
        self.max_logs_spin = QSpinBox()
        self.max_logs_spin.setRange(1, 10000)
        self.max_logs_spin.setValue(plugin.settings["max_logs"]["value"])
        self.max_logs_spin.setMaximumWidth(80)
        row3.addWidget(self.max_logs_spin)
        row3.addStretch()
        layout.addLayout(row3)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setToolTip("Start listening for syslog messages")
        self.start_btn.clicked.connect(lambda: plugin._on_start_receiver_clicked(self))
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setToolTip("Stop syslog receiver")
        self.stop_btn.clicked.connect(lambda: plugin._on_stop_receiver_clicked(self))
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_label = QLabel("Stopped")
        self.status_label.setProperty("plugin_ui_muted", "true")
        layout.addWidget(self.status_label)
        layout.addStretch()

        plugin.receiver_started.connect(self._on_receiver_started)
        plugin.receiver_stopped.connect(self._on_receiver_stopped)

        if plugin.is_receiver_running():
            port = plugin.settings["port"]["value"]
            transport = plugin.settings["transport"]["value"]
            self._on_receiver_started(port, transport)

    def _on_receiver_started(self, port: int, transport: str):
        """Update UI when receiver starts."""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText(f"Listening on :{port} ({transport})")

    def _on_receiver_stopped(self):
        """Update UI when receiver stops."""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Stopped")
