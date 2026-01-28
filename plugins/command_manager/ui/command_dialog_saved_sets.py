#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Helpers for the Saved Command Sets combo in the Command Dialog.
"""


def load_saved_command_sets_into_dialog(dialog):
    """Populate the dialog's saved_sets_combo from the plugin (persistent + temporary) and update run_saved_set_btn."""
    dialog.saved_sets_combo.blockSignals(True)
    current_set = dialog.saved_sets_combo.currentText()
    dialog.saved_sets_combo.clear()
    dialog.saved_sets_combo.addItem("-- Select Command Set --")
    dialog.temporary_saved_set_names = set()
    if hasattr(dialog.plugin, "get_saved_command_sets"):
        command_sets = dialog.plugin.get_saved_command_sets()
        if command_sets:
            for set_name in sorted(command_sets.keys()):
                dialog.saved_sets_combo.addItem(set_name)
    if hasattr(dialog.plugin, "get_temporary_saved_set_names"):
        for set_name in sorted(dialog.plugin.get_temporary_saved_set_names()):
            dialog.saved_sets_combo.addItem(set_name)
            dialog.temporary_saved_set_names.add(set_name)
    index = dialog.saved_sets_combo.findText(current_set)
    if index >= 0:
        dialog.saved_sets_combo.setCurrentIndex(index)
    else:
        dialog.saved_sets_combo.setCurrentIndex(0)
    dialog.run_saved_set_btn.setEnabled(dialog.saved_sets_combo.currentIndex() > 0)
    dialog.saved_sets_combo.blockSignals(False)
