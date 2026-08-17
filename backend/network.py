import json
from backend.logger import logger, log_pretty
from backend.network_utils import (
    run_cmd,
    connection_mapper,
    get_active_connection,
    gateway_finder,
)
from backend.models import (
    Connection,
    PriorityInterface,
    NetworkInfo,
    CachedData,
    bad_response,
)
from backend.config import (
    IPV4_GATEWAY_KEYS,
    IPV6_GATEWAY_KEYS,
    STEAM_HOSTNAME,
    PING_TIMEOUT,
    PING_COUNT,
)
import traceback
from typing import Any, Optional


def get_steam_ip(current_data: CachedData) -> Optional[str]:
    logger.debug("Collecting steam's IP")
    getent_data = run_cmd(["getent", "ahosts", "steampowered.com"])
    if getent_data is None:
        return None
    for line in getent_data.stdout.splitlines():
        if "STREAM" in line:
            res = line.split(" ")[0]
            logger.debug(f"steam's ip is {log_pretty(res)}")
            current_data["steam_ip"] = res
            return res
    return None


def get_priority_interface(current_data: CachedData) -> PriorityInterface:
    try:
        logger.debug("get_priority_interface - enter")

        steam_ip: Optional[str] = current_data["steam_ip"]
        if not steam_ip:
            steam_ip = get_steam_ip(current_data)

        if not steam_ip:
            logger.debug("get_priority_interface - break out due to no steam IP found")
            current_data["priority_interface"] = bad_response()
            return bad_response()

        logger.debug("get_priority_interface - got steam IP")

        ip_data = run_cmd(["ip", "-j", "route", "get", steam_ip])
        logger.debug("get_priority_interface - got ip route data")
        result: PriorityInterface
        if ip_data is None:
            result = bad_response()
        else:
            try:
                ip_route_data: list[dict[str, Any]] = json.loads(ip_data.stdout)
                result = {
                    "success": True,
                    "data": ip_route_data[0]["dev"],
                    "ip": ip_route_data[0]["prefsrc"],
                }
            except (ValueError, KeyError, IndexError) as e:
                logger.error(f"get_priority_interface - JSON parsing failed due to {e}")
                result = bad_response()

        current_data["priority_interface"] = result
        return result
    except Exception as err:
        logger.error(f"get_priority_interface error - {log_pretty(err)}")
        failure: PriorityInterface = {
            "success": False,
            "data": log_pretty(err),
            "ip": "",
        }
        return failure


def get_prioritized_network_info(current_data: CachedData) -> NetworkInfo:
    try:
        logger.debug("get_prioritized_network_info enter")

        connection_data: Optional[Connection] = current_data["active_connection"]
        if not connection_data["connected"] or connection_data["name"] == "":
            connection_data = active_connection(current_data)
        logger.debug("get_prioritized_network_info connection_data %s", connection_data)

        interface_name: PriorityInterface = current_data["priority_interface"]
        if not interface_name["success"] or not interface_name["data"]:
            interface_name = get_priority_interface(current_data)

        logger.debug("get_prioritized_network_info interface_name %s", interface_name)

        if (
            connection_data is None
            or not interface_name["success"]
            or not interface_name["data"]
        ):
            logger.debug(
                "get_prioritized_network_info instant drop out due to no response or bad interface"
            )
            return {"success": False, "data": "N/A", "gateway_ping": False}

        nmcli_result = run_cmd(
            ["nmcli", "-f", "all", "-t", "device", "show", interface_name["data"]]
        )

        # TODO apply suggested improvement
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
                item = e.split(":")
                network_info.append(f"{item.pop(0)}: {':'.join(item)}")
            if ".GATEWAY" in e and found_value:
                item = e.split(":")
                item.pop(0)
                network_info.append(f"{e.split(':')[0]}: {':'.join(item)}")
            if ".DNS" in e and found_value:
                item = e.split(":")
                item.pop(0)
                network_info.append(f"{e.split(':')[0]}: {':'.join(item)}")
            # endregion
            # region gateway data
            if not connection_data["ipv6_disabled"]:
                for key in IPV6_GATEWAY_KEYS:
                    if collected_gateway:
                        break
                    logger.debug(
                        f"BIG - {log_pretty(key)} :::: {log_pretty(e)} :::: {log_pretty(found_value)}"
                    )
                    if key in e and found_value:
                        collected_gateway = gateway_finder(e, 1)
                        logger.debug(f"BIG - Gateway is now {collected_gateway}")
                        break
            for key in IPV4_GATEWAY_KEYS:
                if collected_gateway:
                    break
                logger.debug(
                    f"BIG - {log_pretty(key)} :::: {log_pretty(e)} :::: {log_pretty(found_value)}"
                )
                if key in e and found_value:
                    collected_gateway = gateway_finder(e, 0)
                    logger.debug(f"BIG - Gateway is now {collected_gateway}")

            if not collected_gateway and ":domain_name_servers" in e and found_value:
                logger.debug(
                    f"BIG - :domain_name_servers :::: {log_pretty(e)} :::: {log_pretty(found_value)}"
                )
                collected_gateway = gateway_finder(e, 2)
            # endregion
        if collected_gateway is None:
            logger.debug("get_prioritized_network_info did not find a gateway address")
            gateway_ping = False
        else:
            gateway_ping = can_ping_address(collected_gateway, current_data)

        logger.debug("get_prioritized_network_info finished")

        ping_res: list[str] = []
        for ping in current_data["ping_results"]:
            address = ping.get("address", "")
            could_ping = ping.get("could_ping", False)
            str_builder = f"Pinging {address}"
            str_builder = f'{str_builder} {"succeeded" if could_ping else "failed"}'
            if could_ping:
                str_builder = f'{str_builder} in {ping.get("ping_time", "")}'
            ping_res.append(str_builder)

        final_res = "\n".join(ping_res + network_info)
        return {
            "success": bool(network_info),
            "data": final_res,
            "gateway_ping": gateway_ping,
        }
    except Exception as err:
        logger.error(
            f"get_prioritized_network_info error - {log_pretty(err)} - {traceback.format_exc()}"
        )
        return {
            "success": False,
            "data": str(err),
            "gateway_ping": False,
        }


def is_internet_available(current_data: CachedData) -> bool:
    return can_ping_address(STEAM_HOSTNAME, current_data)


def can_ping_address(address: str, current_data: CachedData) -> bool:
    logger.debug("Pinging %s", address)
    ping_data = run_cmd(
        ["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT), address]
    )
    ping_res = ping_data is not None and ping_data.returncode == 0
    if not ping_res:
        current_data["ping_results"].append(
            {
                "address": address,
                "could_ping": False,
            }
        )
    else:
        ping_time = ""
        for item in (ping_data.stdout if ping_data else "").splitlines():
            if "rtt" in item.lower():
                ping_time = item.split("=")[1].split("/")[1]
        current_data["ping_results"].append(
            {
                "address": address,
                "could_ping": True,
                "ping_time": f"{ping_time} ms",
            }
        )
    logger.debug(f"Pinging {address} finished. Results: {ping_res}")
    return ping_res


def show() -> list[Connection]:
    result = run_cmd(["nmcli", "-t", "connection", "show"])
    if result is None:
        return []
    mapped = list(map(connection_mapper, result.stdout.splitlines()))
    logger.info(f"SHOW - found the following possible networks: {log_pretty(mapped)}")
    return mapped


def up(uuid: str) -> str:
    logger.info("OPENING connection to: " + uuid)
    result = run_cmd(["nmcli", "connection", "up", uuid])
    return result.stdout if result else ""


def down(uuid: str) -> str:
    logger.info("CLOSING connection to: " + uuid)
    result = run_cmd(["nmcli", "connection", "down", uuid])
    return result.stdout if result else ""


def active_connection(current_data: CachedData) -> Optional[Connection]:
    logger.debug("active_connection enter")

    connection = get_active_connection()
    if connection is None:
        logger.debug("active_connection connection is none")
        return None

    logger.debug("active_connection nmcli call")
    result = run_cmd(["nmcli", "connection", "show", connection["uuid"]])
    stdout = result.stdout if result else ""
    ipv6_method = next(
        (line for line in stdout.splitlines() if "ipv6.method" in line), ""
    )
    connection["ipv6_disabled"] = "disabled" in ipv6_method

    logger.debug(
        "active_connection nmcli result collected - ipv6 disabled is %s",
        connection["ipv6_disabled"],
    )
    current_data["active_connection"] = connection
    return connection


def disable_ipv6() -> bool:
    connection = get_active_connection()
    if connection is None:
        return True

    logger.info("DISABLING IPV6 for: " + connection["uuid"])
    run_cmd(
        ["nmcli", "connection", "modify", connection["uuid"], "ipv6.method", "disabled"]
    )
    run_cmd(["nmcli", "connection", "up", connection["uuid"]])
    return True


def enable_ipv6() -> bool:
    connection = get_active_connection()
    if connection is None:
        return True

    logger.info("ENABLING IPV6 for: " + connection["uuid"])
    run_cmd(
        ["nmcli", "connection", "modify", connection["uuid"], "ipv6.method", "auto"]
    )
    run_cmd(["nmcli", "connection", "up", connection["uuid"]])
    return True
