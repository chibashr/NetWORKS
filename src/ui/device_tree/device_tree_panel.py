#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device tree panel: search and tree view with minimal expand/collapse controls.
"""

from .device_tree_model import DeviceTreeModel
from .device_tree_filter import DeviceTreeFilterProxyModel
from .device_tree_view import DeviceTreeView

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QToolButton, QStyle,
)
from ..material_icons import material_icon

# Small integrated expand/collapse: 12×12 icon, 28×28 button (square, shared height)
_EXPAND_COLLAPSE_ICON = 12
_EXPAND_COLLAPSE_BUTTON = 28


class DeviceTreePanel(QWidget):
    """Panel combining tree controls and the device tree view"""
    
    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.setMinimumWidth(240)
        
        self.model = DeviceTreeModel(self.device_manager)
        self.proxy_model = DeviceTreeFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        
        self.view = DeviceTreeView(self.device_manager)
        self.view.setModel(self.proxy_model)
        
        self._create_ui()
        self.restore_state()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Search bar and expand/collapse on one line
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search groups or devices...")
        expand_btn = QToolButton()
        expand_btn.setAutoRaise(True)
        expand_btn.setProperty("iconOnlyInline", "true")
        expand_btn.setIcon(material_icon("expand_more", self, QStyle.SP_ArrowDown))
        expand_btn.setIconSize(QSize(_EXPAND_COLLAPSE_ICON, _EXPAND_COLLAPSE_ICON))
        expand_btn.setFixedSize(_EXPAND_COLLAPSE_BUTTON, _EXPAND_COLLAPSE_BUTTON)
        expand_btn.setToolTip("Expand all groups")
        collapse_btn = QToolButton()
        collapse_btn.setAutoRaise(True)
        collapse_btn.setProperty("iconOnlyInline", "true")
        collapse_btn.setIcon(material_icon("expand_less", self, QStyle.SP_ArrowUp))
        collapse_btn.setIconSize(QSize(_EXPAND_COLLAPSE_ICON, _EXPAND_COLLAPSE_ICON))
        collapse_btn.setFixedSize(_EXPAND_COLLAPSE_BUTTON, _EXPAND_COLLAPSE_BUTTON)
        collapse_btn.setToolTip("Collapse all groups")
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit, 1)
        search_layout.addWidget(expand_btn)
        search_layout.addWidget(collapse_btn)

        layout.addLayout(search_layout)
        layout.addWidget(self.view, 1)

        self.search_edit.textChanged.connect(self.proxy_model.set_filter_text)
        expand_btn.clicked.connect(self.view.expandAll)
        collapse_btn.clicked.connect(self.view.collapseAll)

    def restore_state(self):
        """Restore UI state from workspace settings"""
        self.view.restore_state()

    def save_state(self):
        """Persist UI state to workspace settings"""
        self.view.save_state()