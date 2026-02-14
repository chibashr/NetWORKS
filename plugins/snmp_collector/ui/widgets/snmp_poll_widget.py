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
    QProgressBar,
)
from PySide6.QtCore import Qt

from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES

from ..dialogs.trap_receiver_dialog import TrapReceiverDialog

# Standard high-level OIDs (MIB-II system group and common tables)
STANDARD_OIDS = [
    ("Custom (manual)", ""),
    ("sysDescr", "1.3.6.1.2.1.1.1.0"),
    ("sysUpTime", "1.3.6.1.2.1.1.3.0"),
    ("sysName", "1.3.6.1.2.1.1.5.0"),
    ("sysObjectID", "1.3.6.1.2.1.1.2.0"),
    ("sysContact", "1.3.6.1.2.1.1.4.0"),
    ("sysLocation", "1.3.6.1.2.1.1.6.0"),
    ("sysServices", "1.3.6.1.2.1.1.7.0"),
    ("interfaces (ifTable)", "1.3.6.1.2.1.2.2"),
    ("ipAddrTable", "1.3.6.1.2.1.4.20"),
]


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

        self.poll_oid_combo = QComboBox()
        for label, oid in STANDARD_OIDS:
            self.poll_oid_combo.addItem(label, oid)
        self.poll_oid_combo.currentIndexChanged.connect(self._on_oid_combo_changed)
        poll_form.addRow("Preset OID:", self.poll_oid_combo)
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
        self.trap_receiver_btn = QPushButton("Trap Receiver")
        self.trap_receiver_btn.setToolTip("Configure and start/stop SNMP trap receiver")
        self.trap_receiver_btn.clicked.connect(self._on_trap_receiver_clicked)
        poll_btn_row.addWidget(self.trap_receiver_btn)
        poll_btn_row.addStretch()
        self.poll_get_btn = QPushButton("GET")
        self.poll_get_btn.setToolTip("SNMP GET")
        self.poll_get_btn.clicked.connect(lambda: plugin._on_poll_get_clicked(self))
        self.poll_getnext_btn = QPushButton("GETNEXT")
        self.poll_getnext_btn.setToolTip("SNMP GETNEXT")
        self.poll_getnext_btn.clicked.connect(lambda: plugin._on_poll_getnext_clicked(self))
        poll_btn_row.addWidget(self.poll_get_btn)
        poll_btn_row.addWidget(self.poll_getnext_btn)
        layout.addLayout(poll_btn_row)

        # Progress bar and log together (no separator)
        self.poll_progress = QProgressBar()
        self.poll_progress.setRange(0, 0)  # indeterminate while polling
        self.poll_progress.setMaximumHeight(6)
        self.poll_progress.setVisible(False)
        mark_plugin_ui(self.poll_progress)
        layout.addWidget(self.poll_progress)

        self.poll_result_edit = QTextEdit()
        self.poll_result_edit.setReadOnly(True)
        self.poll_result_edit.setMinimumHeight(180)
        self.poll_result_edit.setStyleSheet("font-size: 9px;")
        self.poll_result_edit.setPlaceholderText("Log output appears here")
        mark_plugin_ui(self.poll_result_edit)
        layout.addWidget(self.poll_result_edit, 1)

        self._on_version_changed(self.poll_version_combo.currentText())

    def _on_version_changed(self, version: str):
        """Show/hide v3 options and community based on selected version."""
        is_v3 = version == "v3"
        self.v3_frame.setVisible(is_v3)
        self.community_frame.setVisible(not is_v3)

    def _on_oid_combo_changed(self, index: int):
        """When a preset OID is selected, fill the OID edit; Custom leaves it for manual entry."""
        oid = self.poll_oid_combo.itemData(index)
        if oid:
            self.poll_oid_edit.setText(oid)
        else:
            self.poll_oid_edit.clear()

    def _on_trap_receiver_clicked(self):
        """Open trap receiver config dialog."""
        dlg = TrapReceiverDialog(self.plugin, self.window())
        dlg.exec()
