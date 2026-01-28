# -*- coding: utf-8 -*-
"""
Report Builder dialog: wraps ReportBuilderWidget with a Close button.
"""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from src.ui.plugin_ui_theme import mark_plugin_ui

from ui.report_builder_widget import ReportBuilderWidget


class ReportBuilderDialog(QDialog):
    """Dialog that hosts the Report Builder widget and a Close button."""

    def __init__(self, plugin, prefill_source=None, parent=None):
        super().__init__(parent or plugin.main_window)
        mark_plugin_ui(self)
        self.setWindowTitle("Report Generator")
        self.setMinimumSize(1200, 700)
        self.resize(1420, 860)

        layout = QVBoxLayout(self)
        self.builder = ReportBuilderWidget(plugin, self)
        layout.addWidget(self.builder)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if prefill_source:
            self.builder.source_combo.setCurrentText(prefill_source)
