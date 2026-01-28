#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Custom command UI and safety check for the Command Dialog.
"""

from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
)


def create_custom_command_section(parent):
    """Build the custom command group (button + show-only checkbox).

    Returns:
        tuple: (group_box, dict with keys 'open_custom_dialog_btn', 'show_only_check')
    """
    custom_command_group = QGroupBox("Custom Commands")
    custom_command_layout = QVBoxLayout(custom_command_group)

    custom_btn_layout = QHBoxLayout()
    open_custom_dialog_btn = QPushButton("Custom Commands…")
    show_only_check = QCheckBox("Allow 'show' commands only")
    show_only_check.setChecked(True)
    show_only_check.setToolTip(
        "When checked, only commands starting with 'show' will be allowed"
    )

    custom_btn_layout.addWidget(open_custom_dialog_btn)
    custom_btn_layout.addWidget(show_only_check)
    custom_command_layout.addLayout(custom_btn_layout)

    return custom_command_group, {
        "open_custom_dialog_btn": open_custom_dialog_btn,
        "show_only_check": show_only_check,
    }


def is_custom_command_allowed(command_text, show_only_checked):
    """Return True if the command is allowed; False if user declined confirmation.

    For non-show commands when show_only_checked is True, the caller should show
    a confirmation dialog and pass the result here, or handle confirmation externally.
    This helper just answers whether the raw text would be blocked when show_only is on.
    """
    if not command_text or not command_text.strip():
        return False, "empty"
    if show_only_checked and not command_text.strip().lower().startswith("show "):
        return False, "non_show"
    return True, None
