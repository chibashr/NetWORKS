#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Query engine for device table filtering: text syntax parser, tree format, and field metadata.

Supports:
- Tree format: {"operator": "AND"|"OR", "conditions": [rule | group, ...]}
- Rule: {"field": str, "operator": str, "value": str|number|list}
- Legacy flat: {"logic": "AND"|"OR", "rules": [{"field","operator","value"}, ...]} → normalized to tree.
- Text syntax: field operator "value" with AND/OR/( ) for power users.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

# Field type determines allowed operators and value handling.
FIELD_TYPES = {
    "Alias": "text",
    "Hostname": "text",
    "IP Address": "ip",
    "MAC Address": "text",
    "Status": "dropdown",
    "Tags": "tags",
    "Groups": "tags",
    "Any Column": "text",
}


def get_field_type(header: str, all_headers: Optional[List[str]] = None) -> str:
    """Return field type for header; unknown headers default to text."""
    if header in FIELD_TYPES:
        return FIELD_TYPES[header]
    # Custom/plugin headers: infer from name
    h = (header or "").lower()
    if "ip" in h or "address" in h and "mac" not in h:
        return "ip"
    if "tag" in h or "group" in h:
        return "tags"
    if "date" in h or "seen" in h or "updated" in h:
        return "date"
    return "text"


# Operators by field type (key = internal name, value = display / text-syntax tokens).
OPERATORS_TEXT = [
    ("equals", "equals", "="),
    ("not_equals", "not equals", "!="),
    ("contains", "contains", None),
    ("not_contains", "not contains", None),
    ("starts_with", "starts with", None),
    ("ends_with", "ends with", None),
    ("matches_regex", "matches regex", None),
    ("is_empty", "is empty", None),
    ("is_not_empty", "is not empty", None),
]
OPERATORS_IP = [
    ("equals", "equals", "="),
    ("contains", "contains", None),
    ("in_subnet", "in subnet", None),
    ("in_range", "in range", None),
    ("is_empty", "is empty", None),
    ("is_not_empty", "is not empty", None),
]
OPERATORS_NUMBER = [
    ("equals", "equals", "="),
    ("not_equals", "not equals", "!="),
    ("greater_than", "greater than", ">"),
    ("less_than", "less than", "<"),
    ("greater_equal", "greater than or equal", ">="),
    ("less_equal", "less than or equal", "<="),
    ("between", "between", None),
    ("is_empty", "is empty", None),
    ("is_not_empty", "is not empty", None),
]
OPERATORS_TAGS = [
    ("contains_any_of", "contains any of", None),
    ("contains_all_of", "contains all of", None),
    ("contains_none_of", "contains none of", None),
    ("equals_exactly", "equals exactly", None),
    ("is_empty", "is empty", None),
    ("is_not_empty", "is not empty", None),
]
OPERATORS_DROPDOWN = [
    ("equals", "equals", "="),
    ("not_equals", "not equals", "!="),
    ("is_one_of", "is one of", None),
    ("is_not_one_of", "is not one of", None),
    ("is_empty", "is empty", None),
    ("is_not_empty", "is not empty", None),
]
OPERATORS_BOOLEAN = [
    ("is_true", "is true", None),
    ("is_false", "is false", None),
    ("is_empty", "is empty", None),
]
OPERATORS_DATE = [
    ("equals", "equals", "="),
    ("greater_than", "after", ">"),
    ("less_than", "before", "<"),
    ("is_today", "is today", None),
    ("is_older_than_days", "is older than X days", None),
    ("is_in_last_days", "is in the last X days", None),
    ("is_empty", "is empty", None),
    ("is_not_empty", "is not empty", None),
]

OPERATORS_BY_TYPE = {
    "text": OPERATORS_TEXT,
    "ip": OPERATORS_IP,
    "number": OPERATORS_NUMBER,
    "tags": OPERATORS_TAGS,
    "dropdown": OPERATORS_DROPDOWN,
    "boolean": OPERATORS_BOOLEAN,
    "date": OPERATORS_DATE,
}


def operators_for_field(header: str, all_headers: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """Return list of (internal_key, display_label) for the field."""
    ft = get_field_type(header, all_headers)
    rows = OPERATORS_BY_TYPE.get(ft, OPERATORS_TEXT)
    return [(r[0], r[1]) for r in rows]


def normalize_legacy_state(flat: Optional[Dict]) -> Optional[Dict]:
    """Convert legacy {"logic","rules"} to tree {"operator","conditions"}."""
    if not flat or not isinstance(flat, dict):
        return None
    rules = flat.get("rules") or []
    if not rules:
        return None
    logic = (flat.get("logic") or "AND").strip().upper()
    logic = "OR" if logic == "OR" else "AND"
    return {"operator": logic, "conditions": [r for r in rules if isinstance(r, dict) and r.get("field")]}


def is_tree_state(state: Optional[Dict]) -> bool:
    """True if state is in tree form (has 'conditions' and 'operator')."""
    if not state or not isinstance(state, dict):
        return False
    return "conditions" in state and "operator" in state


def ensure_tree(state: Optional[Dict]) -> Optional[Dict]:
    """Return tree form; convert legacy flat state if needed."""
    if not state:
        return None
    if is_tree_state(state):
        return state
    return normalize_legacy_state(state)


# ---- Text query grammar (simplified) ----
# term   := group | condition
# group  := "(" expr ")"
# expr   := term ( ("AND"|"&&") term )*  |  term ( ("OR"|"||") term )*
# condition := IDENT operator value
# value  := QUOTED | NUMBER | IDENT
# operator := "=" | "!=" | ">" | "<" | ">=" | "<=" | "contains" | "starts with" | "ends with" | "matches" | "in subnet" | "in range" | "is empty" | "is not empty" | "contains any of" | ...

# Short names for text syntax (same as filter bar).
FIELD_ALIASES = {
    "alias": "Alias", "name": "Alias",
    "hostname": "Hostname", "host": "Hostname",
    "ip": "IP Address", "ip_address": "IP Address",
    "mac": "MAC Address", "mac_address": "MAC Address",
    "status": "Status", "tags": "Tags", "groups": "Groups",
    "any": "Any Column",
}


def _tokenize(text: str) -> List[Tuple[str, str]]:
    """Return list of (kind, value). kind in ('word','op','quoted','number','lp','rp')."""
    text = (text or "").strip()
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        if text[i:i + 1].isspace():
            i += 1
            continue
        if text[i] == "(":
            tokens.append(("lp", "("))
            i += 1
            continue
        if text[i] == ")":
            tokens.append(("rp", ")"))
            i += 1
            continue
        if text[i] in '"\'':
            q = text[i]
            i += 1
            start = i
            while i < n and text[i] != q:
                if text[i] == "\\":
                    i += 1
                i += 1
            tokens.append(("quoted", text[start:i]))
            if i < n:
                i += 1
            continue
        # operators that can be recognized by punctuation
        for op in ["==", "!=", ">=", "<=", "&&", "||"]:
            if text[i:i + len(op)] == op:
                tokens.append(("op", op))
                i += len(op)
                break
        else:
            if text[i] in "=><":
                tokens.append(("op", text[i]))
                i += 1
                continue
        # number (digit sequence, optional decimal)
        if text[i].isdigit():
            start = i
            while i < n and text[i].isdigit():
                i += 1
            if i < n and text[i] == ".":
                i += 1
                while i < n and text[i].isdigit():
                    i += 1
            tokens.append(("number", text[start:i]))
            continue
        # word (identifier or keyword)
        start = i
        while i < n and (text[i].isalnum() or text[i] in "_.-"):
            i += 1
        if i > start:
            tokens.append(("word", text[start:i]))
            continue
        i += 1
    return tokens


def _resolve_field(word: str, all_headers: Optional[List[str]]) -> str:
    w = (word or "").strip().lower()
    if w in FIELD_ALIASES:
        return FIELD_ALIASES[w]
    if all_headers:
        for h in all_headers:
            if h.lower() == w or h.lower().replace(" ", "_") == w:
                return h
    return word.replace("_", " ").title() if word else "Any Column"


def _parse_condition(tokens: List[Tuple[str, str]], pos: int, all_headers: Optional[List[str]]) -> Tuple[Optional[Dict], int]:
    """Parse a single condition: field operator value. Returns (rule_dict, next_pos)."""
    if pos >= len(tokens):
        return None, pos
    if tokens[pos][0] != "word":
        return None, pos
    field_word = tokens[pos][1]
    pos += 1
    field = _resolve_field(field_word, all_headers)

    # operator: word or op; allow multi-word (e.g. "starts with", "is not empty")
    op_raw = None
    if pos < len(tokens):
        kind, val = tokens[pos]
        if kind == "op":
            op_raw = val
            pos += 1
        elif kind == "word":
            words = [val.lower()]
            pos += 1
            for _ in range(2):
                if pos < len(tokens) and tokens[pos][0] == "word":
                    words.append(tokens[pos][1].lower())
                    pos += 1
            # match longest operator phrase
            for k in range(len(words), 0, -1):
                candidate = " ".join(words[:k])
                if candidate in ("is empty", "is not empty", "starts with", "ends with",
                                 "in subnet", "in range", "contains any of", "contains all of",
                                 "contains none of", "equals exactly", "is one of", "is not one of",
                                 "is true", "is false", "is today", "is older than x days",
                                 "is in the last x days", "is in last x days"):
                    op_raw = candidate
                    pos -= len(words) - k
                    break
            else:
                op_raw = words[0]

    if not op_raw:
        return None, max(0, pos - 1)

    # map text ops to internal
    op_map = {
        "=": "equals", "==": "equals", "!=": "not_equals",
        ">": "greater_than", "<": "less_than", ">=": "greater_equal", "<=": "less_equal",
        "contains": "contains", "starts with": "starts_with", "ends with": "ends_with",
        "is empty": "is_empty", "is not empty": "is_not_empty",
        "in subnet": "in_subnet", "in range": "in_range",
        "contains any of": "contains_any_of", "contains all of": "contains_all_of",
        "contains none of": "contains_none_of", "equals exactly": "equals_exactly",
        "is one of": "is_one_of", "is not one of": "is_not_one_of",
        "is true": "is_true", "is false": "is_false",
        "is today": "is_today", "is older than x days": "is_older_than_days",
        "is in the last x days": "is_in_last_days", "is in last x days": "is_in_last_days",
    }
    op = op_map.get(op_raw) or op_raw.lower().replace(" ", "_")

    value = ""
    if pos < len(tokens):
        kind, val = tokens[pos]
        if kind == "quoted":
            value = val
            pos += 1
        elif kind == "word" and op not in ("is_empty", "is_not_empty"):
            value = val
            pos += 1
        elif kind == "number":
            value = val
            pos += 1

    return {"field": field, "operator": op, "value": value}, pos


def _parse_expr(tokens: List[Tuple[str, str]], pos: int, all_headers: Optional[List[str]]) -> Tuple[Optional[Dict], int]:
    """Parse expression: condition or group, then AND/OR sequence."""
    if pos >= len(tokens):
        return None, pos

    if tokens[pos][0] == "lp":
        pos += 1
        inner, pos = _parse_expr(tokens, pos, all_headers)
        if pos < len(tokens) and tokens[pos][0] == "rp":
            pos += 1
        left = inner
    else:
        left, pos = _parse_condition(tokens, pos, all_headers)

    if left is None:
        return None, pos

    # collect AND/OR chain
    chain = [left]
    while pos < len(tokens):
        if tokens[pos][0] == "rp":
            break
        kind, val = tokens[pos][0], (tokens[pos][1] if len(tokens[pos]) > 1 else "")
        is_and = (kind == "word" and val.upper() == "AND") or val == "&&"
        is_or = (kind == "word" and val.upper() == "OR") or val == "||"
        if not (is_and or is_or):
            break
        pos += 1
        right = None
        if pos < len(tokens) and tokens[pos][0] == "lp":
            pos += 1
            right, pos = _parse_expr(tokens, pos, all_headers)
            if pos < len(tokens) and tokens[pos][0] == "rp":
                pos += 1
        else:
            right, pos = _parse_condition(tokens, pos, all_headers)
        if right is None:
            break
        chain.append(("AND" if is_and else "OR", right))
    if len(chain) == 1:
        return chain[0], pos
    # flatten into left-associative tree
    root = chain[0]
    for link, right in chain[1:]:
        root = {"operator": link, "conditions": [root, right]}
    return root, pos


def parse_text_query(text: str, all_headers: Optional[List[str]] = None) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Parse power-user text syntax into a filter tree.

    Returns (tree, None) on success, or (None, error_message) on failure.
    Empty or whitespace-only text returns (None, None) (no filter).
    """
    raw = (text or "").strip()
    if not raw:
        return None, None
    tokens = _tokenize(raw)
    if not tokens:
        return None, None
    all_headers = list(all_headers or []) + ["Any Column"]
    tree, pos = _parse_expr(tokens, 0, all_headers)
    if tree is None:
        return None, "Invalid filter expression"
    return tree, None


def tree_to_syntax(tree: Optional[Dict], header_to_short: Optional[Dict] = None) -> str:
    """
    Convert filter tree to power-user text syntax for the search bar.

    header_to_short: optional map header -> short name (e.g. "IP Address" -> "ip").
    """
    if not tree or not isinstance(tree, dict):
        return ""
    header_to_short = header_to_short or {}
    if "conditions" in tree and "operator" in tree:
        parts = []
        for c in tree.get("conditions", []):
            if isinstance(c, dict) and "conditions" in c:
                part = tree_to_syntax(c, header_to_short)
                if part:
                    parts.append("(" + part + ")")
            elif isinstance(c, dict) and c.get("field"):
                parts.append(_rule_to_syntax(c, header_to_short))
        op = (tree.get("operator") or "AND").strip()
        sep = " OR " if op.upper() == "OR" else " AND "
        return sep.join(p for p in parts if p)
    if tree.get("field"):
        return _rule_to_syntax(tree, header_to_short)
    return ""


def _rule_to_syntax(rule: Dict, header_to_short: Dict) -> str:
    """
    Emit spec-style text for one condition (Section 7).
    Examples: hostname = "server01", tags contains any ["production","critical"],
    status is empty, ip in subnet "192.168.1.0/24".
    """
    f = (rule.get("field") or "").strip()
    op = (rule.get("operator") or "contains").strip()
    v = rule.get("value")
    if v is None:
        v = ""
    v = str(v).strip()
    short = (header_to_short.get(f) or f.replace(" ", "_").lower()).strip() or f

    # Value-free operators (spec phrasing)
    if op in ("is_empty", "is_not_empty", "is_true", "is_false", "is_today"):
        phrase = op.replace("_", " ")
        return f"{short} {phrase}"

    # Multi-value operators: emit ["v1","v2"] (spec Section 7.2)
    list_ops = (
        "contains_any_of", "contains_all_of", "contains_none_of", "equals_exactly",
        "is_one_of", "is_not_one_of",
    )
    if op in list_ops:
        parts = [p.strip() for p in v.replace(",", " ").split() if p.strip()]
        vals = ", ".join(f'"{x}"' for x in parts) if parts else ""
        spec_phrase = {
            "contains_any_of": "contains any",
            "contains_all_of": "contains all",
            "contains_none_of": "contains none of",
            "equals_exactly": "equals exactly",
            "is_one_of": "is one of",
            "is_not_one_of": "is not one of",
        }.get(op, op.replace("_", " "))
        return f'{short} {spec_phrase} [{vals}]'

    # Symbolic operators for comparison (spec Section 7.2)
    if op == "equals":
        return _quoted_value(short, "=", v)
    if op == "not_equals":
        return _quoted_value(short, "!=", v)
    if op == "greater_than":
        return _quoted_value(short, ">", v)
    if op == "less_than":
        return _quoted_value(short, "<", v)
    if op == "greater_equal":
        return _quoted_value(short, ">=", v)
    if op == "less_equal":
        return _quoted_value(short, "<=", v)

    # Word-based operators: "contains", "starts with", "in subnet", etc.
    spec_phrase = {
        "contains": "contains",
        "not_contains": "not contains",
        "starts_with": "starts with",
        "ends_with": "ends with",
        "matches_regex": "matches regex",
        "in_subnet": "in subnet",
        "in_range": "in range",
        "between": "between",
    }.get(op, op.replace("_", " "))
    return _quoted_value(short, spec_phrase, v)


def _quoted_value(field: str, op_or_phrase: str, value: str) -> str:
    """Format field op value with strings quoted, numbers unquoted (spec 7.2)."""
    if not value:
        return f'{field} {op_or_phrase} ""'
    try:
        float(value)
        return f"{field} {op_or_phrase} {value}"
    except (TypeError, ValueError):
        return f'{field} {op_or_phrase} "{value}"'
