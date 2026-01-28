#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Network Scanner Plugin for NetWORKS

Thin entry point: re-exports NetworkScannerPlugin from core.
"""

import os
import sys

# Ensure project root is on path when loaded as plugin entry point
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from plugins.network_scanner.core.network_scanner_plugin import (
    NetworkScannerPlugin as _CoreNetworkScannerPlugin,
)


class NetworkScannerPlugin(_CoreNetworkScannerPlugin):
    """Thin shim so PluginManager finds the plugin class in this module."""

    pass


__all__ = ["NetworkScannerPlugin"]
