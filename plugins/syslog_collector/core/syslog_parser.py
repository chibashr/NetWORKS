#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Syslog message parser supporting RFC 3164, RFC 5424, and raw modes.
"""

import re
from datetime import datetime
from typing import Optional

# Facility names per RFC 3164/5424
FACILITY_NAMES = [
    "kern", "user", "mail", "daemon", "auth", "syslog", "lpr", "news",
    "uucp", "cron", "authpriv", "ftp", "ntp", "audit", "alert", "clock",
    "local0", "local1", "local2", "local3", "local4", "local5", "local6", "local7",
]

# Severity names per RFC 3164/5424
SEVERITY_NAMES = [
    "emerg", "alert", "crit", "err", "warning", "notice", "info", "debug",
]


def _parse_pri(pri_str: str) -> tuple[int, int]:
    """Parse <PRI> into (facility, severity). Returns (0, 0) on failure."""
    m = re.match(r"<(\d+)>", pri_str)
    if not m:
        return 0, 0
    try:
        pri = int(m.group(1))
        facility = pri // 8
        severity = pri % 8
        return facility, severity
    except (ValueError, IndexError):
        return 0, 0


def parse_rfc3164(raw: str) -> dict:
    """
    Parse RFC 3164 (BSD) syslog format.
    Format: <PRI>TIMESTAMP HOST TAG: MESSAGE
    """
    result = {
        "raw": raw,
        "parse_mode": "rfc3164",
        "facility": 0,
        "severity": 0,
        "facility_name": "",
        "severity_name": "",
        "timestamp": "",
        "host": "",
        "tag": "",
        "message": "",
    }
    if not raw or not raw.strip():
        return result

    pri_match = re.match(r"<(\d+)>", raw)
    if not pri_match:
        result["message"] = raw
        return result

    facility, severity = _parse_pri(raw[:pri_match.end()])
    result["facility"] = facility
    result["severity"] = severity
    result["facility_name"] = FACILITY_NAMES[facility] if facility < len(FACILITY_NAMES) else f"facility{facility}"
    result["severity_name"] = SEVERITY_NAMES[severity] if severity < len(SEVERITY_NAMES) else f"severity{severity}"

    rest = raw[pri_match.end():].strip()
    # TIMESTAMP: Mmm dd hh:mm:ss (or Mmm  d hh:mm:ss for single-digit day)
    ts_match = re.match(
        r"([A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+",
        rest
    )
    if ts_match:
        result["timestamp"] = ts_match.group(1).strip()
        rest = rest[ts_match.end():]
        # HOST: non-whitespace
        host_match = re.match(r"(\S+)\s+", rest)
        if host_match:
            result["host"] = host_match.group(1)
            rest = rest[host_match.end():]
            # TAG: alphanumeric, optional
            tag_match = re.match(r"([\w\-]+):\s*", rest)
            if tag_match:
                result["tag"] = tag_match.group(1)
                rest = rest[tag_match.end():]
            result["message"] = rest.strip()
        else:
            result["message"] = rest
    else:
        result["message"] = rest

    return result


def parse_rfc5424(raw: str) -> dict:
    """
    Parse RFC 5424 (structured) syslog format.
    Format: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID STRUCTURED-DATA MSG
    """
    result = {
        "raw": raw,
        "parse_mode": "rfc5424",
        "facility": 0,
        "severity": 0,
        "facility_name": "",
        "severity_name": "",
        "version": "",
        "timestamp": "",
        "host": "",
        "app_name": "",
        "procid": "",
        "msgid": "",
        "structured_data": "",
        "message": "",
    }
    if not raw or not raw.strip():
        return result

    pri_match = re.match(r"<(\d+)>", raw)
    if not pri_match:
        result["message"] = raw
        return result

    facility, severity = _parse_pri(raw[:pri_match.end()])
    result["facility"] = facility
    result["severity"] = severity
    result["facility_name"] = FACILITY_NAMES[facility] if facility < len(FACILITY_NAMES) else f"facility{facility}"
    result["severity_name"] = SEVERITY_NAMES[severity] if severity < len(SEVERITY_NAMES) else f"severity{severity}"

    rest = raw[pri_match.end():].strip()
    parts = rest.split(None, 6)  # max 7 parts: version timestamp host app procid msgid [sd msg]
    if len(parts) < 3:
        result["message"] = rest
        return result

    result["version"] = parts[0]
    result["timestamp"] = parts[1]
    result["host"] = parts[2]
    result["app_name"] = parts[3] if len(parts) > 3 and parts[3] != "-" else ""
    result["procid"] = parts[4] if len(parts) > 4 and parts[4] != "-" else ""
    result["msgid"] = parts[5] if len(parts) > 5 and parts[5] != "-" else ""

    if len(parts) > 6:
        remainder = parts[6]
        # STRUCTURED-DATA is [id param="value"]...; MSG starts with space or is after ]
        if remainder.startswith("["):
            bracket_depth = 0
            i = 0
            for i, c in enumerate(remainder):
                if c == "[":
                    bracket_depth += 1
                elif c == "]":
                    bracket_depth -= 1
                    if bracket_depth == 0:
                        break
            result["structured_data"] = remainder[: i + 1]
            msg_part = remainder[i + 1:].strip()
            if msg_part.startswith("-"):
                msg_part = msg_part[1:].strip()
            result["message"] = msg_part
        else:
            result["message"] = remainder

    return result


def parse_raw(raw: str) -> dict:
    """Store raw message without parsing."""
    return {
        "raw": raw,
        "parse_mode": "raw",
        "facility": 0,
        "severity": 0,
        "facility_name": "",
        "severity_name": "",
        "timestamp": "",
        "host": "",
        "message": raw,
    }


def parse_syslog(raw: str, mode: str = "rfc3164") -> dict:
    """
    Parse syslog message according to mode.
    mode: "rfc3164", "rfc5424", or "raw"
    """
    if mode == "rfc5424":
        return parse_rfc5424(raw)
    if mode == "raw":
        return parse_raw(raw)
    return parse_rfc3164(raw)
