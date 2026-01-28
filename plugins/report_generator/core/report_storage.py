# Report Generator per-workspace report storage.

import json
from pathlib import Path

from loguru import logger


class ReportStorage:
    """Load/save report definitions per workspace under plugins/report_generator."""

    def __init__(self, device_manager):
        self.device_manager = device_manager
        self._cached_workspace = None
        self._reports = []

    def _reports_path(self):
        workspace = self.device_manager.current_workspace or "default"
        base_dir = (
            Path(self.device_manager.workspaces_dir)
            / workspace
            / "plugins"
            / "report_generator"
        )
        return base_dir / "reports.json"

    def ensure_loaded(self):
        workspace = self.device_manager.current_workspace or "default"
        if workspace != self._cached_workspace:
            self.load()
        return self._reports

    def load(self):
        path = self._reports_path()
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, list):
                    self._reports = data
                else:
                    self._reports = []
            except Exception as exc:
                logger.error(f"Report Generator: Failed to load reports: {exc}")
                self._reports = []
        else:
            self._reports = []
        self._cached_workspace = self.device_manager.current_workspace or "default"
        return self._reports

    def save(self, reports):
        path = self._reports_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(reports, handle, indent=2)
            self._reports = reports
            self._cached_workspace = self.device_manager.current_workspace or "default"
            return True
        except Exception as exc:
            logger.error(f"Report Generator: Failed to save reports: {exc}")
            return False
