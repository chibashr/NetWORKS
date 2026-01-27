#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device tree panel: search, compact mode, filter controls around the tree view.
"""

from .device_tree_model import DeviceTreeModel
from .device_tree_filter import DeviceTreeFilterProxyModel
from .device_tree_view import DeviceTreeView

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QToolButton, QMenu, QDockWidget, QStyle,
)
from ..material_icons import material_icon

# Toolbar icon buttons: 24×24 icon, 32×32 button. Inline (next to inputs): 18×18 icon, 24×24 button.
_ICON_SIZE = 24
_ICON_BUTTON_SIZE = 32
_INLINE_ICON_SIZE = 18
_INLINE_BUTTON_SIZE = 24


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
        
        # Search row
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search groups or devices...")
        clear_button = QToolButton()
        clear_button.setAutoRaise(True)
        clear_button.setProperty("iconOnlyInline", "true")
        clear_button.setIcon(material_icon("close", self, QStyle.SP_DialogResetButton))
        clear_button.setIconSize(QSize(_INLINE_ICON_SIZE, _INLINE_ICON_SIZE))
        clear_button.setFixedSize(_INLINE_BUTTON_SIZE, _INLINE_BUTTON_SIZE)
        clear_button.setToolTip("Clear search text")
        clear_button.clicked.connect(self._clear_search)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit, 1)
        search_layout.addWidget(clear_button)
        
        # Toolbar row
        toolbar_layout = QHBoxLayout()
        self.compact_toggle = QCheckBox("Compact")
        self.filter_toggle = QCheckBox("Filter Table")
        expand_button = QToolButton()
        expand_button.setAutoRaise(True)
        expand_button.setProperty("iconOnlyInline", "true")
        expand_button.setIcon(material_icon("expand_more", self, QStyle.SP_ArrowDown))
        expand_button.setIconSize(QSize(_INLINE_ICON_SIZE, _INLINE_ICON_SIZE))
        expand_button.setFixedSize(_INLINE_BUTTON_SIZE, _INLINE_BUTTON_SIZE)
        expand_button.setToolTip("Expand all groups")
        collapse_button = QToolButton()
        collapse_button.setAutoRaise(True)
        collapse_button.setProperty("iconOnlyInline", "true")
        collapse_button.setIcon(material_icon("expand_less", self, QStyle.SP_ArrowUp))
        collapse_button.setIconSize(QSize(_INLINE_ICON_SIZE, _INLINE_ICON_SIZE))
        collapse_button.setFixedSize(_INLINE_BUTTON_SIZE, _INLINE_BUTTON_SIZE)
        collapse_button.setToolTip("Collapse all groups")

        width_button = QToolButton()
        width_button.setAutoRaise(True)
        width_button.setProperty("iconOnlyInline", "true")
        width_button.setIcon(material_icon("width_full", self, QStyle.SP_TitleBarMaxButton))
        width_button.setIconSize(QSize(_INLINE_ICON_SIZE, _INLINE_ICON_SIZE))
        width_button.setFixedSize(_INLINE_BUTTON_SIZE, _INLINE_BUTTON_SIZE)
        width_button.setToolTip("Set a width preset for the device tree")
        width_button.setPopupMode(QToolButton.InstantPopup)
        width_menu = QMenu(self)
        width_menu.addAction("Narrow", lambda: self._apply_width_preset(260))
        width_menu.addAction("Medium", lambda: self._apply_width_preset(320))
        width_menu.addAction("Wide", lambda: self._apply_width_preset(420))
        width_button.setMenu(width_menu)
        
        toolbar_layout.addWidget(self.compact_toggle)
        toolbar_layout.addWidget(self.filter_toggle)
        toolbar_layout.addWidget(expand_button)
        toolbar_layout.addWidget(collapse_button)
        toolbar_layout.addWidget(width_button)
        toolbar_layout.addStretch(1)
        
        layout.addLayout(search_layout)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.view, 1)
        
        # Wire up actions
        self.search_edit.textChanged.connect(self.proxy_model.set_filter_text)
        self.compact_toggle.toggled.connect(self.view.set_compact_mode)
        self.filter_toggle.toggled.connect(self.view.set_filter_table_on_group_select)
        expand_button.clicked.connect(self.view.expandAll)
        collapse_button.clicked.connect(self.view.collapseAll)
        
    def _clear_search(self):
        self.search_edit.clear()
        
    def _apply_width_preset(self, width):
        dock = self._find_dock_widget()
        if dock:
            dock.setMinimumWidth(width)
            dock.resize(width, dock.height())
            self._save_width_preset(width)
        
    def _find_dock_widget(self):
        parent = self.parentWidget()
        while parent:
            if isinstance(parent, QDockWidget):
                return parent
            parent = parent.parentWidget()
        return None
        
    def _save_width_preset(self, width):
        settings = self.view._get_workspace_settings()
        settings.setValue("width_preset", width)
        
    def restore_state(self):
        """Restore UI state from workspace settings"""
        self.view.restore_state()
        self.compact_toggle.setChecked(self.view._compact_mode)
        self.filter_toggle.setChecked(self.view._filter_table_on_group_select)
        settings = self.view._get_workspace_settings()
        preset = settings.value("width_preset", None)
        if preset:
            try:
                self._apply_width_preset(int(preset))
            except (TypeError, ValueError):
                pass
        
    def save_state(self):
        """Persist UI state to workspace settings"""
        self.view.save_state()