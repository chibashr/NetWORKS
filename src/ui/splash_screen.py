#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Splash screen for NetWORKS
"""

from PySide6.QtWidgets import QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QWidget
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont
from PySide6.QtCore import Qt, QSize, QRect
from loguru import logger

from .theme import get_current_theme_tokens


class SplashScreen(QSplashScreen):
    """Splash screen shown during application startup"""

    def __init__(self, version="0.0.0", app=None):
        """Initialize the splash screen.

        Args:
            version: Application version string (from manifest). Defaults to "0.0.0" if not provided.
            app: Optional QApplication instance for theme-aware styling.
        """
        logger.debug("Initializing splash screen")
        self.version = version
        tokens = get_current_theme_tokens(app)
        
        # Create a pixmap for the splash screen
        splash_size = QSize(600, 400)
        pixmap = QPixmap(splash_size)
        pixmap.fill(Qt.white)
        
        # Create a painter to draw on the pixmap
        painter = QPainter(pixmap)
        
        # Set background color
        painter.fillRect(QRect(0, 0, splash_size.width(), splash_size.height()), QColor(245, 245, 245))
        
        # Draw the application name
        title_font = QFont("Arial", 40, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor(0, 120, 215))
        painter.drawText(QRect(0, 50, splash_size.width(), 100), Qt.AlignCenter, "NetWORKS")
        
        # Draw subtitle
        subtitle_font = QFont("Arial", 14)
        painter.setFont(subtitle_font)
        painter.setPen(QColor(80, 80, 80))
        painter.drawText(QRect(0, 120, splash_size.width(), 50), Qt.AlignCenter, "Device Management Platform")
        
        # Draw version
        version_font = QFont("Arial", 10)
        painter.setFont(version_font)
        painter.setPen(QColor(100, 100, 100))
        painter.drawText(QRect(0, splash_size.height() - 30, splash_size.width(), 20), Qt.AlignCenter, f"Version {self.version}")
        
        # Finish painting
        painter.end()
        
        super().__init__(pixmap)
        
        # Create a widget to hold the progress bar and status label
        self.content_widget = QWidget(self)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(20, 0, 20, 40)
        
        # Create status label
        self.status_label = QLabel("Starting...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {tokens.text}; font-size: 12px;")

        # Create progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {tokens.surface_alt};
                border: 1px solid {tokens.border};
                border-radius: 0;
                height: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {tokens.accent};
                border-radius: 0;
            }}
        """)
        
        # Add widgets to layout
        self.content_layout.addStretch()
        self.content_layout.addWidget(self.status_label)
        self.content_layout.addWidget(self.progress_bar)
        
        # Position the content widget
        self.content_widget.setGeometry(0, 0, splash_size.width(), splash_size.height())
        
        logger.debug("Splash screen initialized")

    def update_progress(self, percentage=None, message=None, current_step=None, total_steps=None):
        """
        Update the progress bar and status message
        
        Can be called in two ways:
        1. update_progress(percentage, message)
        2. update_progress(message, current_step, total_steps)  # Legacy format
        """
        # Handle the case where the method is called with the legacy format
        if percentage is not None and message is None and current_step is not None and total_steps is not None:
            # Old format: update_progress(message, current_step, total_steps)
            message = percentage
            percentage = int((current_step / total_steps) * 100)
        
        # Update progress bar if percentage provided
        if percentage is not None:
            self.progress_bar.setValue(percentage)
        
        # Update message if provided
        if message is not None:
            self.status_label.setText(message)
            
        # Force a repaint to update the display
        self.repaint()
        
        # Log the progress update
        if message:
            logger.debug(f"Splash progress: {self.progress_bar.value()}% - {message}")
        else:
            logger.debug(f"Splash progress: {self.progress_bar.value()}%")

    def mousePressEvent(self, event):
        """Prevent closing the splash screen when clicked"""
        pass 