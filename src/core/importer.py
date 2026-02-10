#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device importer module for NetWORKS

This module provides functionality for importing devices from various file formats 
and data sources. It is separate from the device tree to allow for better modularity.
"""

import os
import io
import csv
import json
from loguru import logger
from pathlib import Path

# Import Device class for creating device objects
from .device_manager import Device
from .importer_utils import (
    HAS_CHARDET,
    HAS_DOCX,
    HAS_OPENPYXL,
    HAS_XLRD,
    _try_import_pandas,
    get_chardet,
    get_docx_document,
    get_openpyxl,
    get_pandas,
    get_xlrd,
)


class DeviceImporter:
    """Handles importing devices from various sources"""
    
    def __init__(self, device_manager):
        """Initialize the device importer
        
        Args:
            device_manager: The device manager instance to add imported devices to
        """
        self.device_manager = device_manager
        # These are updated during auto-detection and can be surfaced in the UI.
        self.last_detected_encoding = None
        self.last_detected_delimiter = None
    
    def import_from_file(self, file_path, options=None):
        """Import devices from a file
        
        Args:
            file_path: Path to the file to import
            options: Dictionary of import options:
                - delimiter: CSV delimiter character
                - has_header: Whether the file has a header row
                - encoding: File encoding (or 'auto' to detect)
                - target_group: Group to add devices to
                - field_mapping: Dictionary mapping columns to device properties
                - skip_duplicates: Whether to skip duplicate devices
                - mark_imported: Whether to tag devices as 'imported'
                
        Returns:
            tuple: (success, stats) where success is a boolean and stats is a dict with:
                - imported_count: Number of devices imported
                - skipped_count: Number of devices skipped
                - error_count: Number of devices with errors
        """
        if options is None:
            options = {}
            
        # Set default options
        options.setdefault('delimiter', ',')
        options.setdefault('has_header', True)
        options.setdefault('encoding', 'auto')
        options.setdefault('skip_duplicates', False)
        options.setdefault('mark_imported', True)
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Get raw data based on file type
        data, headers = self._extract_data_from_file(file_path, file_ext, options)
        
        if not data:
            logger.warning(f"No data extracted from file: {file_path}")
            return False, {"imported_count": 0, "skipped_count": 0, "error_count": 0}
            
        # Import the data using the common import function
        return self._import_data(data, headers, options)
    
    def import_from_text(self, text, options=None):
        """Import devices from pasted text
        
        Args:
            text: Text containing device data (CSV, line-by-line IP list, etc.)
            options: Dictionary of import options (see import_from_file)
                
        Returns:
            tuple: (success, stats) where success is a boolean and stats is a dict with:
                - imported_count: Number of devices imported
                - skipped_count: Number of devices skipped
                - error_count: Number of devices with errors
        """
        if options is None:
            options = {}
            
        # Set default options
        options.setdefault('delimiter', ',')
        options.setdefault('has_header', True)
        options.setdefault('skip_duplicates', False)
        options.setdefault('mark_imported', True)
        
        # Extract data from text
        data, headers = self._extract_data_from_text(text, options)
        
        if not data:
            logger.warning("No data could be extracted from text")
            return False, {"imported_count": 0, "skipped_count": 0, "error_count": 0}
        
        # Import the data using the common import function
        return self._import_data(data, headers, options)
    
    def _extract_data_from_file(self, file_path, file_ext, options):
        """Extract data from a file based on its extension
        
        Args:
            file_path: Path to the file
            file_ext: File extension (lowercase)
            options: Import options
            
        Returns:
            tuple: (data, headers) where data is a list of rows and headers is a list of column names
        """
        data = []
        headers = []
        
        try:
            # Handle different file types
            if file_ext in ['.xlsx', '.xls'] and (
                _try_import_pandas() or HAS_OPENPYXL or (file_ext == '.xls' and HAS_XLRD)
            ):
                data, headers = self._extract_from_excel(file_path, file_ext, options)
            elif file_ext == '.docx' and HAS_DOCX:
                data, headers = self._extract_from_docx(file_path, options)
            else:  # CSV and text files
                data, headers = self._extract_from_csv(file_path, options)
                
            return data, headers
        except Exception as e:
            logger.error(f"Error extracting data from file: {e}", exc_info=True)
            return [], None
    
    def _extract_from_excel(self, file_path, file_ext, options):
        """Extract data from Excel files
        
        Args:
            file_path: Path to the Excel file
            file_ext: File extension (.xlsx or .xls)
            options: Import options
            
        Returns:
            tuple: (data, headers) where data is a list of rows and headers is a list of column names
        """
        has_header = options.get('has_header', True)
        sheet_name = options.get('sheet_name')
        sheet_names = options.get('sheet_names')
        
        has_pandas = _try_import_pandas()
        if file_ext == '.xlsx' or (file_ext == '.xls' and has_pandas):
            # Use pandas for Excel files
            if not has_pandas:
                logger.warning("pandas is not installed, falling back to other methods")
                if file_ext == '.xls' and HAS_XLRD:
                    return self._extract_from_excel_xlrd(file_path, options)
                if file_ext == '.xlsx' and HAS_OPENPYXL:
                    return self._extract_from_excel_openpyxl(file_path, options)
                return [], None
                
            try:
                pd = get_pandas()
                engine = 'xlrd' if file_ext == '.xls' else None
                # Support importing multiple worksheets when requested.
                if sheet_names:
                    df_dict = pd.read_excel(file_path, sheet_name=sheet_names, engine=engine)
                    frames = []
                    headers = None
                    for name in sheet_names:
                        frame = df_dict.get(name)
                        if frame is None:
                            continue
                        if headers is None:
                            headers = frame.columns.tolist() if has_header else [
                                f"Column {i+1}" for i in range(len(frame.columns))
                            ]
                        # Align columns with the first sheet's headers
                        frame = frame.reindex(columns=headers, fill_value=None)
                        frames.append(frame)
                    if not frames or headers is None:
                        return [], None
                    df = pd.concat(frames, ignore_index=True)
                else:
                    # Use specific sheet when provided, otherwise default to first sheet
                    df = pd.read_excel(file_path, sheet_name=sheet_name or 0, engine=engine)
                    logger.debug(f"Excel file loaded with {len(df)} rows")
                    headers = df.columns.tolist() if has_header else [
                        f"Column {i+1}" for i in range(len(df.columns))
                    ]

                data = df.values.tolist()

                return data, headers
            except Exception as e:
                logger.error(f"Error reading Excel file with pandas: {e}", exc_info=True)
                if file_ext == '.xls' and HAS_XLRD:
                    logger.info("Trying xlrd fallback for .xls file")
                    return self._extract_from_excel_xlrd(file_path, options)
                if file_ext == '.xlsx' and HAS_OPENPYXL:
                    logger.info("Trying openpyxl fallback for .xlsx file")
                    return self._extract_from_excel_openpyxl(file_path, options)
                return [], None
        elif file_ext == '.xlsx' and HAS_OPENPYXL:
            return self._extract_from_excel_openpyxl(file_path, options)
        elif file_ext == '.xls' and HAS_XLRD:
            return self._extract_from_excel_xlrd(file_path, options)
            
        return [], None
    
    def _extract_from_excel_xlrd(self, file_path, options):
        """Extract data from Excel files using xlrd (for .xls files)
        
        Args:
            file_path: Path to the Excel file
            options: Import options
            
        Returns:
            tuple: (data, headers) where data is a list of rows and headers is a list of column names
        """
        has_header = options.get('has_header', True)
        skip_rows = max(int(options.get('skip_rows', 0)), 0)
        
        try:
            xlrd_mod = get_xlrd()
            if not xlrd_mod:
                return [], None
            workbook = xlrd_mod.open_workbook(file_path)
            sheet_name = options.get('sheet_name')
            sheet_names = options.get('sheet_names')

            def _load_sheet(s):
                logger.debug(f"XLS sheet '{s.name}' loaded with {s.nrows} rows")
                all_rows = [s.row_values(i) for i in range(s.nrows)]
                if has_header and len(all_rows) > 0:
                    hdrs = all_rows[0]
                    rows = all_rows[1:]
                else:
                    hdrs = [f"Column {i+1}" for i in range(s.ncols)]
                    rows = all_rows
                return hdrs, rows

            combined_data = []
            headers = None

            if sheet_names:
                for name in sheet_names:
                    try:
                        sheet = workbook.sheet_by_name(name)
                    except Exception:
                        continue
                    hdrs, rows = _load_sheet(sheet)
                    if headers is None:
                        headers = hdrs
                    # Align column counts
                    if len(hdrs) != len(headers):
                        # Extend or truncate rows to match header length
                        adjusted_rows = []
                        for r in rows:
                            if len(r) < len(headers):
                                r = r + [None] * (len(headers) - len(r))
                            adjusted_rows.append(r[: len(headers)])
                        rows = adjusted_rows
                    combined_data.extend(rows)
            else:
                if sheet_name:
                    try:
                        sheet = workbook.sheet_by_name(sheet_name)
                    except Exception:
                        sheet = workbook.sheet_by_index(0)
                else:
                    sheet = workbook.sheet_by_index(0)
                headers, combined_data = _load_sheet(sheet)

            if headers is None:
                return [], None

            if skip_rows:
                combined_data = combined_data[skip_rows:]

            return combined_data, headers
        except Exception as e:
            logger.error(f"Error reading Excel file with xlrd: {e}", exc_info=True)
            return [], None

    def _extract_from_excel_openpyxl(self, file_path, options):
        """Extract data from XLSX files using openpyxl
        
        Args:
            file_path: Path to the Excel file
            options: Import options
            
        Returns:
            tuple: (data, headers) where data is a list of rows and headers is a list of column names
        """
        has_header = options.get('has_header', True)
        skip_rows = max(int(options.get('skip_rows', 0)), 0)
        
        try:
            openpyxl_mod = get_openpyxl()
            if not openpyxl_mod:
                return [], None
            workbook = openpyxl_mod.load_workbook(file_path, read_only=True, data_only=True)
            sheet_name = options.get('sheet_name')
            sheet_names = options.get('sheet_names')

            def _rows_from_sheet(s):
                rows_local = list(s.iter_rows(values_only=True))
                if not rows_local:
                    return None, []
                rows_local = [list(row) for row in rows_local]
                if has_header and len(rows_local) > 0:
                    hdrs = [str(value) if value is not None else "" for value in rows_local[0]]
                    data_local = rows_local[1:]
                else:
                    hdrs = [f"Column {i+1}" for i in range(len(rows_local[0]))]
                    data_local = rows_local
                return hdrs, data_local

            headers = None
            combined_data = []

            if sheet_names:
                for name in sheet_names:
                    if name not in workbook.sheetnames:
                        continue
                    sheet = workbook[name]
                    hdrs, data_local = _rows_from_sheet(sheet)
                    if hdrs is None:
                        continue
                    if headers is None:
                        headers = hdrs
                    # Align column counts
                    if len(hdrs) != len(headers):
                        adjusted_rows = []
                        for r in data_local:
                            if len(r) < len(headers):
                                r = r + [None] * (len(headers) - len(r))
                            adjusted_rows.append(r[: len(headers)])
                        data_local = adjusted_rows
                    combined_data.extend(data_local)
            else:
                if sheet_name and sheet_name in workbook.sheetnames:
                    sheet = workbook[sheet_name]
                else:
                    sheet = workbook.active
                headers, combined_data = _rows_from_sheet(sheet)

            if headers is None:
                logger.warning("No rows found in XLSX file")
                return [], None

            if skip_rows:
                combined_data = combined_data[skip_rows:]

            return combined_data, headers
        except Exception as e:
            logger.error(f"Error reading Excel file with openpyxl: {e}", exc_info=True)
            return [], None
    
    def _extract_from_docx(self, file_path, options):
        """Extract data from Word documents
        
        Args:
            file_path: Path to the Word document
            options: Import options
            
        Returns:
            tuple: (data, headers) where data is a list of rows and headers is a list of column names
        """
        DocClass = get_docx_document()
        if not DocClass:
            return [], None
        try:
            doc = DocClass(file_path)
            
            # Try to find tables
            if doc.tables:
                # Get first table
                table = doc.tables[0]
                
                # Extract rows from table
                has_header = options.get('has_header', True)
                all_rows = []
                
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    all_rows.append(row_data)
                
                if not all_rows:
                    logger.warning("No data found in Word table")
                    return [], None
                    
                if has_header and len(all_rows) > 0:
                    headers = all_rows[0]
                    data = all_rows[1:]
                else:
                    headers = [f"Column {i+1}" for i in range(len(all_rows[0]))]
                    data = all_rows
                    
                return data, headers
            else:
                # No tables, try to extract from paragraphs
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                return self._extract_data_from_text(text, options)
                
        except Exception as e:
            logger.error(f"Error extracting data from Word document: {e}", exc_info=True)
            return [], None
            
    def _extract_from_csv(self, file_path, options):
        """Extract data from CSV files
        
        Args:
            file_path: Path to the CSV file
            options: Import options
            
        Returns:
            tuple: (data, headers) where data is a list of rows and headers is a list of column names
        """
        # Get selected encoding or detect
        encoding_option = options.get('encoding', 'auto')
        encoding = None
        
        if encoding_option == 'auto':
            chardet_mod = get_chardet()
            if chardet_mod:
                try:
                    with open(file_path, 'rb') as f:
                        raw_data = f.read(10000)  # Read first 10000 bytes
                        result = chardet_mod.detect(raw_data)
                        encoding = result['encoding']
                        logger.debug(f"Detected encoding: {encoding} (confidence: {result.get('confidence', 0):.2f})")
                        if not encoding:
                            encoding = 'utf-8'  # Fallback to UTF-8
                        self.last_detected_encoding = encoding
                except Exception as e:
                    logger.error(f"Error detecting file encoding: {e}")
                    encoding = 'utf-8'  # Fallback to UTF-8
            else:
                encoding = 'utf-8'  # Fallback to UTF-8 if chardet not available
            if not encoding:
                encoding = 'utf-8'
        else:
            encoding = encoding_option
            self.last_detected_encoding = encoding
            
        delimiter = options.get('delimiter', ',')
        has_header = options.get('has_header', True)
        skip_rows = max(int(options.get('skip_rows', 0)), 0)
        
        # Handle different delimiter options
        delimiter_map = {
            "Comma (,)": ',',
            "Tab": '\t',
            "Semicolon (;)": ';',
            "Pipe (|)": '|',
            "Space": ' ',
            "Auto-detect": "auto"
        }
        if isinstance(delimiter, str) and delimiter in delimiter_map:
            delimiter = delimiter_map[delimiter]
        
        # Read the file with detected encoding
        try:
            with open(file_path, 'r', newline='', encoding=encoding, errors='replace') as f:
                if delimiter == "auto":
                    sample = f.read(4096)
                    f.seek(0)
                    try:
                        delimiter = csv.Sniffer().sniff(sample).delimiter
                        logger.debug(f"Auto-detected delimiter: '{delimiter}'")
                        self.last_detected_delimiter = delimiter
                    except Exception:
                        delimiter = ','
                        logger.debug("Could not auto-detect delimiter, defaulting to comma")
                        self.last_detected_delimiter = delimiter
                        
                reader = csv.reader(f, delimiter=delimiter)
                rows = list(reader)
                
                if not rows:
                    logger.warning(f"CSV file is empty: {file_path}")
                    return [], None
                
                logger.debug(f"CSV file loaded with {len(rows)} rows")
                
                if has_header:
                    headers = rows[0]
                    data = rows[1:]
                else:
                    if not rows[0]:
                        logger.warning(f"First row is empty in CSV file: {file_path}")
                        return [], None
                        
                    headers = [f"Column {i+1}" for i in range(len(rows[0]))]
                    data = rows
                    
                if skip_rows:
                    data = data[skip_rows:]
                    
                return data, headers
        except csv.Error as e:
            logger.error(f"CSV parsing error: {e}")
            return [], None
        except Exception as e:
            logger.error(f"File reading error: {e}")
            return [], None
    
    def _extract_data_from_text(self, text, options):
        """Extract data from pasted text
        
        Args:
            text: Text containing device data
            options: Import options
            
        Returns:
            tuple: (data, headers) where data is a list of rows and headers is a list of column names
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for import")
            return [], None
            
        # Get options
        delimiter = options.get('delimiter', ',')
        has_header = options.get('has_header', True)
        skip_rows = max(int(options.get('skip_rows', 0)), 0)
        
        # Handle different delimiter options
        delimiter_map = {
            "Comma (,)": ',',
            "Tab": '\t',
            "Semicolon (;)": ';',
            "Pipe (|)": '|',
            "Space": ' ',
            "Auto-detect": "auto"
        }
        if isinstance(delimiter, str) and delimiter in delimiter_map:
            delimiter = delimiter_map[delimiter]
            
        # Check if this is a simple list (one entry per line)
        lines = text.splitlines()
        
        # Detect if it's a simple list of IPs/hostnames or CSV data
        is_simple_list = True
        delimiter_probe = delimiter if delimiter != "auto" else ","
        for line in lines[:10]:  # Check first 10 lines
            if line.strip() and delimiter_probe in line:
                is_simple_list = False
                break
        
        # Handle simple list of IPs or hostnames (one per line)
        if is_simple_list and len(lines) > 0:
            logger.debug("Detected simple list - one entry per line")
            valid_lines = [line.strip() for line in lines if line.strip()]
            if valid_lines:
                # Create a simple csv structure with one column
                data = [[line] for line in valid_lines]
                headers = ["ip_address"]
                logger.debug(f"Created {len(data)} rows with 1 column from line-by-line input")
                if skip_rows:
                    data = data[skip_rows:]
                return data, headers
        
        # Otherwise process as normal CSV
        try:
            if delimiter == "auto":
                sample = "\n".join(lines[:10])
                try:
                    delimiter = csv.Sniffer().sniff(sample).delimiter
                except Exception:
                    delimiter = ','
                self.last_detected_delimiter = delimiter
                    
            logger.debug(f"Processing as CSV with delimiter: '{delimiter}'")
            f = io.StringIO(text)
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)
            
            if not rows:
                logger.warning("No rows found in pasted text")
                return [], None
            
            # Check if we have any non-empty rows
            valid_rows = []
            for row in rows:
                if row and any(cell.strip() for cell in row if cell):
                    valid_rows.append(row)
            
            if not valid_rows:
                logger.warning("No valid data rows found in pasted text")
                return [], None
            
            # Use valid rows for further processing
            rows = valid_rows
            
            if has_header and len(rows) > 1:
                headers = rows[0]
                data = rows[1:]
            else:
                headers = [f"Column {i+1}" for i in range(len(rows[0]))]
                data = rows
                
            if skip_rows:
                data = data[skip_rows:]
                
            return data, headers
        except Exception as e:
            logger.error(f"Error parsing CSV text: {e}", exc_info=True)
            return [], None

    def get_excel_sheet_names(self, file_path):
        """Return a list of worksheet names for an Excel file.

        This is used by the import wizard UI to let users choose
        which worksheet to import from when a file has multiple sheets.
        """
        sheet_names = []
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in [".xlsx", ".xls"]:
                return sheet_names

            # Prefer pandas if available for consistent behavior
            if _try_import_pandas():
                pd = get_pandas()
                excel_file = pd.ExcelFile(file_path)
                return list(excel_file.sheet_names)

            if file_ext == ".xlsx" and HAS_OPENPYXL:
                openpyxl_mod = get_openpyxl()
                if openpyxl_mod:
                    workbook = openpyxl_mod.load_workbook(file_path, read_only=True)
                    return list(workbook.sheetnames)

            if file_ext == ".xls" and HAS_XLRD:
                xlrd_mod = get_xlrd()
                if xlrd_mod:
                    workbook = xlrd_mod.open_workbook(file_path)
                    return list(workbook.sheet_names())
        except Exception as e:
            logger.error(f"Error getting Excel sheet names: {e}", exc_info=True)
        return sheet_names
        
    def _import_data(self, data, headers, options):
        """Import device data from extracted rows
        
        Args:
            data: List of data rows
            headers: List of column headers
            options: Import options
            
        Returns:
            tuple: (success, stats) where success is a boolean and stats is a dict with:
                - imported_count: Number of devices imported
                - skipped_count: Number of devices skipped
                - error_count: Number of devices with errors
        """
        if not data or not headers:
            return False, {"imported_count": 0, "skipped_count": 0, "error_count": 0}
            
        # Initialize stats
        stats = {
            "imported_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            # Optional details for UI to explain why rows were skipped
            "skipped_reasons": [],
        }
        
        # Get options
        field_mapping = options.get('field_mapping', {})
        duplicate_strategy = options.get('duplicate_strategy')
        skip_duplicates = options.get('skip_duplicates', False)
        mark_imported = options.get('mark_imported', True)
        target_group = options.get('target_group', None)
        progress_callback = options.get('progress_callback')
        
        if not duplicate_strategy:
            duplicate_strategy = "skip" if skip_duplicates else "create_new"
        
        # If no field mapping provided, try to auto-detect
        if not field_mapping:
            field_mapping = self._auto_detect_field_mapping(headers)
            
        # Check for duplicates if needed
        existing_ips = {}
        existing_hostnames = {}
        
        if duplicate_strategy in ["skip", "overwrite"]:
            for device in self.device_manager.get_devices():
                ip = device.get_property("ip_address")
                hostname = device.get_property("hostname")
                
                if ip and ip.strip():
                    existing_ips[ip.strip()] = device
                if hostname and hostname.strip():
                    existing_hostnames[hostname.strip()] = device
        
        # Process each row and create devices (bulk: save workspace once at end)
        total_rows = len(data)
        processed_rows = 0
        self.device_manager.begin_bulk_operation()
        row_index = 0
        for row_data in data:
            row_index += 1
            processed_rows += 1
            if progress_callback:
                progress_callback(processed_rows, total_rows)
            # Skip empty rows or rows with only empty strings
            if not row_data:
                continue
                
            # Check if all cells are empty strings (if they're strings)
            if all((isinstance(cell, str) and cell.strip() == "") for cell in row_data if cell is not None):
                continue
                
            # Create base device properties
            device_props = {}
            row_groups = []
            
            # Map fields based on the field mapping
            for i, header in enumerate(headers):
                if i < len(row_data):
                    value = row_data[i]
                    
                    # Find the device property for this header
                    prop_name = None
                    
                    # Check if the header is in field_mapping
                    for field_name, mapped_headers in field_mapping.items():
                        if header in mapped_headers:
                            prop_name = field_name
                            break
                    
                    # If not found in mapping, check for exact matches with common property names
                    if prop_name is None:
                        header_lower = header.lower()
                        common_mappings = {
                            "alias": ["name", "device name", "alias", "hostname", "host"],
                            "hostname": ["hostname", "host", "host name", "device name"],
                            "ip_address": ["ip", "ip address", "ipaddress", "address"],
                            "mac_address": ["mac", "mac address", "macaddress", "physical", "physical address"],
                            "notes": ["notes", "description", "comments"],
                            "tags": ["tags", "labels", "categories"]
                        }
                        
                        for prop, aliases in common_mappings.items():
                            if header_lower in aliases:
                                prop_name = prop
                                break
                    
                    # If still not found, use the header as the property name
                    if prop_name is None:
                        prop_name = header
                    
                    if prop_name == "ignore":
                        continue
                    if prop_name == "custom":
                        prop_name = header
                    
                    if prop_name == "groups":
                        if value not in (None, ""):
                            if isinstance(value, str):
                                row_groups.extend(
                                    [group.strip() for group in value.split(",") if group.strip()]
                                )
                            else:
                                row_groups.append(str(value))
                        continue
                    
                    # Convert value to appropriate type if needed
                    if value not in (None, ""):
                        # Handle tags as a list
                        if prop_name == "tags" and isinstance(value, str):
                            tags = [tag.strip() for tag in value.split(",") if tag.strip()]
                            device_props[prop_name] = tags
                        else:
                            device_props[prop_name] = value

            # Normalize key string fields early to avoid type issues
            for key in ["ip_address", "hostname"]:
                if key in device_props and device_props[key] is not None:
                    device_props[key] = str(device_props[key])
            
            # Skip if we don't have either IP address or hostname
            if not device_props.get("ip_address") and not device_props.get("hostname"):
                logger.debug(f"Skipping row with no IP or hostname: {row_data}")
                stats["skipped_count"] += 1
                stats["skipped_reasons"].append(
                    f"Row {row_index}: missing both IP address and hostname."
                )
                continue
                
            # Check for duplicates
            duplicate_device = None
            if duplicate_strategy in ["skip", "overwrite"]:
                ip = str(device_props.get("ip_address", "") or "").strip()
                hostname = str(device_props.get("hostname", "") or "").strip()
                
                if ip and ip in existing_ips:
                    duplicate_device = existing_ips[ip]
                elif hostname and hostname in existing_hostnames:
                    duplicate_device = existing_hostnames[hostname]
                    
                if duplicate_device and duplicate_strategy == "skip":
                    logger.debug("Skipping duplicate device based on IP/hostname")
                    stats["skipped_count"] += 1
                    stats["skipped_reasons"].append(
                        f"Row {row_index}: duplicate based on IP/hostname; existing device kept."
                    )
                    continue
            
            # Add imported tag if option is selected
            if mark_imported:
                tags = device_props.get("tags", [])
                if isinstance(tags, list):
                    if "imported" not in tags:
                        tags.append("imported")
                else:
                    tags = [tags, "imported"] if tags else ["imported"]
                device_props["tags"] = tags
                
            try:
                # Ensure all device properties have valid types
                # Extract alias first with a default value
                alias = device_props.pop("alias", "Imported Device")
                
                # Ensure string properties are strings
                for str_prop in ["hostname", "ip_address", "mac_address", "notes", "status"]:
                    if str_prop in device_props:
                        # Convert to string if not None
                        if device_props[str_prop] is not None:
                            device_props[str_prop] = str(device_props[str_prop])
                        else:
                            device_props[str_prop] = ""
                
                # Ensure tags is a list
                if "tags" in device_props and not isinstance(device_props["tags"], list):
                    if device_props["tags"] is not None:
                        device_props["tags"] = [str(device_props["tags"])]
                    else:
                        device_props["tags"] = []
                
                if duplicate_device and duplicate_strategy == "overwrite":
                    update_props = {k: v for k, v in device_props.items() if v not in ("", None)}
                    if alias not in ("", None):
                        update_props["alias"] = alias
                    if update_props:
                        duplicate_device.update_properties(update_props)
                        self.device_manager.device_changed.emit(duplicate_device)
                        # Workspace saved once at end of bulk import
                    device = duplicate_device
                else:
                    # Create a device with minimal valid properties
                    device = Device(alias=alias, **device_props)
                    
                    # Add to device manager
                    self.device_manager.add_device(device)
                
                # Add to group if specified
                if target_group and target_group != self.device_manager.root_group:
                    self.device_manager.add_device_to_group(device, target_group)
                
                # Add to groups provided in the import data
                for group_name in row_groups:
                    group = self.device_manager.get_group(group_name)
                    if not group:
                        group = self.device_manager.create_group(group_name)
                    if group and group != self.device_manager.root_group:
                        self.device_manager.add_device_to_group(device, group)
                
                # Update tracking for duplicates
                if duplicate_strategy in ["skip", "overwrite"]:
                    ip = str(device_props.get("ip_address", "") or "").strip()
                    hostname = str(device_props.get("hostname", "") or "").strip()
                    if ip:
                        existing_ips[ip] = device
                    if hostname:
                        existing_hostnames[hostname] = device
                
                stats["imported_count"] += 1
                
            except Exception as e:
                logger.error(f"Error creating device: {e}", exc_info=True)
                stats["error_count"] += 1

        self.device_manager.end_bulk_operation()
        return stats["imported_count"] > 0, stats
    
    def _auto_detect_field_mapping(self, headers):
        """Auto-detect field mappings based on headers"""
        mappings = {}
        
        for header in headers:
            header_lower = header.lower()
            
            # Default to custom
            mapping = "custom"
            
            # Check common mappings
            if header_lower in ["name", "device name", "alias", "device"]:
                mapping = "alias"
            elif header_lower in ["hostname", "host", "host name"]:
                mapping = "hostname"
            elif header_lower in ["ip", "ip address", "ipaddress", "address", "ipv4", "ipv4 address"]:
                mapping = "ip_address"
            elif header_lower in ["mac", "mac address", "macaddress", "physical address", "physical"]:
                mapping = "mac_address"
            elif header_lower in ["status", "state"]:
                mapping = "status"
            elif header_lower in ["notes", "description", "comments", "comment"]:
                mapping = "notes"
            elif header_lower in ["tags", "labels", "categories", "category"]:
                mapping = "tags"
            elif header_lower in ["vendor", "manufacturer"]:
                mapping = "vendor"
            elif header_lower in ["model", "device model"]:
                mapping = "model"
            elif header_lower in ["serial", "serial number", "serialnumber"]:
                mapping = "serial_number"
            elif header_lower in ["location", "site", "building", "room"]:
                mapping = "location"
            
            # Add to mappings
            if mapping not in mappings:
                mappings[mapping] = []
            mappings[mapping].append(header)
        
        return mappings

    def run_import_wizard(self, parent=None):
        """Run the import wizard UI
        
        Args:
            parent: Parent widget
            
        Returns:
            bool: True if import was successful, False otherwise
        """
        from ..ui.import_wizard import run_device_import_wizard
        
        return run_device_import_wizard(self.device_manager, parent)