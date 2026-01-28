#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Shared device helpers for Template Manager UI: display names and combo populations.
"""


def device_display_name(device):
    """
    Return a label for a device suitable for UI (alias, hostname, ip_address, or "Unknown").
    """
    alias = device.get_property("alias") or ""
    hostname = device.get_property("hostname") or ""
    ip = device.get_property("ip_address") or ""
    return (alias or hostname or ip or "Unknown").strip() or "Unknown"


def group_names_for_combo(device_manager):
    """
    Return a sorted list of non-empty group names for populating a group combo.
    """
    names = []
    try:
        for g in (device_manager.get_groups() or []):
            n = getattr(g, "name", None) or str(g)
            if n:
                names.append(n)
    except Exception:
        pass
    return sorted(set(names))
