#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Settings tabs for the Network Scanner plugin.
Returns (title, widget) list for the Plugin Manager.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QGroupBox,
    QCheckBox,
    QSpinBox,
    QMessageBox,
    QInputDialog,
)
from PySide6.QtGui import QIntValidator

from src.ui.plugin_ui_theme import PLUGIN_UI_SIZES


def get_settings_pages(plugin):
    """Build and return settings pages: list of (title, widget)."""
    main_settings = QWidget()
    main_layout = QVBoxLayout(main_settings)
    grid = PLUGIN_UI_SIZES["grid"]
    pad = PLUGIN_UI_SIZES["section_padding"]
    main_layout.setContentsMargins(pad, pad, pad, pad)
    main_layout.setSpacing(grid * 3)

    general_group = QGroupBox("General Settings")
    general_layout = QFormLayout(general_group)
    general_layout.setContentsMargins(pad, pad, pad, pad)
    general_layout.setSpacing(grid)
    general_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

    refresh_interfaces_layout = QHBoxLayout()
    refresh_interfaces_layout.setSpacing(8)
    interface_combo = QComboBox()
    interface_combo.addItems(plugin.settings["preferred_interface"]["choices"])
    interface_combo.setCurrentText(plugin.settings["preferred_interface"]["value"])
    refresh_interfaces_button = QPushButton("Refresh")
    refresh_interfaces_button.clicked.connect(plugin._update_interface_choices_and_refresh_ui)
    refresh_interfaces_layout.addWidget(interface_combo, 1)
    refresh_interfaces_layout.addWidget(refresh_interfaces_button)
    general_layout.addRow("Preferred Interface:", refresh_interfaces_layout)

    scan_type_combo = QComboBox()
    scan_type_combo.addItems(plugin.settings["scan_type"]["choices"])
    scan_type_combo.setCurrentText(plugin.settings["scan_type"]["value"])
    general_layout.addRow("Default Scan Type:", scan_type_combo)

    interface_combo.currentTextChanged.connect(lambda text: plugin.update_setting("preferred_interface", text))
    scan_type_combo.currentTextChanged.connect(lambda text: plugin.update_setting("scan_type", text))

    main_layout.addWidget(general_group)

    advanced_group = QGroupBox("Advanced Settings")
    advanced_layout = QFormLayout(advanced_group)
    advanced_layout.setContentsMargins(pad, pad, pad, pad)
    advanced_layout.setSpacing(grid)
    advanced_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

    elevated_check = QCheckBox()
    elevated_check.setChecked(plugin.settings["use_sudo"]["value"])
    elevated_check.toggled.connect(lambda state: plugin.update_setting("use_sudo", state))
    advanced_layout.addRow("Use Elevated Permissions:", elevated_check)

    custom_args_edit = QLineEdit(plugin.settings["custom_scan_args"]["value"])
    custom_args_edit.textChanged.connect(lambda text: plugin.update_setting("custom_scan_args", text))
    advanced_layout.addRow("Custom Arguments:", custom_args_edit)

    auto_tag_check = QCheckBox()
    auto_tag_check.setChecked(plugin.settings["auto_tag"]["value"])
    auto_tag_check.toggled.connect(lambda state: plugin.update_setting("auto_tag", state))
    advanced_layout.addRow("Auto Tag Devices:", auto_tag_check)

    batch_threads_spin = QSpinBox()
    batch_threads_spin.setRange(1, 8)
    batch_threads_spin.setValue(max(1, min(8, int(plugin.settings["batch_scan_threads"]["value"] or 1))))
    batch_threads_spin.setToolTip("Number of devices to scan in parallel during batch scans. 1 = sequential.")
    batch_threads_spin.valueChanged.connect(lambda v: plugin.update_setting("batch_scan_threads", v))
    advanced_layout.addRow("Batch scan threads:", batch_threads_spin)

    main_layout.addWidget(advanced_group)
    main_layout.addStretch(1)

    profiles_page = QWidget()
    profiles_page_layout = QVBoxLayout(profiles_page)
    profiles_page_layout.setContentsMargins(pad, pad, pad, pad)
    profiles_page_layout.setSpacing(grid)

    explanation_label = QLabel(
        "Scan profiles define different scanning configurations. "
        "Select a profile to view or edit its settings, or create a new profile."
    )
    explanation_label.setWordWrap(True)
    explanation_label.setStyleSheet("padding: 8px; background-color: palette(window); border-radius: 0px;")
    profiles_page_layout.addWidget(explanation_label)

    profiles_section = QWidget()
    profiles_section_layout = QVBoxLayout(profiles_section)
    profiles_section_layout.setContentsMargins(0, 0, 0, 0)
    profiles_section_layout.setSpacing(12)

    profiles_list_layout = QHBoxLayout()
    profiles_list_layout.setSpacing(10)
    profiles_list = QComboBox()
    profile_keys = list(plugin.settings["scan_profiles"]["value"].keys())
    profiles_list.addItems(profile_keys)
    profiles_list.addItem("--- Add New Profile ---")
    profiles_list_layout.addWidget(QLabel("Select Profile:"))
    profiles_list_layout.addWidget(profiles_list, 1)
    profiles_section_layout.addLayout(profiles_list_layout)

    profile_details_group = QGroupBox("Profile Details")
    profile_form = QFormLayout(profile_details_group)
    profile_form.setContentsMargins(pad, pad, pad, pad)
    profile_form.setSpacing(grid)
    profile_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

    profile_name = QLineEdit()
    profile_form.addRow("Display Name:", profile_name)
    profile_desc = QLineEdit()
    profile_desc.setPlaceholderText("Description of the scan profile")
    profile_form.addRow("Description:", profile_desc)
    profile_args = QLineEdit()
    profile_args.setPlaceholderText("nmap arguments, e.g. -sn -F")
    profile_form.addRow("Arguments:", profile_args)
    profile_timeout = QLineEdit()
    profile_timeout.setValidator(QIntValidator(30, 600))
    profile_form.addRow("Timeout (seconds):", profile_timeout)

    profiles_section_layout.addWidget(profile_details_group)

    buttons_layout = QHBoxLayout()
    save_button = QPushButton("Save Profile")
    delete_button = QPushButton("Delete Profile")
    buttons_layout.addWidget(save_button)
    buttons_layout.addWidget(delete_button)
    profiles_section_layout.addLayout(buttons_layout)
    profiles_page_layout.addWidget(profiles_section)
    profiles_page_layout.addStretch()

    def load_profile_data():
        profile_id = profiles_list.currentText()
        if profile_id == "--- Add New Profile ---":
            profile_name.setText("")
            profile_desc.setText("")
            profile_args.setText("-sn")
            profile_timeout.setText("300")
            delete_button.setEnabled(False)
            profile_name.setEnabled(True)
            profile_desc.setEnabled(True)
            profile_args.setEnabled(True)
            profile_timeout.setEnabled(True)
            save_button.setText("Create Profile")
            profile_details_group.setTitle("New Profile Details")
            return
        if profile_id in plugin.settings["scan_profiles"]["value"]:
            profile = plugin.settings["scan_profiles"]["value"][profile_id]
            profile_name.setText(profile.get("name", profile_id))
            profile_desc.setText(profile.get("description", ""))
            profile_args.setText(profile.get("arguments", ""))
            profile_timeout.setText(str(profile.get("timeout", 300)))
            is_builtin = profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]
            delete_button.setEnabled(not is_builtin)
            profile_name.setEnabled(True)
            profile_desc.setEnabled(True)
            profile_args.setEnabled(True)
            profile_timeout.setEnabled(True)
            save_button.setText("Update Profile")
            profile_details_group.setTitle("Edit Profile Details")

    profiles_list.currentTextChanged.connect(load_profile_data)
    load_profile_data()

    def save_profile():
        profile_id = profiles_list.currentText()
        if profile_id == "--- Add New Profile ---":
            new_id, ok = QInputDialog.getText(
                profiles_page,
                "New Profile",
                "Enter a unique profile ID (lowercase, no spaces):",
                text="custom_scan",
            )
            if not ok or not new_id:
                return
            new_id = new_id.lower().strip().replace(" ", "_")
            if new_id in plugin.settings["scan_profiles"]["value"]:
                QMessageBox.warning(
                    profiles_page,
                    "Profile Exists",
                    f"A profile with ID '{new_id}' already exists. Please choose a different ID.",
                )
                return
            profile_id = new_id
        name = profile_name.text()
        description = profile_desc.text()
        arguments = profile_args.text()
        try:
            timeout = int(profile_timeout.text())
            timeout = max(30, min(600, timeout))
        except ValueError:
            timeout = 300
        updated_profile = {"name": name, "description": description, "arguments": arguments, "timeout": timeout}
        profiles = plugin.settings["scan_profiles"]["value"].copy()
        profiles[profile_id] = updated_profile
        plugin.update_setting("scan_profiles", profiles)
        if profile_id not in plugin.settings["scan_type"]["choices"]:
            choices = list(plugin.settings["scan_type"]["choices"])
            choices.append(profile_id)
            plugin.settings["scan_type"]["choices"] = choices
            scan_type_combo.clear()
            scan_type_combo.addItems(choices)
        if profiles_list.findText(profile_id) == -1:
            profiles_list.clear()
            profiles_list.addItems(list(plugin.settings["scan_profiles"]["value"].keys()))
            profiles_list.addItem("--- Add New Profile ---")
            profiles_list.setCurrentText(profile_id)
        action = "created" if profile_id != profiles_list.currentText() else "updated"
        QMessageBox.information(profiles_page, "Profile Saved", f"The profile '{profile_id}' has been {action}.")

    def delete_profile():
        profile_id = profiles_list.currentText()
        if profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]:
            QMessageBox.warning(profiles_page, "Cannot Delete", "Built-in profiles cannot be deleted.")
            return
        if profile_id == "--- Add New Profile ---":
            return
        if QMessageBox.question(
            profiles_page,
            "Confirm Deletion",
            f"Are you sure you want to delete the profile '{profile_id}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        profiles = plugin.settings["scan_profiles"]["value"].copy()
        if profile_id in profiles:
            del profiles[profile_id]
            plugin.update_setting("scan_profiles", profiles)
            if profile_id in plugin.settings["scan_type"]["choices"]:
                choices = list(plugin.settings["scan_type"]["choices"])
                choices.remove(profile_id)
                plugin.settings["scan_type"]["choices"] = choices
                scan_type_combo.clear()
                scan_type_combo.addItems(choices)
            profiles_list.clear()
            profiles_list.addItems(list(plugin.settings["scan_profiles"]["value"].keys()))
            profiles_list.addItem("--- Add New Profile ---")
            QMessageBox.information(profiles_page, "Profile Deleted", f"The profile '{profile_id}' has been deleted.")

    save_button.clicked.connect(save_profile)
    delete_button.clicked.connect(delete_profile)

    return [("General", main_settings), ("Scan Profiles", profiles_page)]
