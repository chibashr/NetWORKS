#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SNMP poller (GET, GETNEXT) for testing and data collection.
Uses pysnmp hlapi asyncio; runs in thread via asyncio.run().
"""

import asyncio
from typing import List, Tuple, Optional

from loguru import logger

HAS_PYSNMP = False
_GET_CMD = None
_NEXT_CMD = None
_ENGINE = None
_AUTH = None
_TARGET = None
_CONTEXT = None
_OBJECT_TYPE = None
_OBJECT_IDENTITY = None


def _init_pysnmp():
    global HAS_PYSNMP, _GET_CMD, _NEXT_CMD, _ENGINE, _AUTH, _TARGET, _CONTEXT
    global _OBJECT_TYPE, _OBJECT_IDENTITY
    if HAS_PYSNMP:
        return
    try:
        from pysnmp.hlapi.asyncio import getCmd, nextCmd
        from pysnmp.entity.engine import SnmpEngine
        from pysnmp.hlapi.asyncio.auth import CommunityData
        from pysnmp.hlapi.asyncio.transport import UdpTransportTarget
        from pysnmp.hlapi.asyncio.context import ContextData
        from pysnmp.smi.rfc1902 import ObjectType, ObjectIdentity

        HAS_PYSNMP = True
        _GET_CMD = getCmd
        _NEXT_CMD = nextCmd
        _ENGINE = SnmpEngine
        _AUTH = CommunityData
        _TARGET = UdpTransportTarget
        _CONTEXT = ContextData
        _OBJECT_TYPE = ObjectType
        _OBJECT_IDENTITY = ObjectIdentity
    except ImportError as e:
        logger.warning(f"pysnmp not available for polling: {e}")


def _make_var_binds(oid_strs: List[str]):
    """Build ObjectType varBinds from OID strings."""
    if not _OBJECT_TYPE or not _OBJECT_IDENTITY:
        return []
    return [_OBJECT_TYPE(_OBJECT_IDENTITY(oid.strip())) for oid in oid_strs if oid.strip()]


async def _do_get(host: str, oids: List[str], community: str, port: int, timeout: int):
    """Async GET implementation."""
    target = _TARGET((host, port), timeout=timeout)
    auth = _AUTH(community)
    engine = _ENGINE()
    ctx = _CONTEXT()
    var_binds = _make_var_binds(oids)
    if not var_binds:
        return False, [], "No valid OIDs provided"
    err_ind, err_status, err_idx, var_bind_table = await _GET_CMD(
        engine, auth, target, ctx, *var_binds, lookupMib=False
    )
    if err_ind:
        return False, [], str(err_ind)
    if err_status:
        return False, [], f"SNMP error: {err_status}"
    results = []
    for var_bind in var_bind_table:
        oid, val = var_bind
        results.append((str(oid.prettyPrint()), str(val.prettyPrint())))
    return True, results, None


async def _do_getnext(host: str, oid: str, community: str, port: int, timeout: int, max_rep: int):
    """Async GETNEXT implementation - fetches next OID(s) up to max_rep."""
    from pysnmp.proto.rfc1905 import Null, endOfMibView

    target = _TARGET((host, port), timeout=timeout)
    auth = _AUTH(community)
    engine = _ENGINE()
    ctx = _CONTEXT()
    var_binds = _make_var_binds([oid])
    if not var_binds:
        return False, [], "No valid OID provided"
    results = []
    for _ in range(max_rep):
        # Build (oid, Null) for nextCmd request
        next_req = [_OBJECT_TYPE(vb[0], Null("")) for vb in var_binds]
        err_ind, err_status, err_idx, var_bind_table = await _NEXT_CMD(
            engine, auth, target, ctx, *next_req, lookupMib=False
        )
        if err_ind:
            return False, results, str(err_ind)
        if err_status:
            return False, results, f"SNMP error: {err_status}"
        if not var_bind_table:
            break
        row = var_bind_table[0]
        var_binds = []
        for oid_obj, val in row:
            if val is endOfMibView:
                return True, results, None
            results.append((str(oid_obj.prettyPrint()), str(val.prettyPrint())))
            var_binds.append((oid_obj, val))
        if not var_binds:
            break
    return True, results, None


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
        return asyncio.run(_do_get(host, oids, community, port, timeout))
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
        return asyncio.run(_do_getnext(host, oid, community, port, timeout, max_repetitions))
    except Exception as e:
        return False, [], str(e)
