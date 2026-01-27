#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Filter syntax, proxy model, and filter bar helpers for the device table.

Supports:
- Simple search: plain text across all columns.
- Legacy field:value syntax: e.g. ip:192.168 status:online (AND).
- Power-user text syntax: hostname contains "server" AND status = "Active" with ( ) and OR/AND.
- Tree state: {"operator":"AND"|"OR","conditions":[...]} for nested groups; legacy {"logic","rules"} is normalized.
"""

import re
from PySide6.QtCore import Qt, QSortFilterProxyModel

from .device_table_query import (
    ensure_tree,
    parse_text_query,
    tree_to_syntax,
)

# Short names for filter bar syntax (e.g. "ip:192.168" -> IP Address). Used by parse_filter_syntax.
FILTER_FIELD_ALIASES = {
    "alias": "Alias", "name": "Alias",
    "hostname": "Hostname", "host": "Hostname",
    "ip": "IP Address", "ip_address": "IP Address",
    "mac": "MAC Address", "mac_address": "MAC Address",
    "status": "Status", "tags": "Tags", "groups": "Groups",
    "any": "Any Column",
}


def parse_filter_syntax(text, all_headers=None):
    """
    Parse filter bar text into either a simple search string or a filter tree.

    Accepted input:
    - Power-user syntax: hostname contains "server" AND status = "Active", (a OR b) AND c.
      Tried first when the text looks like a query (contains " AND ", " OR ", " contains ", " = ", "(", ")").
    - Legacy field:value: ip:192.168, status:online; short names per FILTER_FIELD_ALIASES; terms AND.
    - Bare words: plain search across all columns.

    Returns:
      (simple_text, None) -> use simple search.
      (None, tree) -> tree is {"operator","conditions"} or legacy {"logic","rules"} for advanced filter.
    """
    raw = (text or "").strip()
    if not raw:
        return "", None

    all_headers_list = list(all_headers or []) + ["Any Column"]
    # Try power-user text query when it looks like one
    look_like_query = (
        " AND " in raw or " OR " in raw or " && " in raw or " || " in raw
        or " contains " in raw.lower() or " = " in raw or " != " in raw
        or raw.startswith("(") or "(" in raw or ")" in raw
    )
    if look_like_query:
        tree, err = parse_text_query(raw, all_headers_list)
        if tree is not None:
            return None, tree
        # fall back to legacy/simple

    all_headers = set(all_headers_list)
    tokens = re.split(r"\s+", raw)
    rules = []
    simple_parts = []

    for t in tokens:
        if not t:
            continue
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):(.+)$", t)
        if m:
            key, val = m.group(1).strip().lower(), m.group(2).strip()
            if not val:
                continue
            header = FILTER_FIELD_ALIASES.get(key)
            if not header:
                for h in all_headers:
                    if h.lower() == key:
                        header = h
                        break
            if not header:
                header = "Any Column"
            if header in all_headers:
                rules.append({"field": header, "operator": "contains", "value": val})
        else:
            simple_parts.append(t)

    if rules:
        for w in simple_parts:
            rules.append({"field": "Any Column", "operator": "contains", "value": w})
        return None, {"logic": "AND", "rules": rules}
    if simple_parts:
        return " ".join(simple_parts), None
    return "", None


def filter_state_to_syntax(state, header_to_short=None):
    """
    Convert advanced filter state to spec-style search bar text (Section 7).

    state may be tree {"operator","conditions"} or legacy {"logic","rules"}.
    Always emits power-user text syntax (e.g. hostname = "x", tags contains any ["a","b"]).
    """
    if not state or not isinstance(state, dict):
        return ""
    header_to_short = header_to_short or _default_header_to_short()
    tree = ensure_tree(state)
    if not tree or not tree.get("conditions"):
        return ""
    return tree_to_syntax(tree, header_to_short)


def _default_header_to_short():
    """Map display headers to preferred short names for filter bar."""
    return {
        "Alias": "alias", "Hostname": "hostname", "IP Address": "ip",
        "MAC Address": "mac", "Status": "status", "Tags": "tags", "Groups": "groups",
        "Any Column": "any",
    }


def _ip_in_subnet(ip_str, cidr_str):
    """True if ip_str is inside CIDR cidr_str (e.g. 192.168.1.0/24)."""
    try:
        import ipaddress
        addr = ipaddress.ip_address(ip_str.strip())
        net = ipaddress.ip_network(cidr_str.strip(), strict=False)
        return addr in net
    except Exception:
        return False


def _ip_in_range(ip_str, range_str):
    """True if ip_str is in range 'low - high' (inclusive)."""
    try:
        import ipaddress
        addr = ipaddress.ip_address(ip_str.strip())
        parts = [p.strip() for p in range_str.split("-") if p.strip()]
        if len(parts) < 2:
            return False
        low = ipaddress.ip_address(parts[0])
        high = ipaddress.ip_address(parts[1])
        return low <= addr <= high
    except Exception:
        return False


def _tags_from_display(display_str):
    """Split display string (e.g. 'a, b, c') into list of trimmed tags."""
    if not display_str or not str(display_str).strip():
        return []
    return [t.strip() for t in str(display_str).split(",") if t.strip()]


class IPSortFilterProxyModel(QSortFilterProxyModel):
    """Custom proxy model that handles sorting IP addresses and tree/legacy filter state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ip_column_index = -1
        self._simple_filter_text = ""
        self._advanced_tree = None  # {"operator","conditions"} or None

    def lessThan(self, left, right):
        source_model = self.sourceModel()
        column = left.column()
        if self.ip_column_index == -1:
            for i, header in enumerate(source_model.get_data_headers()):
                if header == "IP Address":
                    self.ip_column_index = i + 1
                    break
        if column == self.ip_column_index:
            left_data = source_model.data(left)
            right_data = source_model.data(right)
            if not left_data or not right_data:
                return str(left_data) < str(right_data)
            try:
                left_octets = [int(octet) for octet in re.split(r'[.\-:]', left_data) if octet.isdigit()]
                right_octets = [int(octet) for octet in re.split(r'[.\-:]', right_data) if octet.isdigit()]
                while len(left_octets) < len(right_octets):
                    left_octets.append(0)
                while len(right_octets) < len(left_octets):
                    right_octets.append(0)
                for lo, ro in zip(left_octets, right_octets):
                    if lo != ro:
                        return lo < ro
                return False
            except Exception:
                return str(left_data) < str(right_data)
        return super().lessThan(left, right)

    def reset_ip_column(self):
        self.ip_column_index = -1

    def setFilterFixedString(self, pattern):
        self._simple_filter_text = (pattern or "").strip()
        self.invalidateFilter()

    def set_advanced_filter(self, state_or_rules=None, logic="AND"):
        """
        Set advanced filter from tree, legacy state, or list of rules.

        state_or_rules: tree {"operator","conditions"}, legacy {"logic","rules"}, or list of rule dicts.
        logic: used only when state_or_rules is a list (legacy).
        """
        tree = None
        if isinstance(state_or_rules, dict) and (state_or_rules.get("conditions") is not None or state_or_rules.get("rules") is not None):
            tree = ensure_tree(state_or_rules)
        elif isinstance(state_or_rules, list):
            logic = "OR" if (logic or "AND").strip().upper() == "OR" else "AND"
            tree = {"operator": logic, "conditions": state_or_rules} if state_or_rules else None
        self._advanced_tree = tree
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if not model:
            return True
        if self._simple_filter_text:
            if not self._row_matches_simple_filter(model, source_row, source_parent):
                return False
        if not self._advanced_tree or not self._advanced_tree.get("conditions"):
            return True
        return self._evaluate_tree(model, source_row, source_parent, self._advanced_tree)

    def _evaluate_tree(self, model, source_row, source_parent, node):
        """Evaluate a tree node: group (AND/OR of conditions) or leaf rule."""
        if not isinstance(node, dict):
            return True
        if "conditions" in node and "operator" in node:
            op = (node.get("operator") or "AND").strip().upper()
            op = "OR" if op == "OR" else "AND"
            results = []
            for c in node.get("conditions", []):
                if isinstance(c, dict) and "conditions" in c:
                    results.append(self._evaluate_tree(model, source_row, source_parent, c))
                elif isinstance(c, dict) and c.get("field"):
                    results.append(self._match_rule(model, source_row, source_parent, c))
                else:
                    continue
            if not results:
                return True
            return any(results) if op == "OR" else all(results)
        if node.get("field"):
            return self._match_rule(model, source_row, source_parent, node)
        return True

    def _row_matches_simple_filter(self, model, source_row, source_parent):
        haystack = self._simple_filter_text.lower()
        if not haystack:
            return True
        for col in range(1, model.columnCount()):
            value = model.data(model.index(source_row, col, source_parent), Qt.DisplayRole)
            if haystack in str(value or "").lower():
                return True
        return False

    def _match_rule(self, model, source_row, source_parent, rule):
        if not isinstance(rule, dict):
            return None
        field = rule.get("field")
        operator = rule.get("operator")
        raw_value = rule.get("value", "")
        if not field or not operator:
            return None
        value = str(raw_value or "").strip()
        value_lower = value.lower()
        if field == "Any Column":
            return self._match_any_column(model, source_row, source_parent, operator, value_lower)
        column_index = model.get_column_index(field)
        if column_index < 0:
            return None
        cell_value = model.data(model.index(source_row, column_index, source_parent), Qt.DisplayRole)
        cell_str = str(cell_value or "").strip()
        cell_lower = cell_str.lower()
        # Tags/Groups: value can be comma-separated; operators work on list
        if field in ("Tags", "Groups"):
            return self._evaluate_tags_operator(
                _tags_from_display(cell_value), operator, value
            )
        if field == "IP Address" and operator in ("in_subnet", "in_range"):
            return self._evaluate_ip_special(cell_str, operator, value)
        return self._evaluate_operator(cell_lower, operator, value_lower, cell_str, value)

    def _match_any_column(self, model, source_row, source_parent, operator, value):
        column_values = []
        for col in range(1, model.columnCount()):
            cell_value = model.data(model.index(source_row, col, source_parent), Qt.DisplayRole)
            column_values.append(str(cell_value or "").lower())
        if operator in ("not_contains", "not_equals"):
            return all(
                self._evaluate_operator(c, operator, value, str(c), value) for c in column_values
            )
        if operator == "is_empty":
            return all(not c for c in column_values)
        if operator == "is_not_empty":
            return any(c for c in column_values)
        return any(
            self._evaluate_operator(c, operator, value, c, value) for c in column_values
        )

    def _evaluate_tags_operator(self, cell_tags, operator, value_str):
        """cell_tags is list of str; value_str is comma-separated or single."""
        want = [t.strip() for t in value_str.replace(",", " ").split() if t.strip()]
        want_set = set(want)
        cell_set = set(cell_tags)
        if operator == "contains_any_of":
            return bool(want_set & cell_set)
        if operator == "contains_all_of":
            return want_set <= cell_set
        if operator == "contains_none_of":
            return not (want_set & cell_set)
        if operator == "equals_exactly":
            return set(cell_tags) == want_set
        if operator == "is_empty":
            return len(cell_tags) == 0
        if operator == "is_not_empty":
            return len(cell_tags) > 0
        # fallback text op on joined string
        joined = " ".join(cell_tags).lower()
        val = value_str.lower()
        if operator == "contains":
            return val in joined
        if operator == "not_contains":
            return val not in joined
        if operator == "equals":
            return joined == val
        if operator == "not_equals":
            return joined != val
        return False

    def _evaluate_ip_special(self, cell_str, operator, value_str):
        if operator == "in_subnet":
            return _ip_in_subnet(cell_str, value_str)
        if operator == "in_range":
            return _ip_in_range(cell_str, value_str)
        return False

    def _evaluate_operator(self, cell_value, operator, value, cell_raw="", value_raw=""):
        """Compare cell_value (lower) and value (lower); cell_raw/value_raw for numeric/date."""
        # text
        if operator == "contains":
            return value in cell_value
        if operator == "not_contains":
            return value not in cell_value
        if operator == "equals":
            return cell_value == value
        if operator == "not_equals":
            return cell_value != value
        if operator == "starts_with":
            return cell_value.startswith(value)
        if operator == "ends_with":
            return cell_value.endswith(value)
        if operator == "matches_regex":
            try:
                return bool(re.search(value, cell_raw or cell_value))
            except re.error:
                return False
        if operator == "is_empty":
            return (cell_raw or cell_value) == ""
        if operator == "is_not_empty":
            return (cell_raw or cell_value) != ""
        # numeric
        try:
            cn = float(cell_raw or cell_value or "0")
            vn = float(value_raw or value or "0")
        except (TypeError, ValueError):
            cn, vn = 0.0, 0.0
        if operator == "greater_than":
            return cn > vn
        if operator == "less_than":
            return cn < vn
        if operator == "greater_equal":
            return cn >= vn
        if operator == "less_equal":
            return cn <= vn
        if operator == "between":
            parts = [p.strip() for p in (value_raw or value or "").split()]
            if len(parts) >= 2:
                try:
                    lo, hi = float(parts[0]), float(parts[1])
                    return lo <= cn <= hi
                except ValueError:
                    pass
            return False
        # boolean
        if operator == "is_true":
            return (cell_raw or cell_value).lower() in ("true", "1", "yes", "on")
        if operator == "is_false":
            return (cell_raw or cell_value).lower() in ("false", "0", "no", "off")
        # dropdown / is_one_of, is_not_one_of: value is comma-separated
        if operator == "is_one_of":
            opts = [o.strip().lower() for o in (value_raw or value or "").split(",")]
            return cell_value in opts
        if operator == "is_not_one_of":
            opts = [o.strip().lower() for o in (value_raw or value or "").split(",")]
            return cell_value not in opts
        return False
