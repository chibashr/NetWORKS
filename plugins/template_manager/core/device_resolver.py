#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device resolution for Template Manager plugin.
Resolves devices by data source (all/selected/group/subnet/tag) and applies filters.
Logic mirrors plugins/report_generator/report_generator.py for consistency.
"""

import re
from plugins.template_manager.core.template_engine import sanitize_value


def parse_subnet(subnet_text):
    """Parse subnet string to ipaddress.IPv4Network or None."""
    subnet_text = (subnet_text or "").strip()
    if not subnet_text:
        return None
    try:
        import ipaddress
        return ipaddress.ip_network(subnet_text, strict=False)
    except Exception:
        return None


def ip_in_subnet(ip_address, subnet):
    """Return True if ip_address is in subnet (subnet is IPv4Network or None)."""
    if not subnet:
        return False
    try:
        import ipaddress
        return ipaddress.ip_address(ip_address) in subnet
    except Exception:
        return False


# Same labels and map as Report Generator.
DATA_SOURCE_LABELS = [
    "All Devices",
    "Selected Devices",
    "Group",
    "Subnet",
    "Tag",
]

DATA_SOURCE_MAP = {
    "All Devices": "all",
    "Selected Devices": "selected",
    "Group": "group",
    "Subnet": "subnet",
    "Tag": "tag",
}

DATA_SOURCE_REVERSE = {v: k for k, v in DATA_SOURCE_MAP.items()}

FILTER_OPERATORS = [
    "equals",
    "not_equals",
    "contains",
    "starts_with",
    "ends_with",
    "regex",
    ">",
    ">=",
    "<",
    "<=",
]


def resolve_devices(device_manager, data_source, filter_logic="AND", filters=None):
    """
    Resolve devices from data_source dict: type, group, subnet, tag.
    Then apply filters (list of {property, operator, value}) with filter_logic AND/OR.
    Returns list of devices.
    """
    source_type = (data_source or {}).get("type", "all")
    devices = _resolve_by_source(device_manager, source_type, data_source or {})
    if not (filters or []):
        return devices
    return _apply_filters(devices, filters, filter_logic)


def _resolve_by_source(device_manager, source_type, data_source):
    if source_type == "selected":
        return list(device_manager.get_selected_devices())
    if source_type == "group":
        group = device_manager.get_group((data_source.get("group") or "").strip())
        return list(group.get_all_devices()) if group else []
    if source_type == "subnet":
        subnet = parse_subnet(data_source.get("subnet", ""))
        return [
            d
            for d in device_manager.get_devices()
            if ip_in_subnet(d.get_property("ip_address", ""), subnet)
        ]
    if source_type == "tag":
        tag = (data_source.get("tag") or "").strip().lower()
        if not tag:
            return []
        out = []
        for d in device_manager.get_devices():
            tags = d.get_property("tags", []) or []
            if tag in [str(t).lower() for t in tags]:
                out.append(d)
        return out
    return list(device_manager.get_devices())


def _apply_filters(devices, filters, filter_logic="AND"):
    if not filters:
        return devices
    use_or = (filter_logic or "AND").strip().upper() == "OR"
    out = []
    for device in devices:
        props = device.get_properties()
        if use_or:
            if any(
                _filter_match(props.get(f.get("property")), f.get("operator", "equals"), f.get("value", ""))
                for f in filters if f.get("property")
            ):
                out.append(device)
        else:
            if all(
                _filter_match(props.get(f.get("property")), f.get("operator", "equals"), f.get("value", ""))
                for f in filters if f.get("property")
            ):
                out.append(device)
    return out


def _filter_match(actual, operator, expected):
    """Match one filter. Mirrors Report Generator _filter_match."""
    if operator in (">", ">=", "<", "<="):
        try:
            av, ev = float(actual), float(expected)
        except Exception:
            return False
        if operator == ">":
            return av > ev
        if operator == ">=":
            return av >= ev
        if operator == "<":
            return av < ev
        if operator == "<=":
            return av <= ev
    at = sanitize_value(actual)
    et = sanitize_value(expected)
    al, el = at.lower(), et.lower()
    if operator == "equals":
        return al == el
    if operator == "not_equals":
        return al != el
    if operator == "contains":
        if isinstance(actual, list):
            return el in [sanitize_value(x).lower() for x in actual]
        return el in al
    if operator == "starts_with":
        return al.startswith(el)
    if operator == "ends_with":
        return al.endswith(el)
    if operator == "regex":
        try:
            return re.search(et, at) is not None
        except re.error:
            return False
    return False
