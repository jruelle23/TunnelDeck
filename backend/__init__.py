"""TunnelDeck Backend Package."""

from .config import STEAM_HOSTNAME
from .logger import log_pretty, logger
from .models import (
    CachedData,
    Connection,
    NetworkInfo,
    PingResult,
    PriorityInterface,
    bad_response,
    empty_cached_data,
)
from .network import (
    active_connection,
    can_ping_address,
    disable_ipv6,
    down,
    enable_ipv6,
    get_priority_interface,
    get_prioritized_network_info,
    get_steam_ip,
    is_internet_available,
    show,
    up,
)

__all__ = [
    # Logger
    "logger",
    "log_pretty",
    # Config
    "STEAM_HOSTNAME",
    # Models
    "CachedData",
    "Connection",
    "NetworkInfo",
    "PingResult",
    "PriorityInterface",
    "bad_response",
    "empty_cached_data",
    # Network Operations
    "active_connection",
    "can_ping_address",
    "disable_ipv6",
    "down",
    "enable_ipv6",
    "get_priority_interface",
    "get_prioritized_network_info",
    "get_steam_ip",
    "is_internet_available",
    "show",
    "up",
]
