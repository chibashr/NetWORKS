#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Report Generator Plugin for NetWORKS.
"""

from loguru import logger
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QStyle

from src.core.plugin_interface import PluginInterface
from src.ui.material_icons import material_icon

from core.report_storage import ReportStorage
from ui.report_builder_dialog import ReportBuilderDialog


class ReportGeneratorPlugin(PluginInterface):
    def __init__(self):
        super().__init__()
        self.storage = None
        self.actions = []
        self.toolbar_action = None
        self.menu_action = None
        self.context_action_name = "Generate Report"

    def initialize(self, app, plugin_info):
        self.app = app
        self.plugin_info = plugin_info
        self.main_window = app.main_window
        self.device_manager = app.device_manager

        self.storage = ReportStorage(self.device_manager)
        self.storage.ensure_loaded()

        self._register_actions()
        self._register_context_menu()

        self._initialized = True
        self.plugin_initialized.emit()
        logger.info("Report Generator plugin initialized")
        return True

    def _register_actions(self):
        tooltip = "Open the Report Generator to build and export device reports"
        self.menu_action = QAction("Report Generator", self.main_window)
        self.menu_action.setToolTip(tooltip)
        self.menu_action.triggered.connect(self.show_report_dialog)
        self.toolbar_action = QAction("Report Generator", self.main_window)
        self.toolbar_action.setToolTip(tooltip)
        self.toolbar_action.triggered.connect(self.show_report_dialog)
        if self.main_window:
            self.toolbar_action.setIcon(
                material_icon("description", self.main_window, QStyle.SP_FileDialogDetailedView)
            )
        self.actions = [self.menu_action]
        return True

    def _register_context_menu(self):
        if hasattr(self.main_window, "device_table"):
            self.main_window.device_table.register_context_menu_action(
                self.context_action_name,
                self.show_report_dialog_for_selection,
                priority=560,
            )

    def _connect_signals(self):
        self.device_manager.device_added.connect(self.on_device_added)
        self.device_manager.device_removed.connect(self.on_device_removed)
        self.device_manager.device_changed.connect(self.on_device_changed)
        self.device_manager.group_added.connect(self.on_group_added)
        self.device_manager.group_removed.connect(self.on_group_removed)
        self._connected_signals.update(
            {"device_added", "device_removed", "device_changed", "group_added", "group_removed"}
        )

    def get_toolbar_actions(self):
        return [self.toolbar_action] if self.toolbar_action else []

    def get_menu_actions(self):
        return {"Tools": [self.menu_action]} if self.menu_action else {}

    def get_dock_widgets(self):
        return []

    def show_report_dialog(self):
        dialog = ReportBuilderDialog(self, parent=self.main_window)
        dialog.exec()

    def show_report_dialog_for_selection(self, devices):
        dialog = ReportBuilderDialog(self, prefill_source="Selected Devices", parent=self.main_window)
        dialog.exec()

    def cleanup(self):
        if hasattr(self.main_window, "device_table"):
            try:
                self.main_window.device_table.unregister_context_menu_action(self.context_action_name)
            except Exception as exc:
                logger.debug(f"Report Generator: context menu cleanup failed: {exc}")
        return super().cleanup()


__all__ = ["ReportGeneratorPlugin"]
