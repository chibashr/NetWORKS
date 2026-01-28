#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Scan Type Manager dialog for the Network Scanner plugin.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QWidget,
    QMessageBox,
    QHeaderView,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator

from src.ui.plugin_widgets import PluginDialogBase
from src.ui.plugin_ui_theme import mark_plugin_ui


def show_scan_type_manager_dialog(plugin):
    """Show the Scan Type Manager dialog."""
    dialog = PluginDialogBase("Scan Type Manager", plugin.main_window, use_tabs=False)
    dialog.setMinimumWidth(600)
    dialog.setMinimumHeight(500)

    content = QWidget()
    mark_plugin_ui(content)
    layout = QVBoxLayout(content)
    pad = 8
    layout.setContentsMargins(pad, pad, pad, pad)
    layout.setSpacing(8)

    description_label = QLabel(
        "Manage your scan profiles. You can create new profiles, edit existing ones, or delete custom profiles."
    )
    description_label.setWordWrap(True)
    mark_plugin_ui(description_label)
    layout.addWidget(description_label)

    profile_table = QTableWidget()
    profile_table.setColumnCount(3)
    profile_table.setHorizontalHeaderLabels(["Name", "Description", "Arguments"])
    profile_table.horizontalHeader().setStretchLastSection(True)
    profile_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    profile_table.setSelectionBehavior(QTableWidget.SelectRows)
    profile_table.setSelectionMode(QTableWidget.SingleSelection)
    layout.addWidget(profile_table)

    def refresh_table():
        profile_table.setRowCount(0)
        profiles = plugin.settings["scan_profiles"]["value"]
        for i, (profile_id, profile) in enumerate(profiles.items()):
            is_builtin = profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]
            profile_table.insertRow(i)
            name_item = QTableWidgetItem(profile.get("name", profile_id))
            if is_builtin:
                name_item.setToolTip("Built-in profile (can't be deleted)")
                name_item.setBackground(profile_table.palette().alternateBase())
            name_item.setData(Qt.UserRole, profile_id)
            profile_table.setItem(i, 0, name_item)
            profile_table.setItem(i, 1, QTableWidgetItem(profile.get("description", "")))
            profile_table.setItem(i, 2, QTableWidgetItem(profile.get("arguments", "")))
        profile_table.resizeColumnsToContents()
        if profile_table.columnWidth(1) < 150:
            profile_table.setColumnWidth(1, 150)

    refresh_table()

    def edit_profile_dialog(profile_id=None, is_new=False):
        edit_dialog = QDialog(dialog)
        mark_plugin_ui(edit_dialog)
        edit_dialog.setWindowTitle("New Scan Profile" if is_new else "Edit Scan Profile")
        edit_dialog.setMinimumWidth(450)
        edit_layout = QVBoxLayout(edit_dialog)
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        profile_id_edit = QLineEdit()
        if is_new:
            form_layout.addRow("Profile ID:", profile_id_edit)
            profile_id_edit.setPlaceholderText("e.g., custom_scan (no spaces, lowercase)")
        profile_name_edit = QLineEdit()
        form_layout.addRow("Display Name:", profile_name_edit)
        profile_desc_edit = QLineEdit()
        form_layout.addRow("Description:", profile_desc_edit)
        profile_args_edit = QLineEdit()
        profile_args_edit.setPlaceholderText("e.g., -sn -F")
        form_layout.addRow("Arguments:", profile_args_edit)
        profile_timeout_edit = QLineEdit()
        profile_timeout_edit.setValidator(QIntValidator(30, 600))
        form_layout.addRow("Timeout (seconds):", profile_timeout_edit)
        if not is_new and profile_id:
            profile = plugin.settings["scan_profiles"]["value"].get(profile_id, {})
            profile_name_edit.setText(profile.get("name", ""))
            profile_desc_edit.setText(profile.get("description", ""))
            profile_args_edit.setText(profile.get("arguments", ""))
            profile_timeout_edit.setText(str(profile.get("timeout", 300)))
        edit_layout.addLayout(form_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(edit_dialog.accept)
        button_box.rejected.connect(edit_dialog.reject)
        edit_layout.addWidget(button_box)

        if edit_dialog.exec() == QDialog.Accepted:
            if is_new:
                new_id = profile_id_edit.text().strip().lower().replace(" ", "_")
                if not new_id:
                    QMessageBox.warning(dialog, "Invalid ID", "Profile ID cannot be empty.")
                    return
                if new_id in plugin.settings["scan_profiles"]["value"]:
                    QMessageBox.warning(dialog, "Profile Exists", f"A profile with ID '{new_id}' already exists.")
                    return
                profile_id = new_id
            updated_profile = {
                "name": profile_name_edit.text(),
                "description": profile_desc_edit.text(),
                "arguments": profile_args_edit.text(),
                "timeout": int(profile_timeout_edit.text() or "300"),
            }
            profiles = plugin.settings["scan_profiles"]["value"].copy()
            profiles[profile_id] = updated_profile
            plugin.settings["scan_profiles"]["value"] = profiles
            if profile_id not in plugin.settings["scan_type"]["choices"]:
                choices = list(plugin.settings["scan_type"]["choices"])
                choices.append(profile_id)
                plugin.settings["scan_type"]["choices"] = choices
                if hasattr(plugin, "scan_type_combo") and plugin.scan_type_combo is not None:
                    current_text = plugin.scan_type_combo.currentText()
                    plugin.scan_type_combo.clear()
                    plugin.scan_type_combo.addItems(choices)
                    if current_text in choices:
                        plugin.scan_type_combo.setCurrentText(current_text)
            refresh_table()
            return True
        return False

    def on_new_profile():
        edit_profile_dialog(is_new=True)

    def on_edit_profile():
        selected_indexes = profile_table.selectedIndexes()
        if not selected_indexes:
            return
        row = selected_indexes[0].row()
        profile_id = profile_table.item(row, 0).data(Qt.UserRole)
        edit_profile_dialog(profile_id, is_new=False)

    def on_delete_profile():
        selected_indexes = profile_table.selectedIndexes()
        if not selected_indexes:
            return
        row = selected_indexes[0].row()
        profile_id = profile_table.item(row, 0).data(Qt.UserRole)
        if profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]:
            QMessageBox.warning(dialog, "Cannot Delete", "Built-in profiles cannot be deleted.")
            return
        if QMessageBox.question(
            dialog,
            "Confirm Deletion",
            f"Are you sure you want to delete the profile '{profile_id}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        profiles = plugin.settings["scan_profiles"]["value"].copy()
        if profile_id in profiles:
            del profiles[profile_id]
        plugin.settings["scan_profiles"]["value"] = profiles
        if profile_id in plugin.settings["scan_type"]["choices"]:
            choices = list(plugin.settings["scan_type"]["choices"])
            choices.remove(profile_id)
            plugin.settings["scan_type"]["choices"] = choices
            if hasattr(plugin, "scan_type_combo") and plugin.scan_type_combo is not None:
                current_text = plugin.scan_type_combo.currentText()
                plugin.scan_type_combo.clear()
                plugin.scan_type_combo.addItems(choices)
                if current_text in choices:
                    plugin.scan_type_combo.setCurrentText(current_text)
                elif choices:
                    plugin.scan_type_combo.setCurrentIndex(0)
                if plugin.scan_type_combo.count() > 0:
                    plugin.scan_type_combo.currentIndexChanged.emit(plugin.scan_type_combo.currentIndex())
        refresh_table()

    dialog.main_layout.insertWidget(0, content)

    edit_btn = dialog.add_action_button("Edit Profile", on_edit_profile)
    delete_btn = dialog.add_action_button("Delete Profile", on_delete_profile)
    dialog.add_action_button("New Profile", on_new_profile)
    dialog.add_action_button("Close", dialog.reject)
    edit_btn.setEnabled(False)
    delete_btn.setEnabled(False)

    def on_selection_changed():
        selected_indexes = profile_table.selectedIndexes()
        if selected_indexes:
            row = selected_indexes[0].row()
            profile_id = profile_table.item(row, 0).data(Qt.UserRole)
            is_builtin = profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]
            edit_btn.setEnabled(True)
            delete_btn.setEnabled(not is_builtin)
        else:
            edit_btn.setEnabled(False)
            delete_btn.setEnabled(False)

    profile_table.itemSelectionChanged.connect(on_selection_changed)

    def on_double_click(item):
        row = item.row()
        profile_id = profile_table.item(row, 0).data(Qt.UserRole)
        edit_profile_dialog(profile_id, is_new=False)

    profile_table.itemDoubleClicked.connect(on_double_click)
    dialog.exec()
