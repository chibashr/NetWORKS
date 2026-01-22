#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Material icon helpers (Google Material Icons via qtawesome when available).
"""

from loguru import logger
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

try:
    import qtawesome as qta
    HAS_QTA = True
except ImportError:
    HAS_QTA = False


def material_icon(name, widget=None, fallback_standard=None):
    """Return a Material icon with optional fallback to Qt standard icons."""
    icon = QIcon()
    if HAS_QTA:
        try:
            icon = qta.icon(f"md.{name}")
        except Exception as exc:
            logger.debug("Material icon lookup failed for {}: {}", name, exc)
    if not icon.isNull():
        return icon
    if fallback_standard is not None:
        style = widget.style() if widget is not None else QApplication.style()
        return style.standardIcon(fallback_standard)
    return icon
