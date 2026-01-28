# Report Generator constants and default report definition.
# No Qt or device_manager dependencies.

import uuid

DATA_SOURCE_LABELS = [
    "All Devices",
    "Selected Devices",
    "Group",
    "Subnet",
    "Tag",
]

DATA_SOURCE_MAP = {
    "All Devices": "all",
    "Selected Devices": "selected",
    "Group": "group",
    "Subnet": "subnet",
    "Tag": "tag",
}

DATA_SOURCE_REVERSE = {value: key for key, value in DATA_SOURCE_MAP.items()}

MODE_LABELS = ["Table", "Template"]
MODE_MAP = {"Table": "table", "Template": "template"}
MODE_REVERSE = {value: key for key, value in MODE_MAP.items()}

FILTER_OPERATORS = [
    "equals",
    "not_equals",
    "contains",
    "starts_with",
    "ends_with",
    "regex",
    ">",
    ">=",
    "<",
    "<=",
]

TRANSFORM_TYPES = [
    "upper",
    "lower",
    "title",
    "prefix",
    "suffix",
    "date_format",
    "concat",
]

EXPORT_FORMATS = ["HTML", "JSON", "CSV", "TXT"]

# Standard device properties (from Device model). All others are custom.
STANDARD_DEVICE_PROPERTIES = (
    "id", "alias", "hostname", "ip_address", "mac_address", "status", "notes", "tags"
)


def default_report_definition():
    """Return a new report definition with generated id and defaults."""
    return {
        "id": str(uuid.uuid4()),
        "name": "New Report",
        "mode": "table",
        "data_source": {
            "type": "all",
            "group": "",
            "subnet": "",
            "tag": "",
        },
        "filters": [],
        "filter_logic": "AND",
        "columns": [],
        "column_options": {},
        "computed_columns": [],
        "transformations": [],
        "sort": {"column": "", "direction": "asc"},
        "sorts": [],
        "template": {"header": "", "item": "{{alias}}", "footer": ""},
        "output": {"format": "HTML"},
    }
