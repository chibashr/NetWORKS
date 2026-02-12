#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SNMP Collector Plugin for NetWORKS.

Thin entry point: re-exports SnmpCollectorPlugin from core.
"""

import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from plugins.snmp_collector.core.snmp_collector_plugin import SnmpCollectorPlugin

__all__ = ["SnmpCollectorPlugin"]
