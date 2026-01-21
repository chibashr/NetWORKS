#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Responsive toolbar container that stacks controls when width is constrained.
"""

from PySide6.QtWidgets import QWidget, QBoxLayout, QPushButton, QToolButton, QSizePolicy
from PySide6.QtCore import Qt


class ResponsiveToolbar(QWidget):
    """Toolbar container that stacks controls when width is constrained."""

    def __init__(self, parent=None, breakpoint=320):
        super().__init__(parent)
        self._breakpoint = breakpoint
        self._is_vertical = False
        self._widgets = []
        self._original_policies = {}

        self._layout = QBoxLayout(QBoxLayout.LeftToRight)
        self._layout.setContentsMargins(0, 0, 0, 4)
        self._layout.setSpacing(6)
        self._layout.setAlignment(Qt.AlignVCenter)
        self.setLayout(self._layout)

    def addWidget(self, widget, stretch=0):
        self._layout.addWidget(widget, stretch)
        self._widgets.append(widget)
        self._apply_compact_policy(widget)

    def addStretch(self, stretch=0):
        self._layout.addStretch(stretch)

    def setSpacing(self, spacing):
        self._layout.setSpacing(spacing)

    def setContentsMargins(self, left, top, right, bottom):
        self._layout.setContentsMargins(left, top, right, bottom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_layout_direction(event.size().width())

    def _update_layout_direction(self, width):
        should_stack = width < self._breakpoint
        if should_stack == self._is_vertical:
            return

        self._layout.setDirection(
            QBoxLayout.TopToBottom if should_stack else QBoxLayout.LeftToRight
        )
        self._layout.setAlignment(
            (Qt.AlignTop | Qt.AlignLeft) if should_stack else Qt.AlignVCenter
        )
        self._is_vertical = should_stack
        for widget in self._widgets:
            self._apply_compact_policy(widget)

    def _apply_compact_policy(self, widget):
        if not isinstance(widget, (QPushButton, QToolButton)):
            return

        if widget not in self._original_policies:
            self._original_policies[widget] = widget.sizePolicy()

        if self._is_vertical:
            widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        else:
            widget.setSizePolicy(self._original_policies[widget])