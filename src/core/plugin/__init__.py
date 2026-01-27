#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin subsystem: registry, discovery, lifecycle, and validation.

Used by PluginManager; not intended for direct use by app or plugins.
"""

from .plugin_discovery import run_discovery
from .plugin_registry import (
    build_registry_data,
    load_registry_from_file,
    save_registry_to_file,
)

__all__ = [
    "build_registry_data",
    "load_registry_from_file",
    "run_discovery",
    "save_registry_to_file",
]
