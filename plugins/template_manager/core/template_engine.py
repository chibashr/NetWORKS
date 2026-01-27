#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Template engine for Template Manager plugin.
Variable binding matches Report Generator: {{property_name}} syntax.
Logic reused from plugins/report_generator/report_generator.py for consistency.
"""

import re


# Standard device properties (same as Report Generator). All others are custom.
STANDARD_DEVICE_PROPERTIES = (
    "id", "alias", "hostname", "ip_address", "mac_address", "status", "notes", "tags"
)


def sanitize_value(value):
    """Convert value to string for template substitution. Matches Report Generator."""
    if isinstance(value, list):
        return ", ".join([str(v) for v in value])
    if value is None:
        return ""
    return str(value)


def is_expression_line(line):
    """True if line looks like {{x}} + {{y}} expression. Matches Report Generator."""
    if "+" not in line:
        return False
    expression_pattern = re.compile(
        r'^\s*(?:\{\{[^}]+\}\}|"[^"]*"|\'[^\']*\'|\+|\s+)+\s*$'
    )
    return bool(expression_pattern.match(line))


def render_expression_line(line, context):
    """Render one expression line with context. Matches Report Generator."""
    token_pattern = re.compile(r'\{\{[^}]+\}\}|"[^"]*"|\'[^\']*\'|\+')
    parts = []
    for token in token_pattern.findall(line):
        token = token.strip()
        if not token or token == "+":
            continue
        if token.startswith("{{"):
            key = token[2:-2].strip()
            parts.append(sanitize_value(context.get(key, "")))
        elif token.startswith('"') or token.startswith("'"):
            parts.append(token[1:-1])
        else:
            parts.append(token)
    return "".join(parts)


def render_template_text(template_text, context):
    """
    Replace {{property}} placeholders in template_text with context values.
    Supports expression lines (e.g. {{alias}} + " " + {{ip_address}}).
    Matches Report Generator behavior.
    """
    if not template_text:
        return ""
    rendered_lines = []
    placeholder_pattern = re.compile(r"\{\{\s*([^}]+)\s*\}\}")
    for line in template_text.splitlines():
        if is_expression_line(line):
            rendered_lines.append(render_expression_line(line, context))
            continue
        rendered_lines.append(
            placeholder_pattern.sub(
                lambda m: sanitize_value(context.get(m.group(1), "")), line
            )
        )
    return "\n".join(rendered_lines)


def render_template_text_to_html(template_text, context):
    """
    Like render_template_text but returns HTML with substituted values wrapped in <b>.
    Used for preview to show which parts came from variables.
    """
    import html
    if not template_text:
        return ""
    placeholder_pattern = re.compile(r"\{\{\s*([^}]+)\s*\}\}")
    lines_out = []
    for line in template_text.splitlines():
        if is_expression_line(line):
            plain = render_expression_line(line, context)
            lines_out.append(html.escape(plain))
            continue
        last = 0
        parts = []
        for m in placeholder_pattern.finditer(line):
            parts.append(html.escape(line[last : m.start()]))
            val = sanitize_value(context.get(m.group(1), ""))
            parts.append(f"<b>{html.escape(val)}</b>")
            last = m.end()
        parts.append(html.escape(line[last:]))
        lines_out.append("".join(parts))
    return "<br>".join(lines_out)
