#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build device_table_view.py from the original device_table.py (lines 306-405, 1011-end)."""
import os
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(base, "src", "ui", "device_table.py")
dst = os.path.join(base, "src", "ui", "device_table", "device_table_view.py")
with open(src, "r", encoding="utf-8") as f:
    lines = f.readlines()
view_lines = lines[305:3460]
header = r'''#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device table view and internal widgets for NetWORKS.
"""

from .device_table_model import DeviceTableModel
from .device_table_filter import IPSortFilterProxyModel, parse_filter_syntax, filter_state_to_syntax
from .device_table_dialogs import AdvancedFilterDialog

from loguru import logger
from PySide6.QtCore import Qt, Signal, Slot, QRect, QSettings
from PySide6.QtWidgets import (
    QTableView, QHeaderView, QAbstractItemView, QMenu, QApplication, QWidget,
    QVBoxLayout, QFormLayout, QLineEdit, QLabel, QTextEdit, QPushButton, QHBoxLayout,
    QComboBox, QTabWidget, QListWidget, QListWidgetItem, QMessageBox, QGroupBox,
    QCheckBox, QTableWidget, QTableWidgetItem, QFileDialog, QWizard, QWizardPage,
    QScrollArea, QRadioButton, QSizePolicy, QGridLayout, QToolButton, QInputDialog,
)
from PySide6.QtGui import QAction
from ..core.device_manager import Device
from ..responsive_toolbar import ResponsiveToolbar
from ..material_icons import material_icon
import csv
import io
import re
import json
import os
'''
body = "".join(view_lines[0:101]) + "".join(view_lines[705:])
with open(dst, "w", encoding="utf-8") as out:
    out.write(header)
    out.write(body)
print("Written", dst)
