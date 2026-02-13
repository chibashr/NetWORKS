#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SNMP Collector panel layout.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTabWidget,
)
from PySide6.QtCore import Qt

from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES
from src.ui.plugin_widgets import wrap_in_scroll_area

from .widgets.trap_receiver_widget import TrapReceiverWidget
from .widgets.snmp_poll_widget import SnmpPollWidget
from .widgets.ingestion_widget import IngestionWidget
from .widgets.traps_table_widget import TrapsTableWidget


def build_snmp_panel(plugin):
    """Build the SNMP dock panel with tabbed layout. Returns widget only; main window creates dock."""
    container = QWidget()
    mark_plugin_ui(container)
    layout = QVBoxLayout(container)
    pad = PLUGIN_UI_SIZES["section_padding"]
    layout.setContentsMargins(pad, 0, pad, 0)
    layout.setSpacing(PLUGIN_UI_SIZES["collapsible_stack_spacing"])

    tab_widget = QTabWidget()
    tab_widget.addTab(wrap_in_scroll_area(TrapReceiverWidget(plugin)), "Trap Receiver")
    tab_widget.addTab(wrap_in_scroll_area(SnmpPollWidget(plugin)), "SNMP Poll")
    tab_widget.addTab(wrap_in_scroll_area(IngestionWidget(plugin)), "Ingestion")
    tab_widget.addTab(wrap_in_scroll_area(TrapsTableWidget(plugin)), "Collected Traps")
    layout.addWidget(tab_widget)

    container.setMinimumHeight(200)
    container.setMaximumHeight(420)

    return container
