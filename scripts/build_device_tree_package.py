#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build device_tree package from device_tree.py: model, view, panel."""
import os
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(base, "src", "ui", "device_tree.py")
dst_dir = os.path.join(base, "src", "ui", "device_tree")
with open(src, "r", encoding="utf-8") as f:
    lines = f.readlines()

# DeviceTreeModel: lines 102-627 (0-based 101-626)
model_header = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device tree model for NetWORKS.
"""

from .device_tree_item import DeviceTreeItem

from loguru import logger
from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex, Slot
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap, QMimeData
from PySide6.QtWidgets import QApplication, QStyle

import json

from ..material_icons import material_icon
'''
model_body = "".join(lines[101:627])
model_path = os.path.join(dst_dir, "device_tree_model.py")
with open(model_path, "w", encoding="utf-8") as out:
    out.write(model_header)
    out.write(model_body)
print("Written", model_path)

# DeviceTreeView: lines 680-1522 (0-based 679-1521)
view_header = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device tree view for NetWORKS.
"""

from loguru import logger
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QSize, QSettings
from PySide6.QtWidgets import (
    QTreeView, QAbstractItemView, QMenu, QWidget, QDialog, QVBoxLayout,
    QHBoxLayout, QTabWidget, QFileDialog, QLabel, QPushButton, QTextEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFormLayout, QGroupBox, QCheckBox, QWizard, QWizardPage, QMessageBox,
    QDialogButtonBox, QInputDialog, QApplication, QButtonGroup, QRadioButton,
    QPlainTextEdit, QToolButton, QDockWidget, QSizePolicy, QStyle,
)
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap

from ...core.device_manager import Device
from ..material_icons import material_icon

import os
import json
'''
view_body = "".join(lines[679:1522])
view_path = os.path.join(dst_dir, "device_tree_view.py")
with open(view_path, "w", encoding="utf-8") as out:
    out.write(view_header)
    out.write(view_body)
print("Written", view_path)

# DeviceTreePanel: lines 1524-1641 (0-based 1523-1640)
panel_header = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device tree panel: search, compact mode, filter controls around the tree view.
"""

from .device_tree_model import DeviceTreeModel
from .device_tree_filter import DeviceTreeFilterProxyModel
from .device_tree_view import DeviceTreeView

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QToolButton, QMenu, QDockWidget, QStyle,
)
from ..material_icons import material_icon
'''
panel_body = "".join(lines[1523:1641])
panel_path = os.path.join(dst_dir, "device_tree_panel.py")
with open(panel_path, "w", encoding="utf-8") as out:
    out.write(panel_header)
    out.write(panel_body)
print("Written", panel_path)
print("Done.")
