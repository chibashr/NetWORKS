#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SNMP trap receiver running in a background thread.
Uses pysnmp asyncio dispatcher; runs in thread to avoid blocking Qt.
"""

import asyncio
import threading
from typing import Callable, Optional

from loguru import logger

HAS_PYSNMP = False
try:
    from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
    from pysnmp.carrier.asyncio.dgram import udp
    from pysnmp.proto import api
    from pyasn1.codec.ber import decoder
    HAS_PYSNMP = True
except ImportError as e:
    logger.warning(f"pysnmp not available for trap receiver: {e}")


def _parse_trap(whole_msg, transport_domain, transport_address) -> Optional[dict]:
    """Parse SNMP trap/notification from raw message. Returns dict or None."""
    if not HAS_PYSNMP:
        return None
    try:
        msg_ver = int(api.decodeMessageVersion(whole_msg))
        if msg_ver not in api.PROTOCOL_MODULES:
            return {"error": f"Unsupported SNMP version {msg_ver}"}
        p_mod = api.PROTOCOL_MODULES[msg_ver]
        req_msg, _ = decoder.decode(whole_msg, asn1Spec=p_mod.Message())
        req_pdu = p_mod.apiMessage.get_pdu(req_msg)
        result = {
            "transport_domain": str(transport_domain),
            "transport_address": str(transport_address),
            "version": msg_ver,
            "varbinds": [],
        }
        if req_pdu.isSameTypeWith(p_mod.TrapPDU()):
            if msg_ver == api.SNMP_VERSION_1:
                result["enterprise"] = str(p_mod.apiTrapPDU.get_enterprise(req_pdu).prettyPrint())
                result["agent_address"] = str(p_mod.apiTrapPDU.get_agent_address(req_pdu).prettyPrint())
                result["generic_trap"] = str(p_mod.apiTrapPDU.get_generic_trap(req_pdu).prettyPrint())
                result["specific_trap"] = str(p_mod.apiTrapPDU.get_specific_trap(req_pdu).prettyPrint())
                result["uptime"] = str(p_mod.apiTrapPDU.get_timestamp(req_pdu).prettyPrint())
                var_binds = p_mod.apiTrapPDU.get_varbinds(req_pdu)
            else:
                var_binds = p_mod.apiPDU.get_varbinds(req_pdu)
            for oid, val in var_binds:
                result["varbinds"].append({
                    "oid": str(oid.prettyPrint()),
                    "value": str(val.prettyPrint()),
                })
        return result
    except Exception as e:
        return {"error": str(e), "transport_address": str(transport_address)}


def _run_trap_receiver_loop(host: str, port: int, on_trap: Callable, stop_event: threading.Event):
    """Run asyncio-based trap receiver until stop_event is set."""
    if not HAS_PYSNMP:
        return

    def callback(transport_dispatcher, transport_domain, transport_address, whole_msg):
        while whole_msg:
            parsed = _parse_trap(whole_msg, transport_domain, transport_address)
            if parsed:
                try:
                    on_trap(parsed)
                except Exception as e:
                    logger.error(f"Trap callback error: {e}")
            break

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    dispatcher = AsyncioDispatcher()
    dispatcher.registerRecvCbFun(callback)
    try:
        transport = udp.UdpAsyncioTransport().open_server_mode((host, port))
        dispatcher.registerTransport(udp.DOMAIN_NAME, transport)
        dispatcher.jobStarted(1)
        logger.info(f"SNMP trap receiver listening on {host}:{port}")
        while not stop_event.is_set():
            loop.run_until_complete(asyncio.sleep(0.5))
    except Exception as e:
        logger.error(f"Trap receiver error: {e}")
    finally:
        try:
            dispatcher.closeDispatcher()
        except Exception:
            pass
        loop.close()


class TrapReceiverThread:
    """Background thread that receives SNMP traps."""

    def __init__(self, host: str = "0.0.0.0", port: int = 1162, on_trap: Optional[Callable] = None):
        self.host = host
        self.port = port
        self.on_trap = on_trap or (lambda x: None)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Start the trap receiver thread."""
        if not HAS_PYSNMP:
            logger.error("pysnmp not available; cannot start trap receiver")
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=_run_trap_receiver_loop,
            args=(self.host, self.port, self.on_trap, self._stop_event),
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self):
        """Stop the trap receiver thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
