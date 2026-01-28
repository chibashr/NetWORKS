# -*- coding: utf-8 -*-
"""Helpers for rendering JSON/CSV report content as HTML in the preview pane."""

import csv
import html
import io
import json

from core.transforms import sanitize_value


def render_json_preview_html(content):
    """Render JSON string as expandable HTML for the preview pane."""
    try:
        data = json.loads(content)
    except Exception:
        return f"<pre>{html.escape(content)}</pre>"

    def render_node(node):
        if isinstance(node, dict):
            items = []
            for key, value in node.items():
                items.append(
                    f"<details><summary>{html.escape(str(key))}</summary>{render_node(value)}</details>"
                )
            return "".join(items) or "<em>{}</em>"
        if isinstance(node, list):
            items = []
            for index, value in enumerate(node):
                items.append(
                    f"<details><summary>[{index}]</summary>{render_node(value)}</details>"
                )
            return "".join(items) or "<em>[]</em>"
        return f"<pre>{html.escape(sanitize_value(node))}</pre>"

    return render_node(data)


def render_csv_preview_html(content):
    """Render CSV string as table HTML for the preview pane."""
    buffer = io.StringIO(content)
    try:
        reader = csv.reader(buffer)
        rows = list(reader)
    except Exception:
        return f"<pre>{html.escape(content)}</pre>"
    if not rows:
        return "<em>No data</em>"
    header = rows[0]
    body = rows[1:]
    header_cells = "".join(f"<th>{html.escape(cell)}</th>" for cell in header)
    body_rows = []
    for row in body:
        cells = "".join(f"<td>{html.escape(cell)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        "<table border='1' cellspacing='0' cellpadding='4' style='white-space: nowrap;'>"
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table>"
    )
