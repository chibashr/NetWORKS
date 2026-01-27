#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Advanced filter and other table-related dialogs.

Supports tree state (nested groups with AND/OR) and field-type operators
via device_table_query.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QGroupBox,
)

from .device_table_query import ensure_tree, is_tree_state, operators_for_field


class AdvancedFilterDialog(QDialog):
    """
    Dialog for building advanced filters: rules and nested groups.
    get_filter_state / set_filter_state support tree {"operator","conditions"} and legacy {"logic","rules"}.
    """

    apply_requested = Signal(dict)

    def __init__(self, fields, presets, current_state, on_save_preset, on_delete_preset, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Filtering")
        self.setMinimumWidth(580)
        self._fields = list(fields) if fields else []
        self._presets = presets or {}
        self._on_save_preset = on_save_preset
        self._on_delete_preset = on_delete_preset
        self._rule_rows = []
        self._groups = []  # list of {"widget", "logic_combo", "rules_layout", "rule_rows"}
        layout = QVBoxLayout(self)
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Presets:"))
        self.presets_combo = QComboBox()
        preset_layout.addWidget(self.presets_combo, 1)
        for btn_label, slot in [("Load", "_load_selected_preset"), ("Save", "_save_preset"), ("Delete", "_delete_preset")]:
            b = QPushButton(btn_label)
            preset_layout.addWidget(b)
            b.clicked.connect(getattr(self, slot))
        layout.addLayout(preset_layout)
        logic_layout = QHBoxLayout()
        logic_layout.addWidget(QLabel("Match:"))
        self.logic_combo = QComboBox()
        self.logic_combo.addItem("All of the following (AND)", "AND")
        self.logic_combo.addItem("Any of the following (OR)", "OR")
        logic_layout.addWidget(self.logic_combo)
        logic_layout.addStretch(1)
        layout.addLayout(logic_layout)
        rules_container = QWidget()
        self.rules_layout = QVBoxLayout(rules_container)
        self.rules_layout.setContentsMargins(0, 0, 0, 0)
        self.rules_layout.setSpacing(6)
        rules_scroll = QScrollArea()
        rules_scroll.setWidgetResizable(True)
        rules_scroll.setWidget(rules_container)
        layout.addWidget(rules_scroll, 1)
        add_layout = QHBoxLayout()
        add_layout.addWidget(QPushButton("+ Add Filter"), 0)
        add_layout.addWidget(QPushButton("+ Add Group"), 0)
        add_layout.addStretch(1)
        layout.addLayout(add_layout)
        add_layout.itemAt(0).widget().clicked.connect(self._add_rule_row)
        add_layout.itemAt(1).widget().clicked.connect(self._add_group)
        button_box = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Close)
        layout.addWidget(button_box)
        apply_btn = button_box.button(QDialogButtonBox.Apply)
        if apply_btn:
            apply_btn.clicked.connect(lambda: self.apply_requested.emit(self.get_filter_state()))
        button_box.rejected.connect(self.reject)
        self._refresh_presets()
        self.set_filter_state(current_state or {"logic": "AND", "rules": []})

    def _refresh_presets(self):
        self.presets_combo.clear()
        for name in sorted(self._presets.keys()):
            self.presets_combo.addItem(name)

    def _operators_for_field(self, field):
        ops = operators_for_field(field, self._fields)
        return ops if ops else [("contains", "contains")]

    def _add_rule_row(self, rule=None, layout_and_rows=None):
        rule = rule or {}
        target_layout = self.rules_layout if layout_and_rows is None else layout_and_rows["layout"]
        target_list = self._rule_rows if layout_and_rows is None else layout_and_rows["rows"]
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        field_combo = QComboBox()
        field_combo.addItems(self._fields)
        if rule.get("field") in self._fields:
            field_combo.setCurrentText(rule.get("field"))
        operator_combo = QComboBox()
        def fill_operators():
            for i in range(operator_combo.count(), 0, -1):
                operator_combo.removeItem(i - 1)
            for op_key, label in self._operators_for_field(field_combo.currentText()):
                operator_combo.addItem(label, op_key)
            if rule.get("operator"):
                idx = operator_combo.findData(rule.get("operator"))
                if idx >= 0:
                    operator_combo.setCurrentIndex(idx)
        fill_operators()
        field_combo.currentTextChanged.connect(lambda: self._sync_operators_for_row(operator_combo, field_combo))
        value_edit = QLineEdit()
        value_edit.setPlaceholderText("Value (e.g. comma-separated for tags)")
        value_edit.setText(rule.get("value", ""))
        remove_btn = QToolButton()
        remove_btn.setText("×")
        remove_btn.setToolTip("Remove this filter")

        def update_value_state():
            op_key = operator_combo.currentData()
            needs = op_key not in (
                "is_empty", "is_not_empty", "is_true", "is_false", "is_today"
            )
            value_edit.setEnabled(bool(needs))
            if not needs:
                value_edit.clear()

        operator_combo.currentIndexChanged.connect(update_value_state)
        update_value_state()

        def remove_row():
            for i, r in enumerate(target_list):
                if r.get("widget") is row_widget:
                    target_list.pop(i)
                    break
            row_widget.setParent(None)
            row_widget.deleteLater()

        remove_btn.clicked.connect(remove_row)
        row_layout.addWidget(field_combo)
        row_layout.addWidget(operator_combo)
        row_layout.addWidget(value_edit, 1)
        row_layout.addWidget(remove_btn)
        target_layout.addWidget(row_widget)
        target_list.append({
            "widget": row_widget, "field": field_combo,
            "operator": operator_combo, "value": value_edit,
        })

    def _sync_operators_for_row(self, operator_combo, field_combo):
        cur = operator_combo.currentData()
        operator_combo.clear()
        for op_key, label in self._operators_for_field(field_combo.currentText()):
            operator_combo.addItem(label, op_key)
        idx = operator_combo.findData(cur)
        if idx >= 0:
            operator_combo.setCurrentIndex(idx)

    def _add_group(self, group_state=None):
        group_state = group_state or {}
        logic = group_state.get("operator") or group_state.get("logic") or "AND"
        conditions = group_state.get("conditions") or group_state.get("rules") or []
        gb = QGroupBox("Filter group")
        gb.setStyleSheet("QGroupBox { font-weight: bold; }")
        gb_layout = QVBoxLayout(gb)
        gb_layout.setContentsMargins(8, 12, 8, 8)
        logic_row = QHBoxLayout()
        logic_row.addWidget(QLabel("Match:"))
        logic_combo = QComboBox()
        logic_combo.addItem("All (AND)", "AND")
        logic_combo.addItem("Any (OR)", "OR")
        logic_combo.setCurrentIndex(0 if logic == "AND" else 1)
        logic_row.addWidget(logic_combo)
        logic_row.addStretch(1)
        gb_layout.addLayout(logic_row)
        grp_rules_layout = QVBoxLayout()
        grp_rules_layout.setSpacing(4)
        grp_rules_layout.setContentsMargins(0, 0, 0, 0)
        grp_rows = []
        grp_data = {"layout": grp_rules_layout, "rows": grp_rows}
        for c in conditions:
            if isinstance(c, dict) and c.get("conditions") is not None:
                self._add_group(c)
                continue
            if isinstance(c, dict) and c.get("field"):
                self._add_rule_row(c, grp_data)
        add_in_grp = QPushButton("+ Add filter in group")
        add_in_grp.clicked.connect(lambda: self._add_rule_row(None, grp_data))
        gb_layout.addLayout(grp_rules_layout)
        gb_layout.addWidget(add_in_grp)
        remove_grp_btn = QToolButton()
        remove_grp_btn.setText("Remove group")
        remove_grp_btn.clicked.connect(lambda: self._remove_group(grp_info))
        logic_row.addWidget(remove_grp_btn)
        grp_info = {
            "widget": gb, "logic_combo": logic_combo,
            "rules_layout": grp_rules_layout, "rule_rows": grp_rows,
        }
        self._groups.append(grp_info)
        self.rules_layout.addWidget(gb)

    def _remove_group(self, grp_info):
        if grp_info in self._groups:
            self._groups.remove(grp_info)
        w = grp_info.get("widget")
        if w:
            w.setParent(None)
            w.deleteLater()

    def _load_selected_preset(self):
        name = self.presets_combo.currentText()
        if not name or name not in self._presets:
            return
        self.set_filter_state(self._presets.get(name, {}))

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        name = (name or "").strip()
        if not ok or not name:
            return
        state = self.get_filter_state()
        self._presets[name] = state
        if self._on_save_preset:
            self._on_save_preset(name, state)
        self._refresh_presets()
        idx = self.presets_combo.findText(name)
        if idx >= 0:
            self.presets_combo.setCurrentIndex(idx)

    def _delete_preset(self):
        name = self.presets_combo.currentText()
        if not name or name not in self._presets:
            return
        if QMessageBox.question(
            self, "Delete Preset", f"Delete preset '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        del self._presets[name]
        if self._on_delete_preset:
            self._on_delete_preset(name)
        self._refresh_presets()

    def set_filter_state(self, state):
        state = state or {}
        for g in list(self._groups):
            g["widget"].setParent(None)
            g["widget"].deleteLater()
        self._groups.clear()
        for row in list(self._rule_rows):
            row["widget"].setParent(None)
            row["widget"].deleteLater()
        self._rule_rows = []

        tree = ensure_tree(state)
        if tree and tree.get("conditions") is not None:
            logic = (tree.get("operator") or "AND").strip().upper()
            self.logic_combo.setCurrentIndex(0 if logic == "AND" else 1)
            for c in tree.get("conditions", []):
                if isinstance(c, dict) and c.get("conditions") is not None:
                    self._add_group(c)
                elif isinstance(c, dict) and c.get("field"):
                    self._add_rule_row(c)
            if not tree.get("conditions") and not self._groups:
                self._add_rule_row()
            return
        logic = (state.get("logic") or "AND").strip().upper()
        self.logic_combo.setCurrentIndex(0 if logic == "AND" else 1)
        rules = state.get("rules") or []
        if not rules:
            self._add_rule_row()
            return
        for r in rules:
            self._add_rule_row(r)

    def get_filter_state(self):
        conditions = []
        for row in self._rule_rows:
            r = self._rule_to_dict(row)
            if r:
                conditions.append(r)
        for grp in self._groups:
            grp_conditions = []
            for row in grp["rule_rows"]:
                r = self._rule_to_dict(row)
                if r:
                    grp_conditions.append(r)
            if grp_conditions:
                conditions.append({
                    "operator": grp["logic_combo"].currentData() or "AND",
                    "conditions": grp_conditions,
                })
        if not conditions:
            return {"logic": self.logic_combo.currentData() or "AND", "rules": []}
        root_op = self.logic_combo.currentData() or "AND"
        if all(isinstance(c, dict) and "field" in c for c in conditions):
            return {"logic": root_op, "rules": conditions}
        return {"operator": root_op, "conditions": conditions}

    def _rule_to_dict(self, row):
        field = row["field"].currentText()
        operator = row["operator"].currentData()
        value = row["value"].text().strip()
        if not operator:
            return None
        if operator not in ("is_empty", "is_not_empty", "is_true", "is_false", "is_today") and not value:
            return None
        return {"field": field, "operator": operator, "value": value}
