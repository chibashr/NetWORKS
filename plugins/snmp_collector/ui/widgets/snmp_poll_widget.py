#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Reusable SNMP Poll widget for SNMP Collector.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QFormLayout,
)
from PySide6.QtCore import Qt

from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES


class SnmpPollWidget(QWidget):
    """Widget for SNMP GET/GETNEXT polling."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.plugin = plugin

        layout = QVBoxLayout(self)
        layout.setSpacing(PLUGIN_UI_SIZES["grid"])
        layout.setContentsMargins(0, 0, 0, 0)

        poll_form = QFormLayout()
        self.poll_host_edit = QLineEdit()
        self.poll_host_edit.setPlaceholderText("192.168.1.1")
        poll_form.addRow("Host:", self.poll_host_edit)
        self.poll_oid_edit = QLineEdit()
        self.poll_oid_edit.setPlaceholderText("1.3.6.1.2.1.1.1.0 or comma-separated OIDs")
        poll_form.addRow("OID(s):", self.poll_oid_edit)
        self.poll_community_edit = QLineEdit()
        self.poll_community_edit.setText(plugin.settings["community"]["value"])
        self.poll_community_edit.setEchoMode(QLineEdit.Password)
        poll_form.addRow("Community:", self.poll_community_edit)
        layout.addLayout(poll_form)

        poll_btn_row = QHBoxLayout()
        self.poll_get_btn = QPushButton("GET")
        self.poll_get_btn.setToolTip("SNMP GET")
        self.poll_get_btn.clicked.connect(lambda: plugin._on_poll_get_clicked(self))
        self.poll_getnext_btn = QPushButton("GETNEXT")
        self.poll_getnext_btn.setToolTip("SNMP GETNEXT")
        self.poll_getnext_btn.clicked.connect(lambda: plugin._on_poll_getnext_clicked(self))
        poll_btn_row.addWidget(self.poll_get_btn)
        poll_btn_row.addWidget(self.poll_getnext_btn)
        layout.addLayout(poll_btn_row)

        self.poll_result_edit = QTextEdit()
        self.poll_result_edit.setReadOnly(True)
        self.poll_result_edit.setMaximumHeight(100)
        self.poll_result_edit.setPlaceholderText("Poll results appear here")
        layout.addWidget(self.poll_result_edit)
