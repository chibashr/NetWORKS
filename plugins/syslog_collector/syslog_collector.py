#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Syslog Collector Plugin for NetWORKS.

Thin entry point: re-exports SyslogCollectorPlugin from core.
"""

import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from plugins.syslog_collector.core.syslog_collector_plugin import (
    SyslogCollectorPlugin as _CoreSyslogCollectorPlugin,
)


class SyslogCollectorPlugin(_CoreSyslogCollectorPlugin):
    """Thin shim so PluginManager finds the plugin class in this module."""

    pass


__all__ = ["SyslogCollectorPlugin"]
