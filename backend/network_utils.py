from .config import DEFAULT_CMD_TIMEOUT, IPV4_GATEWAY_KEYS, IPV6_GATEWAY_KEYS, NMCLI_MULTI_VALUED_FIELD_SUFFIX_MAP
from .logger import logger, log_pretty
from .models import Connection
import re
import subprocess
from typing import Optional


def run_cmd(
    args: list[str], timeout: int = DEFAULT_CMD_TIMEOUT
) -> Optional[subprocess.CompletedProcess[str]]:
    """Run a command with capture, returning None on timeout."""
    try:
        return subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.error(f"Error occurred while running command: {' '.join(args)}: {e}")
        return None


def connection_mapper(xn: str) -> Connection:
    # Filter out connection names like "FBI: Surveillance van" (nmcli will escape it for us)
    components = re.split(r"(?<!\\):", xn)
    device = components[3] if len(components) > 3 else ""
    return {
        "name": components[0] if len(components) > 0 else "",
        "uuid": components[1] if len(components) > 1 else "",
        "type": components[2] if len(components) > 2 else "",
        "device": device,
        "connected": bool(device),
        "ipv6_disabled": False,
    }


def find_gateway(
    nmcli_data: dict[str, str], ipv6_disabled: bool = False
) -> Optional[str]:
    """Find the priority gateway or DNS server address from nmcli data."""
    if not ipv6_disabled:
        for key in IPV6_GATEWAY_KEYS:
            val = nmcli_data.get(key)
            if val:
                logger.debug(f"BIG - Gateway is now {val}")
                return val

    for key in IPV4_GATEWAY_KEYS:
        val = nmcli_data.get(key)
        if val:
            logger.debug(f"BIG - Gateway is now {val}")
            return val

    return None


def get_active_connection() -> Optional[Connection]:
    result = run_cmd(["nmcli", "-t", "connection", "show", "--active"])
    if result is None:
        return None
    mapped = map(connection_mapper, result.stdout.splitlines())
    return next(
        filter(lambda xn: "wireless" in xn["type"] or "ethernet" in xn["type"], mapped),
        None,
    )

def get_pattern_label(key: str) -> Optional[str]:
    """Returns the matching label for a key, or None if no match."""
    for pattern, label in NMCLI_MULTI_VALUED_FIELD_SUFFIX_MAP.items():
        if pattern in key:
            return label
    return None


def collect_pattern_groups(nmcli_map: dict[str, str]) -> dict[str, list[str]]:
    """Groups nmcli values into pre-filled categories."""
    groups: dict[str, list[str]] = {
        label: [] for label in NMCLI_MULTI_VALUED_FIELD_SUFFIX_MAP.values()
    }

    for key, value in nmcli_map.items():
        if not value:
            continue

        label = get_pattern_label(key)
        if label:
            groups[label].append(value)

    return groups


def format_grouped_network_info(groups: dict[str, list[str]]) -> list[str]:
    """Formats grouped values into newline-separated strings."""
    result: list[str] = []
    for label, values in groups.items():
        if values:
            linebreaked_values = '\n' + ('\n'.join(values) if values is not [] else 'NONE FOUND')
            result.append(f"{label}:{linebreaked_values}")
    return result
