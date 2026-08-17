from typing import Final

# Targets & Hosts
STEAM_HOSTNAME: Final[str] = "steampowered.com"

# Subprocess Timeouts (seconds)
DEFAULT_CMD_TIMEOUT: Final[int] = 15
PING_TIMEOUT: Final[int] = 5
PING_COUNT: Final[int] = 1

# Network Manager Gateway Keys
IPV6_GATEWAY_KEYS: Final[tuple[str, ...]] = (
    "IP6.GATEWAY",
    "IP6.DNS[3]",
    "IP6.DNS[2]",
    "IP6.DNS[1]",
)

IPV4_GATEWAY_KEYS: Final[tuple[str, ...]] = (
    "IP4.GATEWAY",
    "IP4.DNS[3]",
    "IP4.DNS[2]",
    "IP4.DNS[1]",
)

# nmcli prefix mappings for device status, TODO use it
NMCLI_FIELD_PREFIX_MAP: Final[dict[str, str]] = {
    "GENERAL.DEVICE": "DEVICE",
    "GENERAL.TYPE": "TYPE",
    "GENERAL.STATE": "STATE",
    "GENERAL.REASON": "REASON",
    "GENERAL.IP4-CONNECTIVITY": "IP4-CONN",
    "GENERAL.IP6-CONNECTIVITY": "IP6-CONN",
    "GENERAL.IP-IFACE": "IP-IFACE",
    "GENERAL.CONNECTION": "CONNECTION",
    "GENERAL.METERED": "METERED",
    "CAPABILITIES.SPEED": "SPEED",
}
