#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Picker dialog to choose command output from Command Manager as template body.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QPushButton,
    QMessageBox,
)

from src.ui.plugin_ui_theme import mark_plugin_ui
from plugins.template_manager.core.device_utils import device_display_name


class CommandOutputPickerDialog(QDialog):
    """List device + command outputs; user picks one, we return its output text."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent or plugin.main_window)
        mark_plugin_ui(self)
        self.setWindowTitle("Load from Command Manager")
        self.plugin = plugin
        self._chosen_output = None
        self._all_items = []  # list of (label, output_text) for filtering
        self.setMinimumSize(460, 400)
        self._build_ui()
        self._load_outputs()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a saved command output to use as template source:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search device or command…")
        self.search_edit.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_edit)
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(220)
        self.list_widget.itemDoubleClicked.connect(self._on_use)
        layout.addWidget(self.list_widget)
        btn_row = QHBoxLayout()
        use_btn = QPushButton("Use as source")
        use_btn.clicked.connect(self._on_use)
        btn_row.addWidget(use_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_outputs(self):
        """Fill list from Command Manager get_command_outputs for all devices."""
        self.list_widget.clear()
        self._all_items = []
        app = getattr(self.plugin, "app", None)
        pm = getattr(app, "plugin_manager", None) if app else None
        info = pm.get_plugin("command_manager") if pm else None
        if not info or not getattr(info, "instance", None):
            self.list_widget.addItem(QListWidgetItem("(Command Manager plugin not loaded)"))
            return
        cmd_mgr = info.instance
        dm = self.plugin.device_manager
        devices = dm.get_devices() or []
        for device in devices:
            dev_id = getattr(device, "id", None) or ""
            outs = cmd_mgr.get_command_outputs(dev_id) if hasattr(cmd_mgr, "get_command_outputs") else {}
            if not isinstance(outs, dict):
                continue
            for cmd_id, timestamps in outs.items():
                if not isinstance(timestamps, dict):
                    continue
                for ts, rec in timestamps.items():
                    out_text = (rec.get("output") or "").strip() if isinstance(rec, dict) else ""
                    if not out_text:
                        continue
                    label = f"{device_display_name(device)} — {cmd_id}"
                    self._all_items.append((label, out_text))
        for label, out_text in self._all_items:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, out_text)
            self.list_widget.addItem(item)
        self._filter_list()
        if not self._all_items:
            self.list_widget.addItem(QListWidgetItem("(No saved command outputs in Command Manager)"))

    def _filter_list(self):
        q = (self.search_edit.text() or "").strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item or not item.data(Qt.UserRole):
                continue
            label = (item.text() or "").lower()
            item.setHidden(bool(q) and q not in label)

    def _on_use(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.information(self, "Load from Command Manager", "Select an output first.")
            return
        self._chosen_output = item.data(Qt.UserRole)
        if self._chosen_output is not None:
            self.accept()

    def chosen_output(self):
        return self._chosen_output
