#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Template Manager Plugin for NetWORKS.
Creates reusable command templates from device outputs using Report Generator–style
variable binding ({{property_name}}), stores them per workspace, and exports
populated commands to file or sends them to Command Manager for execution.
Opens as a dialog from the toolbar or Tools menu (no dock panel).
"""

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QStyle, QMessageBox

from src.core.plugin_interface import PluginInterface
from src.ui.plugin_ui_theme import mark_plugin_ui
from src.ui.material_icons import material_icon
from plugins.template_manager.core.template_storage import TemplateStorage
from plugins.template_manager.ui.template_manager_dialog import TemplateManagerDialog


class TemplateManagerPlugin(PluginInterface):
    """Template Manager: template authoring and export / Load into Command Manager."""

    CONTEXT_ACTION_NAME = "Export template for…"

    def __init__(self):
        super().__init__()
        self.storage = None
        self.menu_action = None
        self.toolbar_action = None

    def initialize(self, app, plugin_info):
        self.app = app
        self.plugin_info = plugin_info
        self.main_window = app.main_window
        self.device_manager = app.device_manager

        self.storage = TemplateStorage(self.device_manager)
        self.storage.ensure_loaded()

        self._register_actions()
        self._register_context_menu()
        self._initialized = True
        self.plugin_initialized.emit()
        logger.info("Template Manager plugin initialized")
        return True

    def _register_actions(self):
        self.menu_action = QAction("Template Manager", self.main_window)
        self.menu_action.setToolTip("Open Template Manager")
        self.menu_action.triggered.connect(self._show_dialog)
        self.toolbar_action = QAction("Template Manager", self.main_window)
        self.toolbar_action.setToolTip("Open Template Manager")
        self.toolbar_action.triggered.connect(self._show_dialog)
        if self.main_window:
            self.toolbar_action.setIcon(
                material_icon("description", self.main_window, QStyle.SP_FileDialogDetailedView)
            )

    def _register_context_menu(self):
        if hasattr(self.main_window, "device_table") and self.main_window.device_table:
            self.main_window.device_table.register_context_menu_action(
                self.CONTEXT_ACTION_NAME,
                self._on_export_template_for_devices,
                priority=565,
            )

    def _on_export_template_for_devices(self, devices):
        if not devices:
            return
        devices = [devices] if not isinstance(devices, list) else devices
        templates = self.storage.ensure_loaded()
        if not templates:
            QMessageBox.information(
                self.main_window,
                "Export template for…",
                "No templates. Open Template Manager to create some.",
            )
            return
        from plugins.template_manager.ui.batch_export_dialog import BatchExportDialog
        dialog = BatchExportDialog(self, templates, initial_devices=devices, parent=self.main_window)
        dialog.exec()

    def _show_dialog(self):
        if not self.main_window:
            return
        dialog = TemplateManagerDialog(self, parent=self.main_window)
        dialog.exec()

    def get_toolbar_actions(self):
        return [self.toolbar_action] if self.toolbar_action else []

    def get_menu_actions(self):
        if not self.menu_action:
            return {}
        return {"Tools": [self.menu_action]}

    def get_dock_widgets(self):
        return []

    def cleanup(self):
        if hasattr(self.main_window, "device_table") and self.main_window.device_table:
            try:
                self.main_window.device_table.unregister_context_menu_action(self.CONTEXT_ACTION_NAME)
            except Exception:
                pass
        self.storage = None
        return super().cleanup()


__all__ = ["TemplateManagerPlugin"]
