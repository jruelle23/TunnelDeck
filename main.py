# Clone this linked subdirectory of decky-loader to the root of this plugin,
# so it's imports can be resolved: https://github.com/SteamDeckHomebrew/decky-loader/tree/main/backend/decky_loader
import backend as net
from backend import (
    CachedData,
    Connection,
    NetworkInfo,
    PriorityInterface,
    empty_cached_data,
    log_pretty,
    logger,
)

from typing import Optional


class Plugin:
    def __init__(self):
        # Cached data to prevent redundant calls.
        self.current_data: CachedData = empty_cached_data()

    # Plugin entry / exit
    async def _main(self) -> None:
        logger.info("Loading TunnelDeck")
        self.__reset_cached_data()

    async def _unload(self) -> None:
        logger.info("Unloading TunnelDeck")

    # Network info collectors
    # Collect the IP address of steam
    async def get_steam_ip(self) -> Optional[str]:
        logger.debug("Collecting steam's IP")
        return net.get_steam_ip(self.current_data)

    # Collect both priority interface name and IP
    async def get_priority_interface(self) -> PriorityInterface:
        return net.get_priority_interface(self.current_data)

    # Collect detailed networking information based on the prioritized interface name.
    async def get_prioritized_network_info(self) -> NetworkInfo:
        return net.get_prioritized_network_info(self.current_data)

    # Can we ping steampowered.com
    async def is_internet_available(self) -> bool:
        return net.is_internet_available(self.current_data)

    # Can we ping the provided network address
    async def can_ping_address(self, address: str) -> bool:
        return net.can_ping_address(address, self.current_data)

    # Collect and set current VPN
    # Lists the connections from network manager.
    # If device is -- then it's disconnected.
    async def show(self) -> list[Connection]:
        return net.show()

    # Establishes a connection to a VPN
    async def up(self, uuid: str) -> str:
        self.__reset_cached_data()
        return net.up(uuid)

    # Closes a connection to a VPN
    async def down(self, uuid: str) -> str:
        self.__reset_cached_data()
        return net.down(uuid)

    # Checks if IPV6 is disabled on Wi-Fi
    async def active_connection(self) -> Optional[Connection]:
        return net.active_connection(self.current_data)

    # Collect and modify connection settings
    # Disables IPV6 on currently active connection
    async def disable_ipv6(self) -> bool:
        self.__reset_cached_data()
        return net.disable_ipv6()

    # Enable IPV6 on currently active connection
    async def enable_ipv6(self) -> bool:
        self.__reset_cached_data()
        return net.enable_ipv6()

    # Reset all cached network information.
    def __reset_cached_data(self) -> bool:
        logger.debug(
            f"reset_cached_data called - Separator - Last set was {log_pretty(self.current_data)}"
        )
        self.current_data = empty_cached_data()
        return True
