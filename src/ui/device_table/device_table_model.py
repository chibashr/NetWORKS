#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device table model for NetWORKS.
"""

from loguru import logger
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Slot
from PySide6.QtGui import QFontDatabase


class DeviceTableModel(QAbstractTableModel):
    """Model for device table"""

    def __init__(self, device_manager):
        super().__init__()
        self.device_manager = device_manager
        self._devices = []
        self._all_headers = ["Alias", "Hostname", "IP Address", "MAC Address", "Status", "Tags", "Groups"]
        self._all_column_keys = ["alias", "hostname", "ip_address", "mac_address", "status", "tags", "groups"]
        self._headers = self._all_headers.copy()
        self._column_keys = self._all_column_keys.copy()
        self._plugin_columns = []
        self._custom_prop_headers = []
        self._custom_prop_keys = []
        self._device_groups = {}
        self._filter_group = None
        self.device_manager.device_added.connect(self.on_device_added)
        self.device_manager.device_removed.connect(self.on_device_removed)
        self.device_manager.device_changed.connect(self.on_device_changed)
        self.device_manager.group_added.connect(self.on_model_changed)
        self.device_manager.group_removed.connect(self.on_model_changed)
        self.refresh_devices()

    def filter_by_group(self, group):
        self._filter_group = group
        self.refresh_devices()

    def get_all_headers(self):
        self._discover_custom_properties()
        all_headers = self._all_headers.copy()
        plugin_headers = [h for h, _, _ in self._plugin_columns]
        return all_headers + plugin_headers + self._custom_prop_headers

    def get_visible_headers(self):
        return self._headers

    def get_data_headers(self):
        return self._headers

    def get_column_index(self, header):
        if header in self._headers:
            return self._headers.index(header) + 1
        return -1

    def _discover_custom_properties(self):
        self._custom_prop_headers = []
        self._custom_prop_keys = []
        core_props = ["id", "alias", "hostname", "ip_address", "mac_address", "status", "notes", "tags"]
        custom_props = {}
        for device in self.device_manager.get_devices():
            for key, value in device.get_properties().items():
                if key not in core_props and key not in self._all_column_keys:
                    if not isinstance(value, (list, dict)):
                        custom_props[key] = True
        for key in sorted(custom_props.keys()):
            header = key.replace("_", " ").title()
            self._custom_prop_headers.append(header)
            self._custom_prop_keys.append(key)

    def set_visible_headers(self, headers):
        self._discover_custom_properties()
        valid_headers = [h for h in headers if h in self.get_all_headers()]
        if not valid_headers:
            return False
        self._headers = []
        self._column_keys = []
        for i, header in enumerate(self._all_headers):
            if header in valid_headers:
                self._headers.append(header)
                self._column_keys.append(self._all_column_keys[i])
        for header, key, _ in self._plugin_columns:
            if header in valid_headers:
                self._headers.append(header)
        for i, header in enumerate(self._custom_prop_headers):
            if header in valid_headers:
                self._headers.append(header)
                self._column_keys.append(self._custom_prop_keys[i])
        self.layoutChanged.emit()
        return True

    def refresh_devices(self):
        self.beginResetModel()
        if self._filter_group:
            self._devices = self._filter_group.get_all_devices()
        else:
            self._devices = self.device_manager.get_devices()
        self._update_device_groups()
        self._discover_custom_properties()
        self.endResetModel()
        logger.debug(f"Refreshed device table with {len(self._devices)} devices")

    def _update_device_groups(self):
        self._device_groups = {}
        groups = self.device_manager.get_groups()
        for group in groups:
            if group == self.device_manager.root_group:
                continue
            for device in group.devices:
                if device.id not in self._device_groups:
                    self._device_groups[device.id] = []
                self._device_groups[device.id].append(group.name)

    def add_column(self, header, key, callback=None):
        if header in self._headers:
            return False
        self._headers.append(header)
        if callback:
            self._plugin_columns.append((header, key, callback))
        else:
            self._column_keys.append(key)
        self.layoutChanged.emit()
        return True

    def remove_column(self, header):
        if header not in self._headers:
            return False
        index = self._headers.index(header)
        self._headers.pop(index)
        for i, (col_header, key, callback) in enumerate(self._plugin_columns):
            if col_header == header:
                self._plugin_columns.pop(i)
                break
        else:
            if index < len(self._column_keys):
                self._column_keys.pop(index)
        self.layoutChanged.emit()
        return True

    def rowCount(self, parent=None):
        return len(self._devices)

    def columnCount(self, parent=None):
        return len(self._headers) + 1

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section == 0:
                return ""
            return self._headers[section - 1]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._devices):
            return None
        device = self._devices[index.row()]
        column = index.column()
        if column == 0:
            if role == Qt.CheckStateRole:
                return Qt.Checked if device in self.device_manager.get_selected_devices() else Qt.Unchecked
            if role == Qt.UserRole:
                return device
            if role == Qt.TextAlignmentRole:
                return Qt.AlignCenter
            return None
        data_column = column - 1
        if role == Qt.DisplayRole or role == Qt.EditRole:
            for header, key, callback in self._plugin_columns:
                if header == self._headers[data_column]:
                    return callback(device)
            if data_column < len(self._column_keys):
                key = self._column_keys[data_column]
                if key == "groups":
                    groups = self._device_groups.get(device.id, [])
                    return ", ".join(groups) if groups else ""
                value = device.get_property(key, "")
                if key == "tags" and isinstance(value, list):
                    return ", ".join(value)
                return value
            return None
        if role == Qt.FontRole:
            header = self._headers[data_column]
            key = self._column_keys[data_column] if data_column < len(self._column_keys) else None
            if key in ("ip_address", "mac_address") or (key and "id" in key) or "ID" in header:
                return QFontDatabase.systemFont(QFontDatabase.FixedFont)
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter
        if role == Qt.UserRole:
            return device
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        if index.column() == 0:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or index.column() != 0 or role != Qt.CheckStateRole:
            return False
        device = self._devices[index.row()]
        selected_devices = self.device_manager.get_selected_devices()
        next_selection = selected_devices.copy()
        if value == Qt.Checked and device not in next_selection:
            next_selection.append(device)
        elif value == Qt.Unchecked and device in next_selection:
            next_selection.remove(device)
        if set(next_selection) == set(selected_devices):
            return False
        self.device_manager.selected_devices = next_selection.copy()
        self.device_manager.selection_changed.emit(next_selection)
        self.dataChanged.emit(index, index, [Qt.CheckStateRole])
        return True

    def notify_selection_changed(self, rows=None):
        if self.rowCount() == 0:
            return
        if rows:
            for row in rows:
                idx = self.index(row, 0)
                self.dataChanged.emit(idx, idx, [Qt.CheckStateRole])
            return
        left_index = self.index(0, 0)
        right_index = self.index(self.rowCount() - 1, 0)
        self.dataChanged.emit(left_index, right_index, [Qt.CheckStateRole])

    @Slot(object)
    def on_device_added(self, device):
        if device not in self._devices:
            self._devices.append(device)
            self._discover_custom_properties()
            self.layoutChanged.emit()

    @Slot(object)
    def on_device_removed(self, device):
        if device in self._devices:
            row = self._devices.index(device)
            self.beginRemoveRows(QModelIndex(), row, row)
            self._devices.remove(device)
            self.endRemoveRows()
            self._discover_custom_properties()

    @Slot(object)
    def on_device_changed(self, device):
        if device in self._devices:
            self._update_device_groups()
            old_custom = set(self._custom_prop_keys)
            self._discover_custom_properties()
            if set(self._custom_prop_keys) != old_custom:
                self.layoutChanged.emit()
            else:
                row = self._devices.index(device)
                left_index = self.index(row, 0)
                right_index = self.index(row, self.columnCount() - 1)
                self.dataChanged.emit(left_index, right_index)

    @Slot()
    def on_model_changed(self):
        self.refresh_devices()
