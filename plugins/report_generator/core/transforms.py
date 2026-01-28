# Report Generator value transforms (sanitize, date_format, concat, etc.).
# Used by template_engine and report_engine.

import datetime


def sanitize_value(value):
    """Convert value to a display string; join lists with commas."""
    if isinstance(value, list):
        return ", ".join([str(v) for v in value])
    if value is None:
        return ""
    return str(value)


def apply_date_format(value, fmt):
    """Format a date/datetime or ISO string with the given format."""
    if not value:
        return ""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime(fmt)
    try:
        parsed = datetime.datetime.fromisoformat(str(value))
        return parsed.strftime(fmt)
    except Exception:
        return sanitize_value(value)


def parse_concat_parts(value):
    """Parse comma-separated concat spec: property names or quoted literals."""
    parts = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if (part.startswith('"') and part.endswith('"')) or (part.startswith("'") and part.endswith("'")):
            parts.append(("literal", part[1:-1]))
        else:
            parts.append(("property", part))
    return parts


def apply_transform(value, transform, transform_value, context=None):
    """Apply a single transform (upper, lower, prefix, concat, etc.) to a value."""
    base_value = sanitize_value(value)
    if transform == "upper":
        return base_value.upper()
    if transform == "lower":
        return base_value.lower()
    if transform == "title":
        return base_value.title()
    if transform == "prefix":
        return f"{sanitize_value(transform_value)}{base_value}"
    if transform == "suffix":
        return f"{base_value}{sanitize_value(transform_value)}"
    if transform == "date_format":
        return apply_date_format(value, sanitize_value(transform_value) or "%Y-%m-%d")
    if transform == "concat":
        if context is None:
            return base_value
        parts = parse_concat_parts(sanitize_value(transform_value))
        resolved = []
        for part_type, part_value in parts:
            if part_type == "literal":
                resolved.append(part_value)
            else:
                resolved.append(sanitize_value(context.get(part_value, "")))
        return "".join(resolved)
    return base_value


def build_transform_map(transformations):
    """Build a map of target -> list of transform dicts from report transformations."""
    transform_map = {}
    for transform in transformations:
        target = (transform.get("target") or "").strip()
        if not target:
            continue
        transform_map.setdefault(target, []).append(transform)
    return transform_map


def apply_transforms_for_target(value, target, transform_map, context):
    """Apply all transforms for the given target to the value."""
    if target not in transform_map:
        return value
    transformed_value = value
    for transform in transform_map[target]:
        transformed_value = apply_transform(
            transformed_value,
            transform.get("transform"),
            transform.get("value"),
            context,
        )
    return transformed_value
