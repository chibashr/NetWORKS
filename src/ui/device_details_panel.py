#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device details panel for the main window.
This manages the tabs and panels that display device details, including those added by plugins.
"""

import os
from loguru import logger
from PySide6.QtWidgets import QTabWidget, QWidget
from PySide6.QtCore import Qt, Signal, Slot

class DeviceDetailsPanel(QTabWidget):
    """Widget for displaying device details in tabs/panels
    
    This panel is used in the properties dock widget and consists of tabs
    for different aspects of device details. Plugins can add their own
    panels to this widget.
    """
    
    def __init__(self, parent=None):
        """Initialize the device details panel"""
        super().__init__(parent)
        self.setTabPosition(QTabWidget.North)
        self.setDocumentMode(True)
        
        # Track panels added by plugins
        self._plugin_panels = {}  # {panel_name: (widget, tab_index)}
        
    def add_panel(self, name, widget):
        """Add a panel to the device details panel
        
        Args:
            name: The name of the panel/tab
            widget: The widget to add
            
        Returns:
            int: The index of the added tab
        """
        logger.debug(f"Adding device details panel: {name}")
        
        # Add the tab
        index = self.addTab(widget, name)
        
        # Store for later reference/removal
        self._plugin_panels[name] = (widget, index)
        
        return index
        
    def remove_panel(self, name):
        """Remove a panel from the device details panel
        
        Args:
            name: The name of the panel to remove
            
        Returns:
            bool: True if the panel was removed, False otherwise
        """
        logger.debug(f"Removing device details panel: {name}")
        
        if name not in self._plugin_panels:
            logger.warning(f"Panel not found: {name}")
            return False
            
        # Get panel info
        widget, index = self._plugin_panels[name]
        
        # Check if the index is still valid
        if index >= self.count():
            logger.warning(f"Panel index out of range: {index} >= {self.count()}")
            # Try to find it by name
            for i in range(self.count()):
                if self.tabText(i) == name:
                    index = i
                    break
            else:
                # Not found
                logger.warning(f"Could not find panel by name: {name}")
                return False
        
        # Remove from the tab widget
        try:
            self.removeTab(index)
            
            # Force the widget to be properly cleaned up
            if widget:
                if widget.parent() == self:
                    widget.setParent(None)
                widget.deleteLater()
                
            # Remove from our tracking dict
            del self._plugin_panels[name]
            
            # Reindex remaining panels
            self._update_indexes()
            
            logger.debug(f"Successfully removed panel: {name}")
            return True
        except Exception as e:
            logger.error(f"Error removing panel {name}: {e}")
            return False
            
    def _update_indexes(self):
        """Update the tab indexes in our tracking dictionary after removing a tab"""
        # After removing a tab, indexes may have changed
        for name, (widget, _) in list(self._plugin_panels.items()):
            # Find current index
            for i in range(self.count()):
                if self.widget(i) == widget:
                    self._plugin_panels[name] = (widget, i)
                    break 