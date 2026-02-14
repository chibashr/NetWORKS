#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Reusable UI components for plugin surfaces.
"""

from PySide6.QtWidgets import (
    QApplication,
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
    QScrollArea,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont

from .theme import arrow_icon, get_arrow_color
from .plugin_ui_theme import (
    PLUGIN_UI_SIZES,
    mark_plugin_ui,
    apply_compact_button,
    apply_icon_button,
    apply_plugin_ui_layout,
)


def create_plugin_tab_widget() -> QTabWidget:
    """
    Create a QTabWidget with plugin_ui styling.
    Tab content is automatically inset 8px from pane edges via stylesheet.
    Use for plugin docks, dialogs, or panels with tabs.
    """
    tab = QTabWidget()
    mark_plugin_ui(tab)
    mark_plugin_ui(tab.tabBar())
    return tab


def wrap_in_scroll_area(widget: QWidget) -> QScrollArea:
    """
    Wrap a widget in a QScrollArea for overflow handling.
    Use when tab content, forms, or panels may exceed available height.
    """
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidget(widget)
    mark_plugin_ui(scroll)
    return scroll


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
        self.toggle_button.setProperty("plugin_ui_section", "true")
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self._arrow_color = self._resolve_arrow_color()
        self._icon_size = 8  # Compact arrow in section header
        self._icon_down = arrow_icon("down", self._arrow_color, self._icon_size)
        self._icon_right = arrow_icon("right", self._arrow_color, self._icon_size)
        self.toggle_button.setIconSize(QSize(self._icon_size, self._icon_size))
        self.toggle_button.setIcon(self._icon_down if expanded else self._icon_right)
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
        apply_plugin_ui_layout(self.content_layout, PLUGIN_UI_SIZES["collapsible_content_padding"])
        layout.addWidget(self.content_frame)

        self.toggle_button.toggled.connect(self._on_toggled)
        self.content_frame.setVisible(expanded)
        self._update_collapsed_property(expanded)

        app = QApplication.instance()
        if hasattr(app, "theme_changed"):
            app.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self) -> None:
        """Refresh arrow icons when theme changes dynamically."""
        self._arrow_color = self._resolve_arrow_color()
        self._icon_down = arrow_icon("down", self._arrow_color, self._icon_size)
        self._icon_right = arrow_icon("right", self._arrow_color, self._icon_size)
        self.toggle_button.setIcon(
            self._icon_down if self.toggle_button.isChecked() else self._icon_right
        )

    def _on_toggled(self, checked: bool) -> None:
        self.toggle_button.setIcon(self._icon_down if checked else self._icon_right)
        self.content_frame.setVisible(checked)
        self._update_collapsed_property(checked)

    def _resolve_arrow_color(self) -> str:
        """Arrow color for expand/collapse icons; matches dropdown/spin box arrows."""
        return get_arrow_color()

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
