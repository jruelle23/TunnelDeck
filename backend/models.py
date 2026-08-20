from typing import TypedDict


class Connection(TypedDict):
    name: str
    uuid: str
    type: str
    device: str
    connected: bool
    ipv6_disabled: bool


class PriorityInterface(TypedDict):
    success: bool
    data: str
    ip: str


class PingResult(TypedDict, total=False):
    address: str
    could_ping: bool
    ping_time: str


class NetworkInfo(TypedDict):
    success: bool
    data: str
    gateway_ping: bool


class CachedData(TypedDict):
    steam_ip: str
    active_connection: Connection
    priority_interface: PriorityInterface
    ping_results: list[PingResult]


def bad_response() -> PriorityInterface:
    return {
        "success": False,
        "data": "N/A",
        "ip": "",
    }


def empty_cached_data() -> CachedData:
    return {
        "steam_ip": "",
        "active_connection": {
            "name": "",
            "uuid": "",
            "type": "",
            "device": "",
            "connected": False,
            "ipv6_disabled": False,
        },
        "priority_interface": bad_response(),
        "ping_results": [],
    }
