#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Filter proxy for the device tree.
"""

from PySide6.QtCore import Qt, QSortFilterProxyModel


class DeviceTreeFilterProxyModel(QSortFilterProxyModel):
    """Filter proxy for the device tree."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterKeyColumn(0)

    def set_filter_text(self, text):
        self._filter_text = (text or "").strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._filter_text:
            return True
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return False
        if self._row_matches(index):
            return True
        child_count = model.rowCount(index)
        for row in range(child_count):
            if self.filterAcceptsRow(row, index):
                return True
        return False

    def _row_matches(self, index):
        text = index.data(Qt.DisplayRole) or ""
        if self._filter_text.lower() in str(text).lower():
            return True
        item = index.data(Qt.UserRole)
        if hasattr(item, "name"):
            return self._filter_text.lower() in item.name.lower()
        if hasattr(item, "get_property"):
            alias = item.get_property("alias", "")
            hostname = item.get_property("hostname", "")
            ip_address = item.get_property("ip_address", "")
            haystack = " ".join([alias, hostname, ip_address]).lower()
            return self._filter_text.lower() in haystack
        return False
