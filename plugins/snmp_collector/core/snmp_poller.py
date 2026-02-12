#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SNMP poller (GET, GETNEXT) for testing and data collection.
Uses pysnmp hlapi; supports both sync (6.2) and async (7.x) APIs.
"""

from typing import List, Tuple, Optional

from loguru import logger

HAS_PYSNMP = False
_GET_CMD = None
_NEXT_CMD = None
_ENGINE = None
_AUTH = None
_TARGET = None
_OID_CLS = None


def _oid_from_str(oid_str: str):
    """Build OID from string like '1.3.6.1.2.1.1.1.0'."""
    if not _OID_CLS or not oid_str or not oid_str.strip():
        return None
    return _OID_CLS(oid_str.strip())


def _init_pysnmp():
    global HAS_PYSNMP, _GET_CMD, _NEXT_CMD, _ENGINE, _AUTH, _TARGET, _OID_CLS
    if HAS_PYSNMP:
        return
    try:
        from pysnmp.proto.rfc1902 import ObjectName
        _OID_CLS = ObjectName  # type: ignore
    except ImportError:
        return
    try:
        from pysnmp.hlapi.v1arch.asyncio import (
            SnmpEngine,
            CommunityData,
            UdpTransportTarget,
            getCmd,
            nextCmd,
        )
        HAS_PYSNMP = True
        _GET_CMD = getCmd
        _NEXT_CMD = nextCmd
        _ENGINE = SnmpEngine
        _AUTH = CommunityData
        _TARGET = UdpTransportTarget
        return
    except ImportError:
        pass
    try:
        from pysnmp.hlapi import (
            SnmpEngine,
            CommunityData,
            UdpTransportTarget,
            getCmd,
            nextCmd,
        )
        HAS_PYSNMP = True
        _GET_CMD = getCmd
        _NEXT_CMD = nextCmd
        _ENGINE = SnmpEngine
        _AUTH = CommunityData
        _TARGET = UdpTransportTarget
    except ImportError as e:
        logger.warning(f"pysnmp not available for polling: {e}")


def snmp_get(
    host: str,
    oids: List[str],
    community: str = "public",
    port: int = 161,
    timeout: int = 5,
) -> Tuple[bool, List[Tuple[str, str]], Optional[str]]:
    """
    Perform SNMP GET on host for given OIDs.

    Returns:
        (success, list of (oid, value) tuples, error_message)
    """
    _init_pysnmp()
    if not HAS_PYSNMP:
        return False, [], "pysnmp not available"
    try:
        target = _TARGET((host, port), timeout=timeout)
        auth = _AUTH(community)
        engine = _ENGINE()
        var_binds = [_oid_from_str(o) for o in oids if o.strip()]
        if not var_binds:
            return False, [], "No valid OIDs provided"
        cmd_iter = _GET_CMD(engine, auth, target, *var_binds)
        try:
            error_indication, error_status, error_index, var_bind_table = next(cmd_iter)
        except StopIteration:
            return False, [], "No response"
        if error_indication:
            return False, [], str(error_indication)
        if error_status:
            return False, [], f"SNMP error: {error_status.prettyPrint()}"
        results = []
        for var_bind in var_bind_table:
            oid, val = var_bind
            results.append((str(oid.prettyPrint()), str(val.prettyPrint())))
        return True, results, None
    except Exception as e:
        return False, [], str(e)


def snmp_getnext(
    host: str,
    oid: str,
    community: str = "public",
    port: int = 161,
    timeout: int = 5,
    max_repetitions: int = 25,
) -> Tuple[bool, List[Tuple[str, str]], Optional[str]]:
    """
    Perform SNMP GETNEXT on host starting from OID.
    Returns up to max_repetitions var-binds.

    Returns:
        (success, list of (oid, value) tuples, error_message)
    """
    _init_pysnmp()
    if not HAS_PYSNMP:
        return False, [], "pysnmp not available"
    try:
        target = _TARGET((host, port), timeout=timeout)
        auth = _AUTH(community)
        engine = _ENGINE()
        start_oid = _oid_from_str(oid.strip()) if oid.strip() else None
        if not start_oid:
            return False, [], "No valid OID provided"
        results = []
        for error_indication, error_status, error_index, var_bind_table in _NEXT_CMD(
            engine, auth, target, start_oid, maxCalls=max_repetitions
        ):
            if error_indication:
                return False, results, str(error_indication)
            if error_status:
                return False, results, f"SNMP error: {error_status.prettyPrint()}"
            for var_bind in var_bind_table:
                oid_obj, val = var_bind
                results.append((str(oid_obj.prettyPrint()), str(val.prettyPrint())))
        return True, results, None
    except Exception as e:
        return False, [], str(e)
