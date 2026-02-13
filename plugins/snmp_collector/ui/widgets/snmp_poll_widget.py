#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Reusable SNMP Poll widget for SNMP Collector.
Supports SNMPv1, v2c, and v3 with conditional v3 options.
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
    QComboBox,
    QFrame,
)
from PySide6.QtCore import Qt

from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES


class SnmpPollWidget(QWidget):
    """Widget for SNMP GET/GETNEXT polling with v1/v2c/v3 support."""

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

        self.poll_version_combo = QComboBox()
        self.poll_version_combo.addItems(["v1", "v2c", "v3"])
        self.poll_version_combo.currentTextChanged.connect(self._on_version_changed)
        poll_form.addRow("Version:", self.poll_version_combo)

        self.community_frame = QFrame()
        community_layout = QFormLayout(self.community_frame)
        community_layout.setContentsMargins(0, 0, 0, 0)
        self.poll_community_edit = QLineEdit()
        self.poll_community_edit.setText(plugin.settings["community"]["value"])
        self.poll_community_edit.setPlaceholderText("public")
        community_layout.addRow("Community:", self.poll_community_edit)
        layout.addLayout(poll_form)
        layout.addWidget(self.community_frame)

        self.v3_frame = QFrame()
        self.v3_frame.setObjectName("SnmpV3Options")
        v3_layout = QFormLayout(self.v3_frame)
        v3_layout.setContentsMargins(0, 8, 0, 0)
        self.poll_user_edit = QLineEdit()
        self.poll_user_edit.setPlaceholderText("username")
        v3_layout.addRow("User:", self.poll_user_edit)
        self.poll_auth_proto_combo = QComboBox()
        self.poll_auth_proto_combo.addItems(["MD5", "SHA"])
        v3_layout.addRow("Auth protocol:", self.poll_auth_proto_combo)
        self.poll_auth_pass_edit = QLineEdit()
        self.poll_auth_pass_edit.setPlaceholderText("auth password (optional)")
        self.poll_auth_pass_edit.setEchoMode(QLineEdit.Password)
        v3_layout.addRow("Auth password:", self.poll_auth_pass_edit)
        self.poll_priv_proto_combo = QComboBox()
        self.poll_priv_proto_combo.addItems(["None", "DES", "AES128"])
        v3_layout.addRow("Priv protocol:", self.poll_priv_proto_combo)
        self.poll_priv_pass_edit = QLineEdit()
        self.poll_priv_pass_edit.setPlaceholderText("privacy password (optional)")
        self.poll_priv_pass_edit.setEchoMode(QLineEdit.Password)
        v3_layout.addRow("Priv password:", self.poll_priv_pass_edit)
        layout.addWidget(self.v3_frame)
        self.v3_frame.setVisible(False)

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
        self.poll_result_edit.setMaximumHeight(120)
        self.poll_result_edit.setPlaceholderText("Poll results appear here")
        layout.addWidget(self.poll_result_edit)
        layout.addStretch()

        self._on_version_changed(self.poll_version_combo.currentText())

    def _on_version_changed(self, version: str):
        """Show/hide v3 options and community based on selected version."""
        is_v3 = version == "v3"
        self.v3_frame.setVisible(is_v3)
        self.community_frame.setVisible(not is_v3)
