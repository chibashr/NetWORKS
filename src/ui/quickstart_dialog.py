#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Quickstart dialog shown when no plugins are loaded.
Explains the program, plugins, and how to get started.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


class QuickstartDialog(QDialog):
    """
    Quickstart tutorial shown when no plugins are loaded.
    User can skip, disable via checkbox, or open Plugin Manager.
    """

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.config = getattr(app, "config", None)

        self.setWindowTitle("NetWORKS Quickstart")
        self.setMinimumWidth(480)
        self.setMinimumHeight(420)
        self.resize(520, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("Get the Most Out of NetWORKS")
        header.setStyleSheet("font-size: 14pt; font-weight: 600;")
        layout.addWidget(header)

        intro = QLabel(
            "The real power of NetWORKS comes from plugins. Right now no plugins "
            "are loaded in this workspace. Here's a quick guide to get started."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: palette(mid);")
        layout.addWidget(intro)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # Where to find plugins
        find_section = self._section(
            "Where to Find Plugins",
            "Go to Tools → Plugin Manager to browse, install, and enable plugins. "
            "Each workspace remembers which plugins you load. Enable plugins for "
            "this workspace from the Plugin Manager."
        )
        content_layout.addWidget(find_section)

        # How to configure
        config_section = self._section(
            "How to Configure Plugins",
            "Plugin configuration is in Settings (File → Settings). The External "
            "Plugins Directory under General points to your plugins folder. "
            "Each plugin may also have its own settings accessible from the "
            "Plugin Manager or from the plugin's panel."
        )
        content_layout.addWidget(config_section)

        # Documentation
        docs_section = self._section(
            "Documentation",
            "Help → Documentation opens the in-app documentation hub. It includes "
            "user guides, API docs, and plugin-specific documentation when plugins "
            "are loaded. See docs/ in the project for full guides."
        )
        content_layout.addWidget(docs_section)

        # Program overview
        overview_section = self._section(
            "What NetWORKS Offers",
            "• Dockable widgets: Panels can be docked, floated, or tabbed.\n"
            "• Device table: Central list of devices with properties and bulk actions.\n"
            "• Importing: File → Import Devices for CSV/text device onboarding.\n"
            "• Workspaces: Each workspace has its own devices, groups, and plugins."
        )
        content_layout.addWidget(overview_section)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # Don't show again checkbox
        self.dont_show_check = QCheckBox("Don't show this quickstart again")
        self.dont_show_check.setChecked(False)
        layout.addWidget(self.dont_show_check)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        skip_btn = QPushButton("Skip")
        skip_btn.setDefault(True)
        skip_btn.clicked.connect(self._on_skip)
        open_pm_btn = QPushButton("Open Plugin Manager")
        open_pm_btn.clicked.connect(self._on_open_plugin_manager)
        btn_layout.addWidget(skip_btn)
        btn_layout.addWidget(open_pm_btn)
        layout.addLayout(btn_layout)

    def _section(self, title, body):
        """Create a titled section block."""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-weight: 600;")
        layout.addWidget(title_lbl)
        body_lbl = QLabel(body)
        body_lbl.setWordWrap(True)
        body_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(body_lbl)
        return frame

    def _on_skip(self):
        """Dismiss and optionally disable future quickstarts."""
        if self.dont_show_check.isChecked() and self.config:
            self.config.set("ui.show_quickstart_on_no_plugins", False)
            self.config.save()
        self.accept()

    def _on_open_plugin_manager(self):
        """Open Plugin Manager and close quickstart."""
        if self.dont_show_check.isChecked() and self.config:
            self.config.set("ui.show_quickstart_on_no_plugins", False)
            self.config.save()
        # Defer opening so dialog closes first
        mw = getattr(self.app, "main_window", None)
        if mw and hasattr(mw, "on_plugin_manager"):
            QTimer.singleShot(0, mw.on_plugin_manager)
        self.accept()
