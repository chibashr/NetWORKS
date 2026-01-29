# Report Generator Patch Notes

## 3-panel layout (unreleased)

- **Generator dialog**: Report Builder uses a 3-panel layout. Left: Quick Start, Report Details, Data Source (tip removed). Middle (largest): **Table Info** group (Columns / Filters / Sorting tabs and Template Settings). Right: Output, Preview. Report title removed. Middle panel has stretch factor 2 and largest initial size; splitters are adjustable.

## Refactor and compliance (1.0.1)

- **File structure**: Logic and UI split into `core/` and `ui/` modules. No file exceeds the 1,000-line limit; entry point `report_generator.py` is thin (plugin class and re-exports only).
- **Core modules**: `core/constants.py`, `core/transforms.py`, `core/template_engine.py`, `core/subnet_utils.py`, `core/report_storage.py`, `core/report_engine.py` handle constants, transforms, template rendering, subnet helpers, storage, and report execution (resolve, filter, build rows, render). The engine is Qt-free and receives device_manager/theme_tokens from the widget.
- **UI modules**: `ui/report_builder_widget.py` (form, preview, export), `ui/report_builder_ui_builder.py` (builds the form UI), `ui/report_preview_helpers.py` (JSON/CSV preview HTML), `ui/manage_reports_dialog.py` (Manage Reports list/dialog), `ui/report_builder_dialog.py` (dialog shell with Close). All UI files stay under the 1,000-line limit.
- **Tooltips**: Menu and toolbar actions now have tooltips (e.g. “Open the Report Generator to build and export device reports”).
- **Signals**: Device/group signal connections (`on_device_added`, etc.) were removed; handlers were no-ops. Re-enable in a future release if metadata refresh when the dialog is open is desired.
- **Column options**: A short hint “Applied to first selected column.” was added under the Visible/Header controls in the Selected Columns area.
