#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device table package: model, view, filter, query engine, and dialogs.

Re-exports public API so "from src.ui.device_table import DeviceTableModel, DeviceTableView"
and "from .device_table import DeviceTableModel, DeviceTableView" continue to work.

Filter/query: parse_filter_syntax handles power-user text, legacy field:value, and plain search.
filter_state_to_syntax emits text for the search bar. Tree state uses {"operator","conditions"}.
"""

from PySide6.QtWidgets import QAbstractItemView

from .device_table_dialogs import AdvancedFilterDialog
from .device_table_filter import (
    FILTER_FIELD_ALIASES,
    IPSortFilterProxyModel,
    filter_state_to_syntax,
    parse_filter_syntax,
)
from .device_table_model import DeviceTableModel
from .device_table_query import (
    ensure_tree,
    is_tree_state,
    operators_for_field,
    parse_text_query,
    tree_to_syntax,
)
from .device_table_view import DeviceTableView

__all__ = [
    "AdvancedFilterDialog",
    "DeviceTableModel",
    "DeviceTableView",
    "FILTER_FIELD_ALIASES",
    "IPSortFilterProxyModel",
    "QAbstractItemView",
    "ensure_tree",
    "filter_state_to_syntax",
    "is_tree_state",
    "operators_for_field",
    "parse_filter_syntax",
    "parse_text_query",
    "tree_to_syntax",
]
