#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Reusable Ingestion widget for SNMP Collector (testing with pasted JSON).
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
)
from PySide6.QtCore import Qt

from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES


class IngestionWidget(QWidget):
    """Widget for pasting JSON trap data to simulate traps."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.plugin = plugin

        layout = QVBoxLayout(self)
        layout.setSpacing(PLUGIN_UI_SIZES["grid"])
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Paste JSON trap(s) to simulate:"))
        self.ingest_edit = QTextEdit()
        self.ingest_edit.setPlaceholderText(
            '{"agent_address": "192.168.1.1", "varbinds": [{"oid": "1.1.1", "value": "test"}]}'
        )
        self.ingest_edit.setMaximumHeight(80)
        layout.addWidget(self.ingest_edit)
        self.ingest_btn = QPushButton("Ingest")
        self.ingest_btn.setToolTip("Add pasted JSON as simulated trap(s)")
        self.ingest_btn.clicked.connect(lambda: plugin._on_ingest_clicked(self))
        layout.addWidget(self.ingest_btn)
