#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SNMP poller (GET, GETNEXT) for testing and data collection.
Uses pysnmp hlapi asyncio; runs in thread via asyncio.run().
Supports SNMPv1, v2c, and v3.
"""

import asyncio
from typing import List, Tuple, Optional, Any

from loguru import logger

HAS_PYSNMP = False
_GET_CMD = None
_NEXT_CMD = None
_ENGINE = None
_CommunityData = None
_UsmUserData = None
_TARGET = None
_CONTEXT = None
_OBJECT_TYPE = None
_OBJECT_IDENTITY = None
_usmHMACMD5 = None
_usmHMACSHA = None
_usmDES = None
_usmAes128 = None


def _init_pysnmp():
    global HAS_PYSNMP, _GET_CMD, _NEXT_CMD, _ENGINE
    global _CommunityData, _UsmUserData, _TARGET, _CONTEXT
    global _OBJECT_TYPE, _OBJECT_IDENTITY
    global _usmHMACMD5, _usmHMACSHA, _usmDES, _usmAes128
    if HAS_PYSNMP:
        return
    try:
        from pysnmp.hlapi.asyncio import getCmd, nextCmd
        from pysnmp.entity.engine import SnmpEngine
        from pysnmp.hlapi.asyncio.auth import (
            CommunityData,
            UsmUserData,
            usmHMACMD5AuthProtocol,
            usmHMACSHAAuthProtocol,
            usmDESPrivProtocol,
            usmAesCfb128Protocol,
        )
        from pysnmp.hlapi.asyncio.transport import UdpTransportTarget
        from pysnmp.hlapi.asyncio.context import ContextData
        from pysnmp.smi.rfc1902 import ObjectType, ObjectIdentity

        HAS_PYSNMP = True
        _GET_CMD = getCmd
        _NEXT_CMD = nextCmd
        _ENGINE = SnmpEngine
        _CommunityData = CommunityData
        _UsmUserData = UsmUserData
        _TARGET = UdpTransportTarget
        _CONTEXT = ContextData
        _OBJECT_TYPE = ObjectType
        _OBJECT_IDENTITY = ObjectIdentity
        _usmHMACMD5 = usmHMACMD5AuthProtocol
        _usmHMACSHA = usmHMACSHAAuthProtocol
        _usmDES = usmDESPrivProtocol
        _usmAes128 = usmAesCfb128Protocol
    except ImportError as e:
        logger.warning(f"pysnmp not available for polling: {e}")


def build_auth_data(
    version: str,
    community: str = "public",
    user: str = "",
    auth_protocol: str = "",
    auth_password: str = "",
    priv_protocol: str = "",
    priv_password: str = "",
) -> Any:
    """
    Build auth object for SNMP polling.
    version: "v1" | "v2c" | "v3"
    For v3: user required; auth_protocol/auth_password and priv_protocol/priv_password optional.
    """
    _init_pysnmp()
    if not HAS_PYSNMP or not _CommunityData or not _UsmUserData:
        return None

    if version == "v1":
        return _CommunityData(community, mpModel=0)
    if version == "v2c":
        return _CommunityData(community, mpModel=1)

    # v3
    auth_proto = None
    priv_proto = None
    if auth_protocol and auth_password:
        auth_proto = {"md5": _usmHMACMD5, "sha": _usmHMACSHA}.get(
            auth_protocol.lower(), _usmHMACMD5
        )
    if priv_protocol and priv_password and priv_protocol not in ("none", ""):
        priv_proto = {"des": _usmDES, "aes128": _usmAes128}.get(
            priv_protocol.lower(), _usmDES
        )

    return _UsmUserData(
        user or "initial",
        authKey=auth_password or None,
        privKey=priv_password or None,
        authProtocol=auth_proto,
        privProtocol=priv_proto,
    )


def _make_var_binds(oid_strs: List[str]):
    """Build ObjectType varBinds from OID strings."""
    if not _OBJECT_TYPE or not _OBJECT_IDENTITY:
        return []
    return [_OBJECT_TYPE(_OBJECT_IDENTITY(oid.strip())) for oid in oid_strs if oid.strip()]


async def _do_get(host: str, oids: List[str], auth_data: Any, port: int, timeout: int):
    """Async GET implementation."""
    target = _TARGET((host, port), timeout=timeout)
    engine = _ENGINE()
    ctx = _CONTEXT()
    var_binds = _make_var_binds(oids)
    if not var_binds:
        return False, [], "No valid OIDs provided"
    err_ind, err_status, err_idx, var_bind_table = await _GET_CMD(
        engine, auth_data, target, ctx, *var_binds, lookupMib=False
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


async def _do_getnext(host: str, oid: str, auth_data: Any, port: int, timeout: int, max_rep: int):
    """Async GETNEXT implementation - fetches next OID(s) up to max_rep."""
    from pysnmp.proto.rfc1905 import Null, endOfMibView

    target = _TARGET((host, port), timeout=timeout)
    engine = _ENGINE()
    ctx = _CONTEXT()
    var_binds = _make_var_binds([oid])
    if not var_binds:
        return False, [], "No valid OID provided"
    results = []
    for _ in range(max_rep):
        next_req = [_OBJECT_TYPE(vb[0], Null("")) for vb in var_binds]
        err_ind, err_status, err_idx, var_bind_table = await _NEXT_CMD(
            engine, auth_data, target, ctx, *next_req, lookupMib=False
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
    auth_data: Any,
    port: int = 161,
    timeout: int = 5,
) -> Tuple[bool, List[Tuple[str, str]], Optional[str]]:
    """
    Perform SNMP GET on host for given OIDs.
    auth_data: CommunityData or UsmUserData from build_auth_data().

    Returns:
        (success, list of (oid, value) tuples, error_message)
    """
    _init_pysnmp()
    if not HAS_PYSNMP:
        return False, [], "pysnmp not available"
    if not auth_data:
        return False, [], "Invalid auth configuration"
    try:
        return asyncio.run(_do_get(host, oids, auth_data, port, timeout))
    except Exception as e:
        return False, [], str(e)


def snmp_getnext(
    host: str,
    oid: str,
    auth_data: Any,
    port: int = 161,
    timeout: int = 5,
    max_repetitions: int = 25,
) -> Tuple[bool, List[Tuple[str, str]], Optional[str]]:
    """
    Perform SNMP GETNEXT on host starting from OID.
    auth_data: CommunityData or UsmUserData from build_auth_data().

    Returns:
        (success, list of (oid, value) tuples, error_message)
    """
    _init_pysnmp()
    if not HAS_PYSNMP:
        return False, [], "pysnmp not available"
    if not auth_data:
        return False, [], "Invalid auth configuration"
    try:
        return asyncio.run(_do_getnext(host, oid, auth_data, port, timeout, max_repetitions))
    except Exception as e:
        return False, [], str(e)
