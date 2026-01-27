#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
List widget item for plugin list in the plugin manager dialog.
"""

import os
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPalette, QBrush
from PySide6.QtWidgets import QListWidgetItem, QApplication

from ...core.plugin_manager import PluginState


class PluginListItem(QListWidgetItem):
    """Custom list widget item for plugins"""

    def __init__(self, plugin_info):
        super().__init__(plugin_info.name)
        self.plugin_info = plugin_info
        self.setToolTip(plugin_info.description)
        self.update_icon()

    def _load_plugin_icon(self, color):
        icon_path = getattr(self.plugin_info, "icon_path", None)
        if not icon_path or not os.path.exists(icon_path):
            return QIcon()
        base_icon = QIcon(icon_path)
        pixmap = base_icon.pixmap(QSize(32, 32))
        if pixmap.isNull():
            return QIcon()
        tinted = QPixmap(pixmap.size())
        tinted.fill(Qt.transparent)
        painter = QPainter(tinted)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), color)
        painter.end()
        return QIcon(tinted)

    def update_icon(self):
        palette = QApplication.palette()
        text_color = palette.color(QPalette.Text)
        disabled_color = palette.color(QPalette.Disabled, QPalette.Text)
        error_color = QColor(Qt.red)
        if self.plugin_info.state.is_disabled:
            status_text = " [Disabled]"
            self.setForeground(QBrush(disabled_color))
            self.setIcon(self._load_plugin_icon(disabled_color))
        elif self.plugin_info.state.is_loaded:
            status_text = " [Loaded]"
            self.setForeground(QBrush(text_color))
            self.setIcon(self._load_plugin_icon(text_color))
        elif self.plugin_info.state.is_enabled:
            status_text = " [Enabled]"
            self.setForeground(QBrush(text_color))
            self.setIcon(self._load_plugin_icon(text_color))
        elif self.plugin_info.state == PluginState.ERROR:
            status_text = " [Error]"
            self.setForeground(QBrush(error_color))
            self.setIcon(self._load_plugin_icon(error_color))
        else:
            status_text = ""
            self.setForeground(QBrush(text_color))
            self.setIcon(self._load_plugin_icon(text_color))
        self.setText(f"{self.plugin_info.name}{status_text}")
