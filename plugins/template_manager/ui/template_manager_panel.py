#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Template Manager panel: Templates + Details on one row, Source (with Load from CM),
searchable Variables, Export; right side = device preview.
"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QToolButton,
    QLabel,
    QFormLayout,
    QAbstractItemView,
    QMessageBox,
    QFileDialog,
    QSplitter,
    QComboBox,
    QMenu,
    QDialog,
    QDialogButtonBox,
    QStyle,
)
from PySide6.QtGui import QTextCursor, QAction
from src.ui.plugin_ui_theme import mark_plugin_ui
from src.ui.material_icons import material_icon
from plugins.template_manager.core.template_engine import STANDARD_DEVICE_PROPERTIES
from plugins.template_manager.core.template_storage import default_template
from plugins.template_manager.ui.template_preview_widget import TemplatePreviewWidget
import uuid
import json
from datetime import datetime


def _collect_device_properties(device_manager):
    """Standard + custom properties from workspace devices. Mirrors Report Generator."""
    names = set()
    for d in (device_manager.get_devices() or []):
        for k in (d.get_properties() or {}).keys():
            names.add(k)
    standard = [p for p in STANDARD_DEVICE_PROPERTIES if p in names]
    custom = sorted(p for p in names if p not in STANDARD_DEVICE_PROPERTIES)
    return standard, custom


class TemplateManagerPanel(QWidget):
    """Templates + Details same row; Source (Load from CM); searchable Variables; Export; right = preview."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.plugin = plugin
        self.storage = plugin.storage
        self._templates = []
        self._current_id = None
        self._build_ui()
        self._refresh_templates_list()
        self._refresh_preview_devices()
        self.preview_widget.selection_in_preview_triggered.connect(
            self._on_preview_selection_from_widget
        )

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(4, 4, 4, 4)
        main.setSpacing(4)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # —— Left: details (top) + templates (bottom) ——
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        details_group = QGroupBox("Template Details")
        details_layout = QFormLayout(details_group)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Template name")
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Description (optional)")
        details_layout.addRow("Name:", self.name_edit)
        details_layout.addRow("Description:", self.desc_edit)
        left_layout.addWidget(details_group)

        templates_group = QGroupBox("Templates")
        templates_layout = QVBoxLayout(templates_group)
        self.templates_list = QListWidget()
        # Let the global theme (theme.py) control background/selection colors
        # so this matches the Workspace Manager list appearance.
        self.templates_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.templates_list.currentItemChanged.connect(self._on_template_selected)
        self.templates_list.setMinimumWidth(160)
        templates_layout.addWidget(self.templates_list, 1)
        btn_row = QHBoxLayout()
        for label, slot in [
            ("New", self._new_template),
            ("Duplicate", self._duplicate_template),
            ("Delete", self._delete_template),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        templates_layout.addLayout(btn_row)
        left_layout.addWidget(templates_group, 1)
        splitter.addWidget(left_widget)

        # —— Middle: Source / Body + Variables ——
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)

        # Source / Body + Load from Command Manager
        source_group = QGroupBox("Source / Body")
        source_layout = QVBoxLayout(source_group)
        load_row = QHBoxLayout()

        # Icon-only Save button (square, will be sized to match standard button height)
        self.save_btn = QToolButton()
        self.save_btn.setToolTip("Save template (name/description/source)")
        self.save_btn.setIcon(material_icon("save", self, QStyle.SP_DialogSaveButton))
        self.save_btn.setAutoRaise(True)
        self.save_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.save_btn.setIconSize(QSize(16, 16))
        # Match theme.py inline icon-only tool button styling
        self.save_btn.setProperty("iconOnlyInline", True)
        self.save_btn.clicked.connect(self._save_current_template)

        # Icon-only Insert Variable button (square, same height as other buttons)
        self.insert_var_btn = QToolButton()
        self.insert_var_btn.setToolTip("Insert variable…")
        self.insert_var_btn.setIcon(material_icon("code", self, QStyle.SP_CommandLink))
        self.insert_var_btn.setAutoRaise(True)
        self.insert_var_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.insert_var_btn.setIconSize(QSize(16, 16))
        # Match theme.py inline icon-only tool button styling
        self.insert_var_btn.setProperty("iconOnlyInline", True)
        self.insert_var_btn.clicked.connect(self._open_variable_picker_dialog)
        # Add icon buttons on the far left
        load_row.addWidget(self.save_btn)
        load_row.addWidget(self.insert_var_btn)
        # Main text button to the right of icons
        self.load_cm_btn = QPushButton("Load Source from Command Manager")
        self.load_cm_btn.clicked.connect(self._load_from_command_manager)
        load_row.addWidget(self.load_cm_btn)

        # Let theme stylesheet control exact sizing based on iconOnlyInline property
        self.find_btn = QPushButton("Find/Replace…")
        self.find_btn.setToolTip("Find and replace text in the source/body editor.")
        self.find_btn.clicked.connect(self._open_find_replace_dialog)
        load_row.addWidget(self.find_btn)
        load_row.addStretch()
        source_layout.addLayout(load_row)
        self.body_edit = QTextEdit()
        self.body_edit.setPlaceholderText("Paste or type template text. Use {{property_name}} for device fields. Right-click to insert variables.")
        # Slightly smaller minimum height so the overall dialog can be more compact.
        self.body_edit.setMinimumHeight(80)
        self.body_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self.body_edit.customContextMenuRequested.connect(self._on_body_context_menu)
        source_layout.addWidget(self.body_edit)
        middle_layout.addWidget(source_group, 1)
        splitter.addWidget(middle_widget)

        # —— Right: Preview ——
        self.preview_widget = TemplatePreviewWidget(self.plugin, self.body_edit, self)
        splitter.addWidget(self.preview_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        main.addWidget(splitter)
        # Export buttons and status label are created here but added to the
        # dialog layout so they can share a single bottom row with the Close
        # button.
        self.export_file_btn = QPushButton("Export template file…")
        self.export_file_btn.clicked.connect(self._export_template_file)
        self.send_cm_btn = QPushButton("Load into Command Manager")
        self.send_cm_btn.clicked.connect(self._load_into_command_manager_direct)
        self.batch_export_btn = QPushButton("Batch export…")
        self.batch_export_btn.clicked.connect(self._open_batch_export_dialog)
        self.status_label = QLabel("")
        self.status_label.setProperty("plugin_ui_muted", "true")

    def _refresh_preview_devices(self):
        self.preview_widget.refresh_devices()

    def _on_preview_selection_from_widget(self, plain):
        """When text is selected in the preview, select the same text in the body editor."""
        if not plain:
            return
        # Selects the first occurrence of the preview selection in the body; if the same text appears multiple times, only the first match is used.
        body = self.body_edit.toPlainText()
        pos = body.find(plain)
        if pos == -1:
            return
        ec = self.body_edit.textCursor()
        ec.setPosition(pos)
        ec.setPosition(pos + len(plain), QTextCursor.KeepAnchor)
        self.body_edit.setTextCursor(ec)
        self.body_edit.setFocus()

    def _on_body_context_menu(self, pos):
        """Right-click on body: show Insert variable submenu."""
        menu = QMenu(self.body_edit)
        insert_action = QAction("Insert variable…", self.body_edit)
        insert_action.triggered.connect(self._open_variable_picker_dialog)
        menu.addAction(insert_action)
        menu.addSeparator()
        find_action = QAction("Find/Replace…", self.body_edit)
        find_action.triggered.connect(self._open_find_replace_dialog)
        menu.addAction(find_action)
        menu.exec(self.body_edit.mapToGlobal(pos))

    def _load_from_command_manager(self):
        from plugins.template_manager.ui.command_output_picker import CommandOutputPickerDialog
        d = CommandOutputPickerDialog(self.plugin, self)
        if d.exec() and d.chosen_output() is not None:
            self.body_edit.setPlainText(d.chosen_output())

    def _refresh_templates_list(self):
        self._templates = self.storage.ensure_loaded()
        self.templates_list.clear()
        for t in self._templates:
            name = (t.get("name") or "Unnamed").strip()
            desc = (t.get("description") or "").strip()[:40]
            label = f"{name}" + (f" — {desc}" if desc else "")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, t.get("id"))
            self.templates_list.addItem(item)
        self._update_status()

    def _current_template(self):
        if not self._current_id:
            return None
        for t in self._templates:
            if t.get("id") == self._current_id:
                return t
        return None

    def _on_template_selected(self, current, _previous):
        if not current:
            self._current_id = None
            self.name_edit.clear()
            self.desc_edit.clear()
            self.body_edit.clear()
            return
        self._current_id = current.data(Qt.UserRole)
        t = self._current_template()
        if not t:
            return
        self.name_edit.setText(t.get("name") or "")
        self.desc_edit.setText(t.get("description") or "")
        self.body_edit.setPlainText(t.get("body") or "")

    def _save_current_to_model(self):
        t = self._current_template()
        if not t:
            return
        t["name"] = self.name_edit.text().strip() or "Unnamed"
        t["description"] = self.desc_edit.text().strip()
        t["body"] = self.body_edit.toPlainText()
        t["updated_at"] = datetime.utcnow().isoformat() + "Z"
        if t.get("created_at") is None:
            t["created_at"] = t["updated_at"]
        self.storage.save(self._templates)
        self._refresh_templates_list()
        self._update_status()

    def _save_current_template(self):
        """Save the currently edited template (name, description, source/body)."""
        # Ensure there is a "current" template to save.
        if not self._current_id or not self._current_template():
            t = default_template()
            self._templates.append(t)
            self._current_id = t.get("id")
        current_id = self._current_id
        self._save_current_to_model()
        # Restore selection after refresh (refresh clears list and _current_id)
        if current_id:
            self._current_id = current_id
            for i in range(self.templates_list.count()):
                if self.templates_list.item(i).data(Qt.UserRole) == current_id:
                    self.templates_list.setCurrentRow(i)
                    break

    def _new_template(self):
        t = default_template()
        self._templates.append(t)
        self.storage.save(self._templates)
        self._refresh_templates_list()
        for i in range(self.templates_list.count()):
            if self.templates_list.item(i).data(Qt.UserRole) == t["id"]:
                self.templates_list.setCurrentRow(i)
                break
        self.name_edit.setText(t.get("name") or "")
        self.desc_edit.setText(t.get("description") or "")
        self.body_edit.setPlainText(t.get("body") or "")

    def _duplicate_template(self):
        t = self._current_template()
        if not t:
            return
        import copy
        new_t = copy.deepcopy(t)
        new_t["id"] = str(uuid.uuid4())
        new_t["name"] = (t.get("name") or "Template") + " (Copy)"
        new_t["created_at"] = datetime.utcnow().isoformat() + "Z"
        new_t["updated_at"] = new_t["created_at"]
        self._templates.append(new_t)
        self.storage.save(self._templates)
        self._refresh_templates_list()
        for i in range(self.templates_list.count()):
            if self.templates_list.item(i).data(Qt.UserRole) == new_t["id"]:
                self.templates_list.setCurrentRow(i)
                break

    def _delete_template(self):
        t = self._current_template()
        if not t:
            return
        if QMessageBox.question(
            self,
            "Delete Template",
            f"Delete template \"{t.get('name', 'Unnamed')}\"?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self._templates = [x for x in self._templates if x.get("id") != self._current_id]
        self.storage.save(self._templates)
        self._current_id = None
        self._refresh_templates_list()
        self.name_edit.clear()
        self.desc_edit.clear()
        self.body_edit.clear()

    def _insert_at_cursor(self, text):
        self.body_edit.insertPlainText(text)

    def _open_variable_picker_dialog(self):
        d = VariablePickerDialog(self.plugin, parent=self)
        if d.exec() and d.chosen_variable():
            self._insert_at_cursor(f"{{{{{d.chosen_variable()}}}}}")

    def _open_find_replace_dialog(self):
        # Prefill find with current selection if present.
        sel = self.body_edit.textCursor().selectedText()
        sel = (sel or "").replace("\u2029", "\n").strip()
        d = FindReplaceDialog(self.body_edit, initial_find=sel, parent=self)
        d.exec()


    def _update_status(self):
        n = len(self._templates)
        self.status_label.setText(f"{n} template(s)")

    def _export_template_file(self):
        self._save_current_to_model()
        selected = self._current_template()
        to_export = [selected] if selected else self._templates
        if not to_export:
            QMessageBox.information(self, "Export", "No templates to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export template file", "", "Template file (*.json);;All Files (*)"
        )
        if not path:
            return
        payload = {"version": 1, "templates": to_export}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            QMessageBox.information(self, "Export", f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export", f"Export failed: {e}")

    def _load_into_command_manager_direct(self):
        """Load the current template into Command Manager as a command set (one command per line). No dialog."""
        t = self._current_template()
        if not t:
            QMessageBox.information(
                self, "Load into Command Manager", "Select a template to load."
            )
            return
        current_id = self._current_id
        self._save_current_to_model()
        # Restore selection after refresh (refresh clears list and _current_id)
        for i in range(self.templates_list.count()):
            if self.templates_list.item(i).data(Qt.UserRole) == current_id:
                self.templates_list.setCurrentRow(i)
                break
        body = (t.get("body") or "").strip()
        if not body:
            QMessageBox.information(
                self, "Load into Command Manager", "Template has no commands."
            )
            return
        info = self.plugin.app.plugin_manager.get_plugin("command_manager")
        if not info or not getattr(info, "instance", None):
            QMessageBox.warning(
                self,
                "Load into Command Manager",
                "Command Manager plugin is not loaded.",
            )
            return
        cmd_mgr = info.instance
        # Prefill Command Manager's Custom Commands dialog instead of creating a saved set.
        if hasattr(cmd_mgr, "pending_custom_commands_text"):
            cmd_mgr.pending_custom_commands_text = body
        cmd_mgr.open_dialog()
        # Close Template Manager so only Command Manager is visible
        top = self.window()
        if top and top.isWindow():
            top.close()

    def _open_batch_export_dialog(self, initial_devices=None):
        """Open batch export (expanded output for devices/group/subnet). initial_devices = list from context menu."""
        from plugins.template_manager.ui.batch_export_dialog import BatchExportDialog
        self._save_current_to_model()
        to_export = self.get_selected_templates_for_export()
        if not to_export:
            QMessageBox.information(self, "Batch export", "No templates selected.")
            return
        d = BatchExportDialog(self.plugin, to_export, initial_devices=initial_devices, parent=self)
        d.exec()

    def get_selected_templates_for_export(self):
        cur = self._current_template()
        if cur:
            return [cur]
        return self._templates


class VariablePickerDialog(QDialog):
    """Searchable variable list for inserting placeholders into the body editor."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent or plugin.main_window)
        mark_plugin_ui(self)
        self.setWindowTitle("Insert variable")
        self._chosen = None
        self._items = []  # list of (key, label)
        self.setMinimumSize(420, 440)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Search and select a variable to insert as a placeholder:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search variables…")
        self.search_edit.textChanged.connect(self._filter)
        layout.addWidget(self.search_edit)
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._use_current)
        layout.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        use_btn = QPushButton("Insert")
        use_btn.clicked.connect(self._use_current)
        btn_row.addWidget(use_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        dm = getattr(plugin, "device_manager", None)
        standard, custom = ([], []) if not dm else _collect_device_properties(dm)
        names = standard + custom if (standard or custom) else list(STANDARD_DEVICE_PROPERTIES)
        std_set = set(standard) if (standard or custom) else set(STANDARD_DEVICE_PROPERTIES)
        self._items = [(n, f"{n} (standard)" if n in std_set else n) for n in names]

        for key, label in self._items:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.list_widget.addItem(item)
        self._filter()

    def _filter(self):
        q = (self.search_edit.text() or "").strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            key = (item.data(Qt.UserRole) or "").lower()
            text = (item.text() or "").lower()
            item.setHidden(bool(q) and q not in key and q not in text)

    def _use_current(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        self._chosen = item.data(Qt.UserRole)
        self.accept()

    def chosen_variable(self):
        return self._chosen


class FindReplaceDialog(QDialog):
    """Lightweight find/replace for the template body editor (supports placeholders)."""

    def __init__(self, text_edit: QTextEdit, initial_find: str = "", parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.setWindowTitle("Find / Replace")
        self._edit = text_edit
        self.setMinimumSize(520, 160)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find… (e.g. {{ip_address}})")
        self.find_edit.setText(initial_find or "")
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with… (e.g. {{ip}})")
        form.addRow("Find:", self.find_edit)
        form.addRow("Replace:", self.replace_edit)
        layout.addLayout(form)

        row = QHBoxLayout()
        find_next = QPushButton("Find next")
        find_next.clicked.connect(self._find_next)
        replace_one = QPushButton("Replace")
        replace_one.clicked.connect(self._replace_one)
        replace_all = QPushButton("Replace all")
        replace_all.clicked.connect(self._replace_all)
        row.addWidget(find_next)
        row.addWidget(replace_one)
        row.addWidget(replace_all)
        row.addStretch()
        close_btns = QDialogButtonBox(QDialogButtonBox.Close)
        close_btns.rejected.connect(self.reject)
        row.addWidget(close_btns)
        layout.addLayout(row)

    def _needle(self):
        return (self.find_edit.text() or "")

    def _find_next(self):
        needle = self._needle()
        if not needle:
            return
        if not self._edit.find(needle):
            # Wrap to start and try again
            cur = self._edit.textCursor()
            cur.movePosition(QTextCursor.Start)
            self._edit.setTextCursor(cur)
            self._edit.find(needle)

    def _replace_one(self):
        needle = self._needle()
        if not needle:
            return
        cur = self._edit.textCursor()
        if cur.hasSelection() and cur.selectedText().replace("\u2029", "\n") == needle:
            cur.insertText(self.replace_edit.text() or "")
            self._edit.setTextCursor(cur)
            return
        self._find_next()

    def _replace_all(self):
        needle = self._needle()
        if not needle:
            return
        replacement = self.replace_edit.text() or ""
        doc = self._edit.document()
        cur = QTextCursor(doc)
        cur.beginEditBlock()
        # Start from top
        cur.movePosition(QTextCursor.Start)
        self._edit.setTextCursor(cur)
        while self._edit.find(needle):
            c = self._edit.textCursor()
            c.insertText(replacement)
            self._edit.setTextCursor(c)
        cur.endEditBlock()
