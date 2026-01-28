# Report Generator subnet helpers (parse_subnet, ip_in_subnet).
# Pure helpers; no plugin state.

import ipaddress
from loguru import logger


def parse_subnet(subnet_text):
    """Parse a subnet string into an ip_network or None if invalid."""
    subnet_text = (subnet_text or "").strip()
    if not subnet_text:
        return None
    try:
        return ipaddress.ip_network(subnet_text, strict=False)
    except Exception:
        logger.debug(f"Report Generator: Invalid subnet or IP: {subnet_text!r}")
        return None


def ip_in_subnet(ip_address_val, subnet):
    """Return True if the given IP string is in the subnet (ip_network or None)."""
    if not subnet:
        return False
    try:
        return ipaddress.ip_address(ip_address_val) in subnet
    except Exception:
        return False
