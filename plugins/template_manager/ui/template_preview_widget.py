#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Preview widget for Template Manager: device combo and rendered output with optional
"select in editor" via a signal. Used by TemplateManagerPanel to reduce file length.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QTextEdit,
)

from src.ui.plugin_ui_theme import mark_plugin_ui
from plugins.template_manager.core.device_utils import device_display_name
from plugins.template_manager.core.template_engine import render_template_text_to_html


class TemplatePreviewWidget(QWidget):
    """
    Device combo and read-only rendered preview. Emits selection_in_preview_triggered(plain_text)
    when the user selects text so the panel can locate it in the body editor.
    """

    selection_in_preview_triggered = Signal(str)

    def __init__(self, plugin, body_edit=None, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.setMinimumWidth(400)
        self._plugin = plugin
        self._body_edit = body_edit
        self._build_ui()
        if body_edit is not None:
            body_edit.textChanged.connect(self.refresh_preview)
        self._combo.currentIndexChanged.connect(self.refresh_preview)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        group = QGroupBox("Preview")
        inner = QVBoxLayout(group)
        inner.addWidget(QLabel("Device:"))
        self._combo = QComboBox()
        self._combo.setMinimumWidth(200)
        inner.addWidget(self._combo)
        inner.addWidget(QLabel("Rendered output:"))
        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setPlaceholderText(
            "Select a device to see template rendered with its data. "
            "Select text here to locate it in the editor."
        )
        self._preview_text.selectionChanged.connect(self._on_selection_changed)
        inner.addWidget(self._preview_text)
        layout.addWidget(group)

    def _on_selection_changed(self):
        """Emit selected plain text so the panel can select the first occurrence in the body editor."""
        cursor = self._preview_text.textCursor()
        if not cursor.hasSelection():
            return
        sel = cursor.selectedText()
        if not sel or sel.startswith("\u2029"):
            return
        plain = sel.replace("\u2029", "\n")
        self.selection_in_preview_triggered.emit(plain)

    def refresh_devices(self):
        """Populate device combo from plugin's device manager."""
        dm = getattr(self._plugin, "device_manager", None)
        self._combo.clear()
        self._combo.addItem("(No device)", None)
        if dm:
            for d in (dm.get_devices() or []):
                name = device_display_name(d)
                self._combo.addItem(name, d)
        self.refresh_preview()

    def refresh_preview(self):
        """Render body with current device and show in preview. Body comes from body_edit if set."""
        body = (self._body_edit.toPlainText().strip() if self._body_edit else "") or ""
        device = self._combo.currentData()
        if not body or not device:
            self._preview_text.setPlainText(
                body or "(Enter template body and select a device.)"
            )
            return
        ctx = dict(device.get_properties() or {})
        try:
            html_out = render_template_text_to_html(body, ctx)
            self._preview_text.setHtml(html_out)
        except Exception:
            self._preview_text.setPlainText("(Preview error)")
