#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Action creation for main window menus and toolbar.
Call create_actions(main_window) during MainWindow init.
"""

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QStyle

from .material_icons import material_icon


def create_actions(mw):
    """Create and attach menu/toolbar actions to the main window."""
    mw.action_new_device = QAction("New Device", mw)
    mw.action_new_device.setIcon(material_icon("devices", mw, QStyle.SP_ComputerIcon))
    mw.action_new_device.setStatusTip("Create a new device")
    mw.action_new_device.triggered.connect(mw.on_new_device)

    mw.action_new_group = QAction("New Group", mw)
    mw.action_new_group.setIcon(material_icon("create_new_folder", mw, QStyle.SP_DirIcon))
    mw.action_new_group.setStatusTip("Create a new device group")
    mw.action_new_group.triggered.connect(mw.on_new_group)

    mw.action_import_devices = QAction("Import Devices", mw)
    mw.action_import_devices.setIcon(material_icon("file_upload", mw, QStyle.SP_DialogOpenButton))
    mw.action_import_devices.setStatusTip("Import devices from a file")
    mw.action_import_devices.triggered.connect(mw.on_import_devices)

    mw.action_save = QAction("Save", mw)
    mw.action_save.setIcon(material_icon("save", mw, QStyle.SP_DialogSaveButton))
    mw.action_save.setShortcut(QKeySequence.Save)
    mw.action_save.setStatusTip("Save all devices")
    mw.action_save.triggered.connect(mw.on_save)

    mw.action_save_workspace = QAction("Save Workspace", mw)
    mw.action_save_workspace.setStatusTip("Save current workspace")
    mw.action_save_workspace.triggered.connect(mw.on_save_workspace)

    mw.action_manage_workspaces = QAction("Manage Workspaces", mw)
    mw.action_manage_workspaces.setStatusTip("Manage workspaces")
    mw.action_manage_workspaces.triggered.connect(mw.on_manage_workspaces)

    mw.action_exit = QAction("Exit", mw)
    mw.action_exit.setShortcut(QKeySequence.Quit)
    mw.action_exit.setStatusTip("Exit the application")
    mw.action_exit.triggered.connect(mw.close)

    mw.action_select_all = QAction("Select All", mw)
    mw.action_select_all.setShortcut(QKeySequence.SelectAll)
    mw.action_select_all.setStatusTip("Select all devices")
    mw.action_select_all.triggered.connect(mw.on_select_all)

    mw.action_deselect_all = QAction("Deselect All", mw)
    mw.action_deselect_all.setStatusTip("Deselect all devices")
    mw.action_deselect_all.triggered.connect(mw.on_deselect_all)

    mw.action_delete = QAction("Delete", mw)
    mw.action_delete.setShortcut(QKeySequence.Delete)
    mw.action_delete.setStatusTip("Delete selected devices")
    mw.action_delete.triggered.connect(mw.on_delete)

    mw.action_refresh = QAction("Refresh", mw)
    mw.action_refresh.setIcon(material_icon("refresh", mw, QStyle.SP_BrowserReload))
    mw.action_refresh.setShortcut(QKeySequence.Refresh)
    mw.action_refresh.setStatusTip("Refresh device status")
    mw.action_refresh.triggered.connect(mw.on_refresh)

    mw.action_plugin_manager = QAction("Plugin Manager", mw)
    mw.action_plugin_manager.setStatusTip("Manage plugins")
    mw.action_plugin_manager.triggered.connect(mw.on_plugin_manager)

    mw.action_settings = QAction("Settings", mw)
    mw.action_settings.setShortcut(QKeySequence.Preferences)
    mw.action_settings.setStatusTip("Configure application settings")
    mw.action_settings.triggered.connect(mw.on_settings)

    mw.action_documentation = QAction("Documentation", mw)
    mw.action_documentation.setStatusTip("View program documentation")
    mw.action_documentation.triggered.connect(mw.on_documentation)

    mw.action_report_issue = QAction("Report Issue", mw)
    mw.action_report_issue.setStatusTip("Report an issue or request a feature")
    mw.action_report_issue.triggered.connect(mw.on_report_issue)

    mw.action_check_updates = QAction("Check for Updates", mw)
    mw.action_check_updates.setStatusTip("Check for application updates")
    mw.action_check_updates.triggered.connect(mw.on_check_updates)

    mw.action_about = QAction("About", mw)
    mw.action_about.setStatusTip("About NetWORKS")
    mw.action_about.triggered.connect(mw.on_about)

    mw.action_recycle_bin = QAction("Recycle Bin", mw)
    mw.action_recycle_bin.setIcon(material_icon("restore_from_trash", mw, QStyle.SP_TrashIcon))
    mw.action_recycle_bin.setStatusTip("View and restore deleted devices")
    mw.action_recycle_bin.triggered.connect(mw.on_recycle_bin)
