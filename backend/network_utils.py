from .config import DEFAULT_CMD_TIMEOUT
from .logger import logger
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


def gateway_finder(new_id: str, parser_type: int) -> Optional[str]:
    if parser_type == 0:
        # IPV4 - value after the first ':'
        return new_id.split(":", 1)[1] if ":" in new_id else None
    if parser_type == 1:
        # IPV6 - value (with colons) after the first ':'
        return new_id.split(":", 1)[1] if ":" in new_id else None
    if parser_type == 2:
        # :domain_name_servers = 8.8.8.8 192.168.2.1 -> last DNS entry
        if "=" not in new_id:
            return None
        servers = new_id.split("=", 1)[1].split()
        return servers[-1] if servers else None
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
