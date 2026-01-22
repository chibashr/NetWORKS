#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Workspace browser dialog for selecting or creating workspaces.
"""

import json
import os

from loguru import logger
from PySide6.QtCore import Qt, QDir
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QLineEdit,
    QTextEdit, QPushButton, QTreeView, QGroupBox, QFormLayout, QMessageBox
)
from PySide6.QtWidgets import QFileSystemModel


class WorkspaceBrowserDialog(QDialog):
    """Dialog that lets users browse workspace directories and view metadata."""

    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.workspaces_dir = device_manager.workspaces_dir
        self.selected_workspace_dir = None
        self.selected_workspace_name = None
        self.create_requested = False
        self.new_workspace_name = ""
        self.new_workspace_description = ""

        self.setWindowTitle("Workspace Browser")
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        header = QLabel("Browse and select a workspace, or create a new one:")
        header.setStyleSheet("font-size: 12pt; font-weight: bold;")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        # File browser panel
        browser_widget = QGroupBox("Workspaces")
        browser_layout = QVBoxLayout(browser_widget)
        self.workspace_model = QFileSystemModel(self)
        self.workspace_model.setRootPath(self.workspaces_dir)
        self.workspace_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Files)

        self.workspace_view = QTreeView()
        self.workspace_view.setModel(self.workspace_model)
        self.workspace_view.setRootIndex(self.workspace_model.index(self.workspaces_dir))
        self.workspace_view.setHeaderHidden(True)
        self.workspace_view.setSortingEnabled(True)
        browser_layout.addWidget(self.workspace_view)
        splitter.addWidget(browser_widget)

        # Details panel
        details_widget = QGroupBox("Workspace Details")
        details_layout = QVBoxLayout(details_widget)

        form_layout = QFormLayout()
        self.name_label = QLabel("—")
        self.description_label = QLabel("—")
        self.device_count_label = QLabel("—")
        self.path_label = QLabel("—")

        self.description_label.setWordWrap(True)
        self.path_label.setWordWrap(True)

        form_layout.addRow("Name:", self.name_label)
        form_layout.addRow("Description:", self.description_label)
        form_layout.addRow("Device Count:", self.device_count_label)
        form_layout.addRow("Path:", self.path_label)

        details_layout.addLayout(form_layout)

        # Preview tree for workspace files
        self.preview_model = QFileSystemModel(self)
        self.preview_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Files)
        self.preview_model.setRootPath(self.workspaces_dir)

        self.preview_view = QTreeView()
        self.preview_view.setModel(self.preview_model)
        self.preview_view.setHeaderHidden(True)
        details_layout.addWidget(self.preview_view, 1)

        splitter.addWidget(details_widget)
        splitter.setSizes([350, 550])

        # New workspace section
        new_group = QGroupBox("New Workspace")
        new_layout = QVBoxLayout(new_group)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.new_name_edit = QLineEdit()
        name_layout.addWidget(self.new_name_edit)
        new_layout.addLayout(name_layout)

        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        self.new_desc_edit = QTextEdit()
        self.new_desc_edit.setMaximumHeight(80)
        desc_layout.addWidget(self.new_desc_edit)
        new_layout.addLayout(desc_layout)

        layout.addWidget(new_group)

        # Buttons
        button_layout = QHBoxLayout()
        self.open_button = QPushButton("Open Workspace")
        self.create_button = QPushButton("Create Workspace")
        self.cancel_button = QPushButton("Cancel")

        button_layout.addWidget(self.open_button)
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.workspace_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.open_button.clicked.connect(self._on_open_clicked)
        self.create_button.clicked.connect(self._on_create_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _resolve_workspace_dir(self, index):
        if not index.isValid():
            return None
        path = self.workspace_model.filePath(index)
        if os.path.isdir(path):
            return path
        return os.path.dirname(path)

    def _load_metadata(self, workspace_dir):
        workspace_file = os.path.join(workspace_dir, "workspace.json")
        if os.path.exists(workspace_file):
            try:
                with open(workspace_file, "r") as handle:
                    data = json.load(handle)
                name = data.get("name") or os.path.basename(workspace_dir)
                description = data.get("description", "")
                device_count = len(data.get("devices", []))
                return name, description, device_count
            except Exception as exc:
                logger.error(f"Failed to load workspace metadata: {exc}")

        # Fallback when workspace.json is missing or invalid
        devices_dir = os.path.join(workspace_dir, "devices")
        device_count = 0
        if os.path.isdir(devices_dir):
            device_count = len([d for d in os.listdir(devices_dir) if os.path.isdir(os.path.join(devices_dir, d))])
        return os.path.basename(workspace_dir), "", device_count

    def _on_selection_changed(self, selected, _deselected):
        index = selected.indexes()[0] if selected.indexes() else None
        if not index:
            return
        workspace_dir = self._resolve_workspace_dir(index)
        if not workspace_dir:
            return
        name, description, device_count = self._load_metadata(workspace_dir)

        self.selected_workspace_dir = workspace_dir
        self.selected_workspace_name = name

        self.name_label.setText(name or "—")
        self.description_label.setText(description or "—")
        self.device_count_label.setText(str(device_count))
        self.path_label.setText(workspace_dir)

        self.preview_view.setRootIndex(self.preview_model.index(workspace_dir))

    def _on_open_clicked(self):
        if not self.selected_workspace_dir:
            QMessageBox.warning(self, "Open Workspace", "Select a workspace folder or file first.")
            return
        self.create_requested = False
        self.accept()

    def _on_create_clicked(self):
        name = self.new_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Create Workspace", "Please enter a workspace name.")
            return
        self.create_requested = True
        self.new_workspace_name = name
        self.new_workspace_description = self.new_desc_edit.toPlainText().strip()
        self.accept()
