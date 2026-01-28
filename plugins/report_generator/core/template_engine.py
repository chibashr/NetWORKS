# Report Generator template rendering (expression lines, {{placeholder}} substitution).
# Aligns with template_manager-style variable binding.

import re

from .transforms import sanitize_value


def is_expression_line(line):
    """True if the line looks like an expression (e.g. {{a}} + \" \" + {{b}})."""
    if "+" not in line:
        return False
    expression_pattern = re.compile(
        r'^\s*(?:\{\{[^}]+\}\}|"[^"]*"|\'[^\']*\'|\+|\s+)+\s*$'
    )
    return bool(expression_pattern.match(line))


def render_expression_line(line, context):
    """Render one expression line by resolving {{key}} and quoted literals."""
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
    """Render template text: expression lines via render_expression_line, others via {{key}} sub."""
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
                lambda match: sanitize_value(context.get(match.group(1), "")), line
            )
        )
    return "\n".join(rendered_lines)
