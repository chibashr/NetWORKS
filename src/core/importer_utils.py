#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Optional dependencies and pandas lazy-load for the importer.
Extracted from importer to keep DeviceImporter focused and to isolate optional deps.
"""

from loguru import logger

# Optional dependency flags and module refs
HAS_PANDAS = False
_PANDAS_IMPORT_ERROR = None
_pd_module = None
_openpyxl = None
_xlrd = None
_docx_document = None
_chardet = None

try:
    import openpyxl
    _openpyxl = openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
    logger.debug("openpyxl not available for importing XLSX files")

try:
    import xlrd
    _xlrd = xlrd
    HAS_XLRD = True
except ImportError:
    HAS_XLRD = False
    logger.debug("xlrd not available for importing legacy Excel files")

try:
    from docx import Document
    _docx_document = Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
    logger.debug("python-docx not available for importing Word documents")

try:
    import chardet
    _chardet = chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False
    logger.debug("chardet not available for detecting file encodings")


def _try_import_pandas():
    """Import pandas lazily; return True if pandas is available."""
    global HAS_PANDAS, _PANDAS_IMPORT_ERROR, _pd_module
    if HAS_PANDAS and _pd_module is not None:
        return True
    if _PANDAS_IMPORT_ERROR is not None:
        return False
    try:
        import pandas as pd  # type: ignore
        _pd_module = pd
        HAS_PANDAS = True
        return True
    except Exception as e:
        _PANDAS_IMPORT_ERROR = e
        logger.warning(f"pandas not available for importing Excel files: {e}")
        return False


def get_pandas():
    """Return the pandas module if available, else None."""
    _try_import_pandas()
    return _pd_module


def get_openpyxl():
    """Return the openpyxl module if available, else None."""
    return _openpyxl


def get_xlrd():
    """Return the xlrd module if available, else None."""
    return _xlrd


def get_docx_document():
    """Return the docx.Document class if available, else None."""
    return _docx_document


def get_chardet():
    """Return the chardet module if available, else None."""
    return _chardet
