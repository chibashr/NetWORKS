#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Overflow-aware toolbar that collapses lower-priority actions into a menu.
"""

from loguru import logger
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QStyle, QToolBar, QToolButton

from .material_icons import material_icon


class ScalableToolbar(QToolBar):
    """Toolbar that moves actions into an overflow menu when space is tight."""

    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self._overflow_action = None
        self._is_updating = False
        self._overflow_menu = QMenu(self)
        self._overflow_button = QToolButton(self)
        self._overflow_button.setAutoRaise(True)
        self._overflow_button.setPopupMode(QToolButton.InstantPopup)
        self._overflow_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._overflow_button.setToolTip("More actions")
        self._overflow_button.setMenu(self._overflow_menu)
        self._overflow_button.setIcon(self._resolve_overflow_icon())

        self._overflow_action = super().addWidget(self._overflow_button)
        self._overflow_action.setVisible(False)
        self._expanded_toolbutton_style = self.toolButtonStyle()

    def add_toolbar_action(self, action, priority=None):
        if priority is not None:
            action.setProperty("toolbar_priority", priority)
        self._ensure_action_tooltip(action)
        self._ensure_action_icon(action)
        self.insertAction(self._overflow_action, action)
        self._update_overflow()
        return action

    def add_toolbar_separator(self):
        separator = self.insertSeparator(self._overflow_action)
        self._update_overflow()
        return separator

    def actionEvent(self, event):
        try:
            super().actionEvent(event)
        except (RuntimeError, AttributeError):
            # Qt objects may be deleted during shutdown
            return
        
        if event.type() in (QEvent.ActionAdded, QEvent.ActionRemoved, QEvent.ActionChanged):
            if self._overflow_action is None:
                return
            if self._is_updating:
                return
            try:
                if event.type() == QEvent.ActionAdded:
                    action = event.action()
                    if action and action is not self._overflow_action:
                        actions = self.actions()
                        if actions and actions[-1] is not self._overflow_action:
                            self.removeAction(action)
                            self.insertAction(self._overflow_action, action)
                self._update_overflow()
            except (RuntimeError, AttributeError):
                # Qt objects may be deleted during shutdown
                return

    def setToolButtonStyle(self, style):
        self._expanded_toolbutton_style = style
        super().setToolButtonStyle(style)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overflow()

    def _resolve_overflow_icon(self):
        icon = material_icon("more_horiz", self)
        if not icon.isNull():
            return icon
        icon = QIcon.fromTheme("view-more-symbolic")
        if icon.isNull():
            icon = material_icon("more_horiz", self, QStyle.SP_ToolBarHorizontalExtensionButton)
        return icon

    def _action_priority(self, action):
        priority = action.property("toolbar_priority")
        try:
            return int(priority)
        except (TypeError, ValueError):
            return 0

    def _ensure_action_tooltip(self, action):
        if not action.toolTip():
            label = action.text()
            if label:
                action.setToolTip(label)

    def _ensure_action_icon(self, action):
        if not action.icon().isNull():
            return
        logger.warning("Toolbar action missing icon: {}", action.text())
        action.setIcon(material_icon("description", self, QStyle.SP_FileIcon))

    def _content_width(self, actions):
        visible_actions = [action for action in actions if action.isVisible()]
        if not visible_actions:
            return 0
        rects = [self.actionGeometry(action) for action in visible_actions]
        rects = [rect for rect in rects if not rect.isNull()]
        if not rects:
            return 0
        return max(rect.right() for rect in rects) + 1

    def _layout_toolbar(self):
        layout = self.layout()
        if layout:
            layout.activate()

    def _apply_compact_mode(self, enabled):
        target_style = Qt.ToolButtonIconOnly if enabled else self._expanded_toolbutton_style
        if self.toolButtonStyle() != target_style:
            super().setToolButtonStyle(target_style)

    def _apply_separator_visibility(self, actions):
        visible_indices = [
            index for index, action in enumerate(actions)
            if action.isVisible() and not action.isSeparator()
        ]
        if not visible_indices:
            for action in actions:
                if action.isSeparator():
                    action.setVisible(False)
            return

        first_visible = min(visible_indices)
        last_visible = max(visible_indices)
        for index, action in enumerate(actions):
            if not action.isSeparator():
                continue
            action.setVisible(first_visible < index < last_visible)

    def _populate_overflow_menu(self, actions):
        self._overflow_menu.clear()
        pending_separator = False
        has_items = False
        for action in actions:
            if action is self._overflow_action:
                continue
            if action.isSeparator():
                pending_separator = True
                continue
            if action.isVisible():
                pending_separator = False
                continue
            if pending_separator and has_items:
                self._overflow_menu.addSeparator()
                pending_separator = False
            self._overflow_menu.addAction(action)
            has_items = True
        self._overflow_action.setVisible(has_items)

    def _update_overflow(self):
        if self._is_updating:
            return
        
        # Guard against accessing deleted Qt objects during shutdown
        if self._overflow_action is None:
            return
        
        try:
            # Check if the overflow action's widget still exists
            if not hasattr(self._overflow_action, 'isVisible') or not hasattr(self._overflow_action, 'setVisible'):
                return
        except (RuntimeError, AttributeError):
            # Qt object may be deleted
            return
        
        self._is_updating = True
        try:
            actions = [action for action in self.actions() if action is not self._overflow_action]
            if not actions:
                if self._overflow_action:
                    self._overflow_action.setVisible(False)
                if self._overflow_menu:
                    self._overflow_menu.clear()
                self._is_updating = False
                return

            for action in actions:
                if action:
                    action.setVisible(True)
            if self._overflow_action:
                self._overflow_action.setVisible(False)
            self._apply_separator_visibility(actions)
            self._apply_compact_mode(False)
            self._layout_toolbar()
        except (RuntimeError, AttributeError) as e:
            # Qt objects may be deleted during shutdown
            logger.debug(f"Error updating overflow menu during shutdown: {e}")
            self._is_updating = False
            return

        if self._content_width(actions) <= self.width():
            self._populate_overflow_menu(actions)
            self._is_updating = False
            return

        # Hide labels before collapsing actions into overflow.
        self._apply_compact_mode(True)
        self._layout_toolbar()
        if self._content_width(actions) <= self.width():
            self._populate_overflow_menu(actions)
            self._is_updating = False
            return

        self._overflow_action.setVisible(True)
        self._layout_toolbar()
        available_width = self.width() - self._overflow_button.sizeHint().width()
        available_width = max(0, available_width)

        candidates = [action for action in actions if not action.isSeparator()]
        while candidates and self._content_width(actions) > available_width:
            candidate = min(candidates, key=self._action_priority)
            candidate.setVisible(False)
            candidates.remove(candidate)
            self._apply_separator_visibility(actions)
            self._layout_toolbar()

        self._populate_overflow_menu(actions)
        self._is_updating = False