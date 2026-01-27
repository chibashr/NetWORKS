#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin manager dialog package.

Re-exports so "from .plugin_manager_dialog import PluginManagerDialog" works.
"""

from .plugin_list_item import PluginListItem
from .plugin_manager_dialog import PluginManagerDialog

__all__ = ["PluginManagerDialog", "PluginListItem"]
