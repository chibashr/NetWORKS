#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
List widget item for plugin list in the plugin manager dialog.
Supports both PluginInfo (installed) and CatalogPluginInfo (catalog-only).
"""

import os
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPalette, QBrush
from PySide6.QtWidgets import QListWidgetItem, QApplication

from ...core.plugin_manager import PluginState


class PluginListItem(QListWidgetItem):
    """Custom list widget item for plugins (installed or catalog)."""

    def __init__(self, plugin_info, catalog_status=None):
        """
        plugin_info: PluginInfo (installed) or CatalogPluginInfo (catalog).
        catalog_status: For catalog items: "installed"|"update_available"|"not_installed".
        """
        super().__init__(plugin_info.name)
        self.plugin_info = plugin_info
        self.catalog_status = catalog_status
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

    def _is_catalog_item(self):
        return self.catalog_status is not None

    def update_icon(self):
        palette = QApplication.palette()
        text_color = palette.color(QPalette.Text)
        disabled_color = palette.color(QPalette.Disabled, QPalette.Text)
        error_color = QColor(Qt.red)
        if self._is_catalog_item():
            if self.catalog_status == "update_available":
                status_text = " [Update available]"
            elif self.catalog_status == "installed":
                status_text = " [Installed]"
            else:
                status_text = " [Not installed]"
            self.setForeground(QBrush(text_color))
            self.setIcon(self._load_plugin_icon(text_color))
            self.setText(f"{self.plugin_info.name}{status_text}")
            return
        if self.plugin_info.state.is_disabled:
            status_text = " [Disabled]"
            self.setForeground(QBrush(disabled_color))
            self.setIcon(self._load_plugin_icon(disabled_color))
        elif self.plugin_info.state.is_loaded:
            status_text = " [Loaded]"
            self.setForeground(QBrush(text_color))
            self.setIcon(self._load_plugin_icon(text_color))
        elif self.plugin_info.state == PluginState.DISCOVERED:
            status_text = " [Not loaded]"
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
