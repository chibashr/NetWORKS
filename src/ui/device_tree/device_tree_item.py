#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device tree item: tree node for groups and devices.
"""

from loguru import logger


class DeviceTreeItem:
    """Item in the device tree"""

    def __init__(self, data, parent=None, device=None, group=None):
        self.item_data = data
        self.parent_item = parent
        self.child_items = []
        self.device = device
        self.group = group
        self.device_ip = ""
        self.group_device_count = 0

    def appendChild(self, item):
        self.child_items.append(item)

    def child(self, row):
        if row < 0 or row >= len(self.child_items):
            return None
        return self.child_items[row]

    def childCount(self):
        return len(self.child_items)

    def columnCount(self):
        return len(self.item_data)

    def data(self, column):
        if column < 0 or column >= len(self.item_data):
            return None
        return self.item_data[column]

    def parent(self):
        return self.parent_item

    def row(self):
        if self.parent_item:
            try:
                return self.parent_item.child_items.index(self)
            except ValueError:
                logger.debug(f"DeviceTreeItem not found in parent's child list: {self.item_data[0]}")
                return 0
        return 0

    def removeChild(self, row):
        if row < 0 or row >= len(self.child_items):
            return False
        self.child_items.pop(row)
        return True

    def removeAllChildren(self):
        self.child_items = []

    def findChild(self, device=None, group=None):
        if device:
            for child in self.child_items:
                if child.device and child.device.id == device.id:
                    return child
        elif group:
            for child in self.child_items:
                if child.group and child.group.name == group.name:
                    return child
        return None
