#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Custom Commands dialog for Command Manager.

Allows entering one or more lines of commands to run in order.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QPlainTextEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QFont, QPainter

from src.ui.plugin_ui_theme import mark_plugin_ui


class LineNumberArea(QWidget):
    """Line number widget for the code editor."""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        
    def sizeHint(self):
        return self.editor.line_number_area_width(), 0
        
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """Text editor with line numbers."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)
        self.highlight_current_line()
        
    def line_number_area_width(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num /= 10
            digits += 1
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
        
    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
        
    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(0, 0, self.line_number_area_width(), cr.height())
        
    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.palette().color(self.palette().ColorRole.Base))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingGeometry(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self.palette().color(self.palette().ColorRole.Text))
                painter.drawText(0, top, self.line_number_area.width() - 3, self.fontMetrics().height(),
                               Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingGeometry(block).height())
            block_number += 1
            
    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = self.palette().color(self.palette().ColorRole.AlternateBase)
            selection.format.setBackground(line_color)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)


class CustomCommandsDialog(QDialog):
    """Multi-line custom command entry dialog."""

    def __init__(self, parent=None, initial_text="", title="Custom Commands"):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.setWindowTitle(title)
        self.resize(700, 420)
        self._build_ui(initial_text=initial_text)

    def _build_ui(self, initial_text=""):
        layout = QVBoxLayout(self)

        help_row = QHBoxLayout()
        help_row.addWidget(
            QLabel(
                "Enter one command per line. Commands run in order on each device, then the next device."
            )
        )
        help_row.addStretch()
        layout.addLayout(help_row)

        # Use code editor with line numbers
        self.text = CodeEditor()
        self.text.setPlaceholderText("e.g.\nconf t\ninterface gi0/1\ndescription {{ip_address}}\nend\nwr mem")
        self.text.setPlainText(initial_text or "")
        font = QFont("Courier New", 9)
        self.text.setFont(font)
        layout.addWidget(self.text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.run_btn = QPushButton("Run")
        buttons.addButton(self.run_btn, QDialogButtonBox.AcceptRole)
        buttons.rejected.connect(self.reject)
        self.run_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)

    def get_lines(self):
        """Return non-empty stripped lines."""
        raw = self.text.toPlainText() or ""
        return [ln.strip() for ln in raw.splitlines() if ln.strip()]

