#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Reusable UI components for plugin surfaces.
"""

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QToolButton,
    QSizePolicy,
    QFrame,
    QTabWidget,
    QPushButton,
    QDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont

from .plugin_ui_theme import (
    PLUGIN_UI_SIZES,
    mark_plugin_ui,
    apply_compact_button,
    apply_icon_button,
    apply_plugin_ui_layout,
)


class PluginDockHeader(QWidget):
    """Dock header with icon/title and compact action buttons."""

    def __init__(self, title: str, icon: QIcon | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("PluginDockHeader")
        mark_plugin_ui(self)

        layout = QHBoxLayout(self)
        layout.setSpacing(PLUGIN_UI_SIZES["grid"])
        layout.setContentsMargins(8, 0, 8, 0)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(PLUGIN_UI_SIZES["icon_button_size"], PLUGIN_UI_SIZES["icon_button_size"])
        if icon:
            self.icon_label.setPixmap(icon.pixmap(self.icon_label.size()))
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("PluginDockTitle")
        title_font = QFont()
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        layout.addStretch(1)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(PLUGIN_UI_SIZES["grid"])
        layout.addLayout(self.actions_layout)

        # Use a compact minimum height so the header stays dense but can grow
        # slightly when fonts or DPI are larger than default.
        self.setMinimumHeight(PLUGIN_UI_SIZES["dock_header_height"])

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_icon(self, icon: QIcon | None) -> None:
        if icon:
            self.icon_label.setPixmap(icon.pixmap(self.icon_label.size()))
        else:
            self.icon_label.clear()

    def add_action(self, action) -> QToolButton:
        button = QToolButton(self)
        button.setDefaultAction(action)
        button.setAutoRaise(True)
        if action.icon().isNull():
            button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            apply_compact_button(button)
        else:
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            apply_icon_button(button)
        self.actions_layout.addWidget(button)
        return button


class CollapsibleSection(QWidget):
    """
    Collapsible content section with a full-width, centered header (folder-style).
    Use layout spacing 0 and addStretch when stacking multiple sections so they
    sit flush and anchor to the top.
    """

    def __init__(self, title: str, parent: QWidget | None = None, expanded: bool = True):
        super().__init__(parent)
        self.setObjectName("CollapsibleSection")
        mark_plugin_ui(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header_widget = QFrame(self)
        self.header_widget.setObjectName("CollapsibleSectionHeader")
        self.header_widget.setProperty("plugin_ui_section", "true")
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        header_layout.addStretch(1)
        self.title_label = QLabel(title, self.header_widget)
        self.title_label.setObjectName("CollapsibleSectionTitle")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)

        self.toggle_button = QToolButton(self.header_widget)
        self.toggle_button.setText("")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle_button.setProperty("plugin_ui_section", "true")
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(self.toggle_button)

        def _header_click(widget, e):
            self.toggle_button.click()
            e.accept()
        self.header_widget.mousePressEvent = lambda e: _header_click(self.header_widget, e)
        self.title_label.mousePressEvent = lambda e: _header_click(self.title_label, e)
        self.title_label.setCursor(Qt.PointingHandCursor)

        layout.addWidget(self.header_widget)

        self.content_frame = QFrame(self)
        self.content_frame.setProperty("plugin_ui_section", "true")
        self.content_frame.setObjectName("CollapsibleSectionContent")
        self.content_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.content_layout = QVBoxLayout(self.content_frame)
        apply_plugin_ui_layout(self.content_layout, PLUGIN_UI_SIZES["section_padding"])
        layout.addWidget(self.content_frame)

        self.toggle_button.toggled.connect(self._on_toggled)
        self.content_frame.setVisible(expanded)
        self._update_collapsed_property(expanded)

    def _on_toggled(self, checked: bool) -> None:
        self.toggle_button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.content_frame.setVisible(checked)
        self._update_collapsed_property(checked)

    def _update_collapsed_property(self, expanded: bool) -> None:
        """Update property for styling when collapsed (bottom border on header)."""
        collapsed = "true" if not expanded else "false"
        self.setProperty("collapsed", collapsed)
        self.header_widget.setProperty("collapsed", collapsed)
        self.style().unpolish(self)
        self.style().polish(self)
        self.header_widget.style().unpolish(self.header_widget)
        self.header_widget.style().polish(self.header_widget)

    def set_title(self, title: str) -> None:
        """Update the section header title."""
        self.title_label.setText(title)


class PluginDialogBase(QDialog):
    """Dialog base layout with tabs and a compact button bar."""

    def __init__(self, title: str = "", parent: QWidget | None = None, use_tabs: bool = True):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.setWindowTitle(title)

        self.main_layout = QVBoxLayout(self)
        apply_plugin_ui_layout(self.main_layout, PLUGIN_UI_SIZES["dialog_padding"])

        self.tab_widget = None
        if use_tabs:
            self.tab_widget = QTabWidget(self)
            mark_plugin_ui(self.tab_widget)
            mark_plugin_ui(self.tab_widget.tabBar())
            self.main_layout.addWidget(self.tab_widget)

        self.button_bar = QWidget(self)
        self.button_bar.setObjectName("PluginDialogButtonBar")
        self.button_layout = QHBoxLayout(self.button_bar)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(PLUGIN_UI_SIZES["grid"])
        self.button_layout.addStretch(1)
        self.main_layout.addWidget(self.button_bar)

    def add_tab(self, widget: QWidget, title: str) -> None:
        if not self.tab_widget:
            raise ValueError("PluginDialogBase is configured without tabs.")
        mark_plugin_ui(widget)
        self.tab_widget.addTab(widget, title)

    def add_action_button(self, label: str, callback=None) -> QPushButton:
        button = QPushButton(label, self)
        apply_compact_button(button)
        if callback:
            button.clicked.connect(callback)
        self.button_layout.addWidget(button)
        return button
