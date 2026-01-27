#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Template storage for Template Manager plugin.
Per-workspace storage under workspaces/<workspace>/plugins/template_manager/templates.json.
"""

import json
import uuid
from pathlib import Path

from loguru import logger


def default_template():
    """Return a new template dict with required fields."""
    return {
        "id": str(uuid.uuid4()),
        "name": "New Template",
        "description": "",
        "source_command_ref": None,
        "body": "",
        "created_at": None,
        "updated_at": None,
    }


class TemplateStorage:
    """Load/save templates.json per workspace. Mirrors Report Generator storage pattern."""

    def __init__(self, device_manager):
        self.device_manager = device_manager
        self._cached_workspace = None
        self._templates = []

    def _templates_path(self):
        workspace = self.device_manager.current_workspace or "default"
        base_dir = (
            Path(self.device_manager.workspaces_dir)
            / workspace
            / "plugins"
            / "template_manager"
        )
        return base_dir / "templates.json"

    def ensure_loaded(self):
        workspace = self.device_manager.current_workspace or "default"
        if workspace != self._cached_workspace:
            self.load()
        return self._templates

    def load(self):
        path = self._templates_path()
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, list):
                    self._templates = data
                elif isinstance(data, dict) and "templates" in data:
                    self._templates = data.get("templates", [])
                else:
                    self._templates = []
            except Exception as exc:
                logger.error(f"Template Manager: Failed to load templates: {exc}")
                self._templates = []
        else:
            self._templates = []
        self._cached_workspace = self.device_manager.current_workspace or "default"
        return self._templates

    def save(self, templates):
        path = self._templates_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(templates, handle, indent=2)
            self._templates = templates
            self._cached_workspace = self.device_manager.current_workspace or "default"
            return True
        except Exception as exc:
            logger.error(f"Template Manager: Failed to save templates: {exc}")
            return False
