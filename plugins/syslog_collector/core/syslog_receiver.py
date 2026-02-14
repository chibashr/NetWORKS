#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Syslog receiver running in background threads.
Supports UDP and TCP, configurable transport.
"""

import socket
import threading
from typing import Callable, Optional

from loguru import logger


def _run_udp_receiver(host: str, port: int, on_message: Callable, stop_event: threading.Event):
    """Run UDP syslog receiver until stop_event is set."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.settimeout(0.5)
        logger.info(f"Syslog UDP receiver listening on {host}:{port}")
        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(65535)
                if data:
                    try:
                        text = data.decode("utf-8", errors="replace").strip()
                        if text:
                            on_message(text, str(addr[0]))
                    except Exception as e:
                        logger.warning(f"Syslog UDP decode error: {e}")
            except socket.timeout:
                continue
            except OSError as e:
                if not stop_event.is_set():
                    logger.error(f"Syslog UDP receiver error: {e}")
                break
    except Exception as e:
        logger.error(f"Syslog UDP receiver failed: {e}")
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _run_tcp_receiver(host: str, port: int, on_message: Callable, stop_event: threading.Event):
    """Run TCP syslog receiver until stop_event is set."""
    server = None
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(5)
        server.settimeout(0.5)
        logger.info(f"Syslog TCP receiver listening on {host}:{port}")
        while not stop_event.is_set():
            try:
                server.settimeout(0.5)
                client, addr = server.accept()
                client.settimeout(1.0)
                try:
                    buf = b""
                    while not stop_event.is_set():
                        chunk = client.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                        # Syslog over TCP: messages may be newline or null-delimited
                        text = buf.decode("utf-8", errors="replace")
                        for sep in ("\n", "\r\n", "\x00"):
                            if sep in text:
                                parts = text.split(sep)
                                buf = parts[-1].encode("utf-8", errors="replace")
                                for p in parts[:-1]:
                                    p = p.strip()
                                    if p:
                                        on_message(p, str(addr[0]))
                                break
                finally:
                    try:
                        client.close()
                    except Exception:
                        pass
            except socket.timeout:
                continue
            except OSError as e:
                if not stop_event.is_set():
                    logger.error(f"Syslog TCP receiver error: {e}")
                break
    except Exception as e:
        logger.error(f"Syslog TCP receiver failed: {e}")
    finally:
        if server:
            try:
                server.close()
            except Exception:
                pass


class SyslogReceiverThread:
    """Background thread(s) that receive syslog messages over UDP and/or TCP."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 1514,
        transport: str = "udp",
        on_message: Optional[Callable[[str, str], None]] = None,
    ):
        self.host = host
        self.port = port
        self.transport = transport.lower()
        self.on_message = on_message or (lambda text, addr: None)
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> bool:
        """Start the syslog receiver thread(s)."""
        if self._threads:
            return all(t.is_alive() for t in self._threads)
        self._stop_event.clear()
        target_udp = lambda: _run_udp_receiver(
            self.host, self.port, self.on_message, self._stop_event
        )
        target_tcp = lambda: _run_tcp_receiver(
            self.host, self.port, self.on_message, self._stop_event
        )
        if self.transport in ("udp", "both"):
            t_udp = threading.Thread(target=target_udp, daemon=True)
            t_udp.start()
            self._threads.append(t_udp)
        if self.transport in ("tcp", "both"):
            t_tcp = threading.Thread(target=target_tcp, daemon=True)
            t_tcp.start()
            self._threads.append(t_tcp)
        return bool(self._threads)

    def stop(self):
        """Stop the syslog receiver thread(s)."""
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=3.0)
        self._threads.clear()

    @property
    def is_running(self) -> bool:
        return any(t.is_alive() for t in self._threads)
