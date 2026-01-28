# Report Generator report execution: resolve, filter, build rows, render.
# Qt-free; receives device_manager and theme_tokens from the widget.

import csv
import html
import io
import json
import re

from . import constants
from .subnet_utils import ip_in_subnet, parse_subnet
from .template_engine import render_template_text
from .transforms import (
    apply_transform,
    apply_transforms_for_target,
    build_transform_map,
    sanitize_value,
)


def resolve_devices(report, device_manager):
    """Resolve the device list for the report's data_source (all/selected/group/subnet/tag)."""
    data_source = report.get("data_source", {})
    source_type = data_source.get("type", "all")
    if source_type == "selected":
        return device_manager.get_selected_devices()
    if source_type == "group":
        group = device_manager.get_group(data_source.get("group"))
        return group.get_all_devices() if group else []
    if source_type == "subnet":
        subnet = parse_subnet(data_source.get("subnet", ""))
        return [
            device
            for device in device_manager.get_devices()
            if ip_in_subnet(device.get_property("ip_address", ""), subnet)
        ]
    if source_type == "tag":
        tag = data_source.get("tag", "").strip().lower()
        if not tag:
            return []
        results = []
        for device in device_manager.get_devices():
            tags = device.get_property("tags", []) or []
            tag_values = [str(t).lower() for t in tags]
            if tag in tag_values:
                results.append(device)
        return results
    return device_manager.get_devices()


def filter_match(actual, operator, expected):
    """Return True if actual matches the filter (operator, expected)."""
    if operator in (">", ">=", "<", "<="):
        try:
            actual_val = float(actual)
            expected_val = float(expected)
        except Exception:
            return False
        if operator == ">":
            return actual_val > expected_val
        if operator == ">=":
            return actual_val >= expected_val
        if operator == "<":
            return actual_val < expected_val
        if operator == "<=":
            return actual_val <= expected_val
    actual_text = sanitize_value(actual)
    expected_text = sanitize_value(expected)
    actual_lower = actual_text.lower()
    expected_lower = expected_text.lower()
    if operator == "equals":
        return actual_lower == expected_lower
    if operator == "not_equals":
        return actual_lower != expected_lower
    if operator == "contains":
        if isinstance(actual, list):
            actual_values = [sanitize_value(item).lower() for item in actual]
            return expected_lower in actual_values
        return expected_lower in actual_lower
    if operator == "starts_with":
        return actual_lower.startswith(expected_lower)
    if operator == "ends_with":
        return actual_lower.endswith(expected_lower)
    if operator == "regex":
        try:
            return re.search(expected_text, actual_text) is not None
        except re.error:
            return False
    return False


def apply_filters(devices, filters, filter_logic="AND"):
    """Filter devices by the given filter list and AND/OR logic."""
    if not filters:
        return devices
    use_or = (filter_logic or "AND").strip().upper() == "OR"
    filtered = []
    for device in devices:
        properties = device.get_properties()
        if use_or:
            passes = any(
                filter_match(
                    properties.get(flt.get("property")),
                    flt.get("operator", "equals"),
                    flt.get("value", ""),
                )
                for flt in filters
            )
        else:
            passes = True
            for flt in filters:
                if not filter_match(
                    properties.get(flt.get("property")),
                    flt.get("operator", "equals"),
                    flt.get("value", ""),
                ):
                    passes = False
                    break
        if passes:
            filtered.append(device)
    return filtered


def build_rows(devices, report, transform_map, all_columns=None):
    """Build list of row dicts from devices using report columns/computed and transforms."""
    columns = report.get("columns", [])
    if not columns and all_columns is not None:
        columns = all_columns
    computed_columns = report.get("computed_columns", [])
    rows = []
    for device in devices:
        properties = device.get_properties()
        context = {key: sanitize_value(value) for key, value in properties.items()}
        row = {}
        for column in columns:
            value = properties.get(column, "")
            transformed = apply_transforms_for_target(value, column, transform_map, context)
            row[column] = sanitize_value(transformed)
        for computed in computed_columns:
            name = computed.get("name", "")
            parts = computed.get("parts", "")
            computed_value = apply_transform("", "concat", parts, context)
            transformed = apply_transforms_for_target(
                computed_value, name, transform_map, context
            )
            row[name] = sanitize_value(transformed)
        rows.append(row)
    sort_definitions = report.get("sorts") or []
    if not sort_definitions:
        legacy_sort = report.get("sort", {})
        if legacy_sort.get("column"):
            sort_definitions = [legacy_sort]
    for sort_def in reversed(sort_definitions):
        sort_column = (sort_def.get("column") or "").strip()
        if not sort_column:
            continue
        rows.sort(
            key=lambda r, column=sort_column: r.get(column, ""),
            reverse=sort_def.get("direction") == "desc",
        )
    return rows


def _rows_to_csv(rows, columns, display_headers=None):
    headers = display_headers if display_headers is not None else columns
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(col, "") for col in columns])
    return buffer.getvalue()


def _rows_to_txt(rows, columns, display_headers=None):
    headers = display_headers if display_headers is not None else columns
    header = "\t".join(headers)
    lines = [header]
    for row in rows:
        lines.append("\t".join(sanitize_value(row.get(col, "")) for col in columns))
    return "\n".join(lines)


def _lines_to_csv(lines):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["content"])
    for line in lines:
        writer.writerow([line])
    return buffer.getvalue()


def _wrap_report_html(body_html, title, theme_tokens):
    """Wrap body HTML in a full document with theme CSS using theme_tokens."""
    color_scheme = "dark" if theme_tokens.name == "dark" else "light"
    title_text = html.escape(title or "Report")
    font_size = theme_tokens.font_size
    meta_size = max(font_size - 1, 8)
    return f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title_text}</title>
    <style>
        :root {{
            color-scheme: {color_scheme};
            --accent: {theme_tokens.accent};
            --accent-soft: {theme_tokens.accent_soft};
            --bg: {theme_tokens.background};
            --surface: {theme_tokens.surface};
            --surface-alt: {theme_tokens.surface_alt};
            --surface-raised: {theme_tokens.surface_raised};
            --border: {theme_tokens.border};
            --text: {theme_tokens.text};
            --text-muted: {theme_tokens.text_muted};
            --header-bg: {theme_tokens.header_bg};
            --header-text: {theme_tokens.header_text};
            --table-alt: {theme_tokens.table_alt};
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 16px;
            font-family: "Segoe UI", "San Francisco", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
            font-size: {font_size}px;
            color: var(--text);
            background: var(--bg);
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            white-space: nowrap;
        }}
        th, td {{
            border: 1px solid var(--border);
            padding: 2px 4px;
            text-align: left;
        }}
        th {{
            background: var(--header-bg);
            color: var(--header-text);
            font-weight: 600;
        }}
        tbody tr:nth-child(even) {{
            background: var(--table-alt);
        }}
        tbody tr:hover {{
            background: var(--surface-raised);
        }}
        .report-pre {{
            border: 1px solid var(--border);
            background: var(--surface);
            padding: 8px;
            white-space: pre-wrap;
        }}
        .report-meta {{
            color: var(--text-muted);
            font-size: {meta_size}px;
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    {body_html}
</body>
</html>
"""


def render_table_report(
    report, rows, computed_columns, column_options, all_columns_fn, theme_tokens
):
    """Render table report to (content_string, error_or_none)."""
    output_format = report.get("output", {}).get("format", "HTML")
    columns = report.get("columns", []) or (all_columns_fn() if all_columns_fn else [])
    computed_names = [col.get("name") for col in computed_columns if col.get("name")]
    opts = column_options or {}
    visible = lambda c: opts.get(c, {}).get("visible", True)
    header = lambda c: (opts.get(c, {}).get("header") or "").strip() or c
    all_names = [c for c in columns + computed_names if visible(c)]
    display_names = [header(c) for c in all_names]

    if output_format == "JSON":
        filtered = [{k: r[k] for k in all_names if k in r} for r in rows]
        return json.dumps(filtered, indent=2), None
    if output_format == "CSV":
        return _rows_to_csv(rows, all_names, display_names), None
    if output_format == "TXT":
        return _rows_to_txt(rows, all_names, display_names), None
    # HTML
    headers = display_names
    header_cells = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(sanitize_value(row.get(col, '')))}</td>"
            for col in all_names
        )
        body_rows.append(f"<tr>{cells}</tr>")
    table_html = (
        f"<table><thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table>"
    )
    return _wrap_report_html(
        table_html, report.get("name") or "Report", theme_tokens
    ), None


def render_template_report(report, devices, rows, transform_map, theme_tokens):
    """Render template report to (content_string, error_or_none)."""
    template = report.get("template", {})
    output_format = report.get("output", {}).get("format", "HTML")
    total = len(devices)
    content_lines = []
    header_context = {"total": total, "index": 0}
    header = render_template_text(template.get("header", ""), header_context)
    if header:
        content_lines.append(header)
    for index, device in enumerate(devices, start=1):
        base_context = device.get_properties()
        context = {key: sanitize_value(value) for key, value in base_context.items()}
        context["index"] = index
        context["total"] = total
        for computed in report.get("computed_columns", []):
            name = computed.get("name", "")
            parts = computed.get("parts", "")
            if name:
                context[name] = sanitize_value(
                    apply_transform("", "concat", parts, context)
                )
        for key in list(context.keys()):
            context[key] = sanitize_value(
                apply_transforms_for_target(context[key], key, transform_map, context)
            )
        content_lines.append(render_template_text(template.get("item", ""), context))
    footer_context = {"total": total, "index": total}
    footer = render_template_text(template.get("footer", ""), footer_context)
    if footer:
        content_lines.append(footer)
    content = "\n".join([line for line in content_lines if line is not None])
    if output_format == "JSON":
        return json.dumps({"content": content, "lines": content_lines}, indent=2), None
    if output_format == "CSV":
        return _lines_to_csv(content_lines), None
    if output_format == "HTML":
        escaped = html.escape(content)
        content_html = f"<pre class='report-pre'>{escaped}</pre>"
        return _wrap_report_html(
            content_html, report.get("name") or "Report", theme_tokens
        ), None
    return content, None
