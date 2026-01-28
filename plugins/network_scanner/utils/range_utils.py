#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Range utilities for the Network Scanner plugin.
Pure helpers with no plugin dependency.
"""

import ipaddress
import re


def _split_range_into_chunks(network_range, max_hosts_per_chunk=32):
    """Split a network range into smaller chunks for incremental scanning.
    Returns a list of strings (chunk targets). Single-host or small ranges return [network_range].
    """
    target_text = (network_range or "").strip()
    if not target_text:
        return [network_range]
    try:
        if "/" in target_text:
            net = ipaddress.IPv4Network(target_text, strict=False)
            n = net.num_addresses
            if n <= max_hosts_per_chunk:
                return [network_range]
            # Split into /28 subnets (16 hosts each) or similar
            new_prefix = min(28, net.prefixlen + 4)  # aim for ~16–256 hosts per subnet
            while new_prefix < 31:
                subnets = list(net.subnets(new_prefix=new_prefix))
                if len(subnets) < 2:
                    new_prefix += 1
                    continue
                return [str(s) for s in subnets]
            return [network_range]
        targets = [t for t in re.split(r"[,\s]+", target_text) if t]
        if len(targets) <= 1:
            if len(targets) == 1 and "-" in targets[0]:
                start_s, end_s = targets[0].split("-", 1)
                start_s, end_s = start_s.strip(), end_s.strip()
                start_ip = ipaddress.IPv4Address(start_s)
                end_ip = ipaddress.IPv4Address(end_s)
                n = int(end_ip) - int(start_ip) + 1
                if n <= max_hosts_per_chunk:
                    return [network_range]
                out = []
                step = max_hosts_per_chunk
                for i in range(0, n, step):
                    a = ipaddress.IPv4Address(int(start_ip) + i)
                    b = ipaddress.IPv4Address(min(int(start_ip) + i + step - 1, int(end_ip)))
                    out.append(f"{a}-{b}")
                return out
            return [network_range]
        if len(targets) <= max_hosts_per_chunk:
            return [network_range]
        out = []
        for i in range(0, len(targets), max_hosts_per_chunk):
            out.append(",".join(targets[i : i + max_hosts_per_chunk]))
        return out
    except Exception:
        return [network_range]
