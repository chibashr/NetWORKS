# -*- coding: utf-8 -*-
"""
Manage Reports dialog: list reports, New/Duplicate/Delete, switch selection.
Calls back into the ReportBuilderWidget for create/duplicate/delete/select.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from src.ui.plugin_ui_theme import mark_plugin_ui


def show_manage_reports_dialog(parent, builder_widget):
    """Show the Manage Reports dialog; parent is the widget parent, builder_widget is the ReportBuilderWidget."""
    dialog = ManageReportsDialog(parent, builder_widget)
    dialog.exec()


class ManageReportsDialog(QDialog):
    """Dialog to list, create, duplicate, delete, and switch reports via the builder widget."""

    def __init__(self, parent, builder_widget):
        super().__init__(parent)
        self._builder = builder_widget
        mark_plugin_ui(self)
        self.setWindowTitle("Manage Reports")
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        layout.addWidget(self._list)

        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        button_row = QHBoxLayout()
        new_btn = QPushButton("New")
        dup_btn = QPushButton("Duplicate")
        del_btn = QPushButton("Delete")
        button_row.addWidget(new_btn)
        button_row.addWidget(dup_btn)
        button_row.addWidget(del_btn)
        layout.addLayout(button_row)

        new_btn.clicked.connect(self._on_new)
        dup_btn.clicked.connect(self._on_duplicate)
        del_btn.clicked.connect(self._on_delete)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_list()

    def _refresh_list(self):
        self._list.clear()
        for report in self._builder.reports:
            item = QListWidgetItem(report.get("name", "Unnamed Report"))
            item.setData(Qt.UserRole, report.get("id"))
            self._list.addItem(item)
        current_id = self._builder.current_report_id
        if current_id:
            for row in range(self._list.count()):
                item = self._list.item(row)
                if item.data(Qt.UserRole) == current_id:
                    self._list.setCurrentRow(row)
                    break

    def _on_selection_changed(self):
        selected = self._list.selectedItems()
        if not selected:
            return
        report_id = selected[0].data(Qt.UserRole)
        self._builder._select_report(report_id)

    def _on_new(self):
        self._builder.create_report()
        self._refresh_list()

    def _on_duplicate(self):
        self._builder.duplicate_report()
        self._refresh_list()

    def _on_delete(self):
        self._builder.delete_report()
        self._refresh_list()
