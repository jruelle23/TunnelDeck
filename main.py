# Clone this subdirectory of decky-loader to the root of this plugin, 
# so it's imports can be resolved: https://github.com/SteamDeckHomebrew/decky-loader/tree/main/backend/decky_loader
import decky;
import json
import logging
import pprint
import re
import subprocess
import traceback
from typing import Any, Optional, TypedDict
from settings import SettingsManager


logging.basicConfig(filename=decky.DECKY_PLUGIN_LOG_DIR + "/tunneldeck.log",
                    format="[TunnelDeck] %(asctime)s %(levelname)s %(message)s",
                    filemode="w+",
                    force=True)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

IPV6_GATEWAY_KEYS = ['IP6.GATEWAY', 'IP6.DNS[3]', 'IP6.DNS[2]', 'IP6.DNS[1]']
IPV4_GATEWAY_KEYS = ['IP4.GATEWAY', 'IP4.DNS[3]', 'IP4.DNS[2]', 'IP4.DNS[1]']

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


def run_cmd(args: list[str], timeout: int = 15) -> Optional[subprocess.CompletedProcess[str]]:
    """Run a command with capture, returning None on timeout."""
    try:
        return subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
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
        return new_id.split(':', 1)[1] if ':' in new_id else None
    if parser_type == 1:
        # IPV6 - value (with colons) after the first ':'
        return new_id.split(':', 1)[1] if ':' in new_id else None
    if parser_type == 2:
        # :domain_name_servers = 8.8.8.8 192.168.2.1 -> last DNS entry
        if '=' not in new_id:
            return None
        servers = new_id.split('=', 1)[1].split()
        return servers[-1] if servers else None
    return None


def get_active_connection() -> Optional[Connection]:
    result = run_cmd(["nmcli", "-t", "connection", "show", "--active"])
    if result is None:
        return None
    mapped = map(connection_mapper, result.stdout.splitlines())
    return next(filter(lambda xn: 'wireless' in xn["type"] or 'ethernet' in xn["type"], mapped), None)

def log_pretty(obj: Any) -> str:
    pp = pprint.PrettyPrinter(indent=2, sort_dicts=False)
    return f"{pp.pformat(obj)}"


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


class Plugin:
    settings: SettingsManager = SettingsManager("tunneldeck")
    # Cached data to prevent redundant calls.
    current_data: CachedData = empty_cached_data()

    # region Plugin entry / exit
    async def _main(self) -> None:
        logger.info("Loading OpenVPN setting")
        await self.reset_cached_data()
        openvpn_enabled: bool = self.settings.getSetting("openvpn_enabled", False)
        logger.info("OpenVPN enabled: %s", "yes" if openvpn_enabled else "no")

    async def _unload(self) -> None:
        openvpn_enabled: bool = self.settings.getSetting("openvpn_enabled", False)
        logger.info("OpenVPN enabled: %s", "yes" if openvpn_enabled else "no")

    # endregion

    # region Network info collectors
    # Reset all cached network information.
    async def reset_cached_data(self) -> bool:
        logger.debug(f'reset_cached_data called - Seperator - Last set was {log_pretty(self.current_data)}')
        self.current_data = empty_cached_data()
        return True

    # Collect the IP address of steam
    async def get_steam_ip(self) -> Optional[str]:
        logger.debug("Collecting steam's IP")
        getent_data = run_cmd(["getent", "ahosts", "steampowered.com"])
        if getent_data is None or (getent_data.stderr and not getent_data.stdout):
            return None
        for line in getent_data.stdout.splitlines():
            if "STREAM" in line:
                res = line.split(" ")[0]
                logger.debug(f"steam's ip is {log_pretty(res)}")
                self.current_data["steam_ip"] = res
                return res
        return None

    # Collect both priority interface name and IP
    async def get_priority_interface(self) -> PriorityInterface:
        try:
            logger.debug("get_priority_interface - enter")

            steam_ip: Optional[str] = self.current_data["steam_ip"]
            if not steam_ip:
                steam_ip = await self.get_steam_ip()

            if not steam_ip:
                logger.debug("get_priority_interface - break out due to no steam IP found")
                self.current_data['priority_interface'] = bad_response()
                return bad_response()

            logger.debug("get_priority_interface - got steam IP")

            ip_data = run_cmd(["ip", "-j", "route", "get", steam_ip])
            logger.debug("get_priority_interface - got ip route data")
            result: PriorityInterface
            if ip_data is None or ip_data.stderr or not ip_data.stdout:
                result = bad_response()
            else:
                try:
                    ip_route_data: list[dict[str, Any]] = json.loads(ip_data.stdout)
                    result = {
                        "success": True,
                        "data": ip_route_data[0]["dev"],
                        "ip": ip_route_data[0]['prefsrc'],
                    }
                except (ValueError, KeyError, IndexError) as e:
                    logger.error(f"get_priority_interface - JSON parsing failed due to {e}")
                    result = bad_response()

            self.current_data['priority_interface'] = result
            return result
        except Exception as err:
            logger.error(f'get_priority_interface error - {log_pretty(err)}')
            failure: PriorityInterface = {
                "success": False,
                "data": log_pretty(err),
                "ip": "",
            }
            return failure

    # Collect detailed networking information based on the prioritized interface name.
    async def get_prioritized_network_info(self) -> NetworkInfo:
        try:
            logger.debug("get_prioritized_network_info enter")

            connection_data: Optional[Connection] = self.current_data['active_connection']
            if not connection_data['connected'] or connection_data['name'] == "":
                connection_data = await self.active_connection()
            logger.debug("get_prioritized_network_info connection_data %s", connection_data)

            interface_name: PriorityInterface = self.current_data["priority_interface"]
            if not interface_name['success'] or not interface_name['data']:
                interface_name = await self.get_priority_interface()

            logger.debug("get_prioritized_network_info interface_name %s", interface_name)

            if connection_data is None or not interface_name['success'] or not interface_name['data']:
                logger.debug("get_prioritized_network_info instant drop out due to no response or bad interface")
                return {"success": False, "data": "N/A", "gateway_ping": False}

            nmcli_result = run_cmd(["nmcli", "-f", "all", "-t", "device", "show", interface_name['data']])
            nmcli_res: list[str] = nmcli_result.stdout.splitlines() if nmcli_result else []
            logger.debug("get_prioritized_network_info nmcli_res %s", nmcli_res)

            network_info: list[str] = []

            collected_gateway: Optional[str] = None
            for e in nmcli_res:
                parts = e.split(":")
                found_value: Optional[str] = parts[1] if len(parts) > 1 else None
                # region Priority network data
                if "GENERAL.DEVICE" in e and found_value:
                    network_info.append(f"DEVICE: {found_value}")
                if "GENERAL.TYPE" in e and found_value:
                    network_info.append(f"TYPE: {found_value}")
                if "GENERAL.STATE" in e and found_value:
                    network_info.append(f"STATE: {found_value}")
                if "GENERAL.REASON" in e and found_value:
                    network_info.append(f"REASON: {found_value}")
                if "GENERAL.IP4-CONNECTIVITY" in e and found_value:
                    network_info.append(f"IP4-CONN: {found_value}")
                if "GENERAL.IP6-CONNECTIVITY" in e and found_value:
                    network_info.append(f"IP6-CONN: {found_value}")
                if "GENERAL.IP-IFACE" in e and found_value:
                    network_info.append(f"IP-IFACE: {found_value}")
                if "GENERAL.CONNECTION" in e and found_value:
                    network_info.append(f"CONNECTION: {found_value}")
                if "GENERAL.METERED" in e and found_value:
                    network_info.append(f"METERED: {found_value}")
                if "CAPABILITIES.SPEED" in e and found_value:
                    network_info.append(f"SPEED: {found_value}")

                if ".ADDRESS" in e and found_value:
                    item = e.split(':')
                    network_info.append(f"{item.pop(0)}: {':'.join(item)}")
                if ".GATEWAY" in e and found_value:
                    item = e.split(':')
                    item.pop(0)
                    network_info.append(f"{e.split(':')[0]}: {':'.join(item)}")
                if ".DNS" in e and found_value:
                    item = e.split(':')
                    item.pop(0)
                    network_info.append(f"{e.split(':')[0]}: {':'.join(item)}")
                # endregion
                # region gateway data
                if not connection_data["ipv6_disabled"]:
                    for key in IPV6_GATEWAY_KEYS:
                        if collected_gateway:
                            break
                        logger.debug(f'BIG - {log_pretty(key)} :::: {log_pretty(e)} :::: {log_pretty(found_value)}')
                        if key in e and found_value:
                            collected_gateway = gateway_finder(e, 1)
                            logger.debug(f'BIG - Gateway is now {collected_gateway}')
                            break
                for key in IPV4_GATEWAY_KEYS:
                    if collected_gateway:
                        break
                    logger.debug(f'BIG - {log_pretty(key)} :::: {log_pretty(e)} :::: {log_pretty(found_value)}')
                    if key in e and found_value:
                        collected_gateway = gateway_finder(e, 0)
                        logger.debug(f'BIG - Gateway is now {collected_gateway}')

                if not collected_gateway and ":domain_name_servers" in e and found_value:
                    logger.debug(f'BIG - :domain_name_servers :::: {log_pretty(e)} :::: {log_pretty(found_value)}')
                    collected_gateway = gateway_finder(e, 2)
                # endregion
            if collected_gateway is None:
                logger.debug("get_prioritized_network_info did not find a gateway address")
                gateway_ping = False
            else:
                gateway_ping = await self.can_ping_address(collected_gateway)

            logger.debug("get_prioritized_network_info finished")

            ping_res: list[str] = []
            for ping in self.current_data['ping_results']:
                address = ping.get("address", "")
                could_ping = ping.get("could_ping", False)
                str_builder = f'Pinging {address}'
                str_builder = f'{str_builder} {"succeeded" if could_ping else "failed"}'
                if could_ping:
                    str_builder = f'{str_builder} in {ping.get("ping_time", "")}'
                ping_res.append(str_builder)

            final_res = '\n'.join(ping_res + network_info)
            return {
                "success": bool(network_info),
                "data": final_res,
                "gateway_ping": gateway_ping,
            }
        except Exception as err:
            logger.error(f'get_prioritized_network_info error - {log_pretty(err)} - {traceback.format_exc()}')
            return {
                "success": False,
                "data": str(err),
                "gateway_ping": False,
            }

    # Can we ping steampowered.com
    async def is_internet_available(self) -> bool:
        return await self.can_ping_address("steampowered.com")

    # Can we ping the provided network address
    async def can_ping_address(self, address: str) -> bool:
        logger.debug("Pinging %s", address)
        ping_data = run_cmd(["ping", "-c", "1", "-W", "5", address])
        ping_res = ping_data is not None and not ping_data.stderr
        if not ping_res:
            self.current_data['ping_results'].append({
                'address': address,
                'could_ping': False,
            })
        else:
            ping_time = ''
            for item in (ping_data.stdout if ping_data else "").splitlines():
                if 'rtt' in item.lower():
                    ping_time = item.split('=')[1].split('/')[1]
            self.current_data['ping_results'].append({
                'address': address,
                'could_ping': True,
                'ping_time': f'{ping_time} ms',
            })
        logger.debug(f"Pinging {address} finished. Results: {ping_res}")
        return ping_res

    # endregion

    # region Collect and set current VPN
    # Lists the connections from network manager.
    # If device is -- then it's disconnected.
    async def show(self) -> list[Connection]:
        result = run_cmd(["nmcli", "-t", "connection", "show"])
        if result is None:
            return []
        mapped = list(map(connection_mapper, result.stdout.splitlines()))
        logger.info(f'SHOW - found the following possible networks: {log_pretty(mapped)}')
        return mapped

    # Establishes a connection to a VPN
    async def up(self, uuid: str) -> str:
        logger.info("OPENING connection to: " + uuid)
        await self.reset_cached_data()
        result = run_cmd(["nmcli", "connection", "up", uuid])
        return result.stdout if result else ""

    # Closes a connection to a VPN
    async def down(self, uuid: str) -> str:
        logger.info("CLOSING connection to: " + uuid)
        await self.reset_cached_data()
        result = run_cmd(["nmcli", "connection", "down", uuid])
        return result.stdout if result else ""

    # Checks if IPV6 is disabled on Wi-Fi
    async def active_connection(self) -> Optional[Connection]:
        logger.debug("active_connection enter")

        connection = get_active_connection()
        if connection is None:
            logger.debug("active_connection connection is none")
            return None

        logger.debug("active_connection nmcli call")
        result = run_cmd(["nmcli", "connection", "show", connection["uuid"]])
        stdout = result.stdout if result else ""
        ipv6_method = next((line for line in stdout.splitlines() if "ipv6.method" in line), "")
        connection["ipv6_disabled"] = "disabled" in ipv6_method

        logger.debug("active_connection nmcli result collected - ipv6 disabled is %s", connection["ipv6_disabled"])
        self.current_data['active_connection'] = connection
        return connection

    # endregion

    # region Collect and modify connection settings
    # Disables IPV6 on currently active connection
    async def disable_ipv6(self) -> bool:
        await self.reset_cached_data()

        connection = get_active_connection()
        if connection is None:
            return True

        logger.info("DISABLING IPV6 for: " + connection["uuid"])
        subprocess.run(["nmcli", "connection", "modify", connection["uuid"], "ipv6.method", "disabled"])
        subprocess.run(["systemctl", "restart", "NetworkManager"])
        return True

    # Enable IPV6 on currently active connection
    async def enable_ipv6(self) -> bool:
        await self.reset_cached_data()

        connection = get_active_connection()
        if connection is None:
            return True

        logger.info("ENABLING IPV6 for: " + connection["uuid"])
        subprocess.run(["nmcli", "connection", "modify", connection["uuid"], "ipv6.method", "auto"])
        subprocess.run(["systemctl", "restart", "NetworkManager"])
        return True
