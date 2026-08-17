import {
  PanelSection,
  PanelSectionRow,
  staticClasses,
  ToggleField,
  Field,
} from "@decky/ui";

import { callable, definePlugin, toaster } from "@decky/api";

import { FC, useCallback, useEffect, useRef, useState } from "react";

import { BsShieldLock } from "react-icons/bs";

type Connection = {
  name: string;
  uuid: string;
  type: string;
  connected: boolean;
  ipv6_disabled?: boolean;
};

interface PluginResponse {
  success: boolean;
  data: string;
}

interface InterfaceResponse extends PluginResponse {
  ip: string;
}

interface NetworkResponse extends PluginResponse {
  gateway_ping: boolean;
}

const show = callable<[], Connection[]>("show");
const up = callable<[uuid: string], void>("up");
const down = callable<[uuid: string], void>("down");
const getActiveConnection = callable<[], Connection>("active_connection");
const resetCachedData = callable<[], boolean>("reset_cached_data");
const disableIpv6 = callable<[], void>("disable_ipv6");
const enableIpv6 = callable<[], void>("enable_ipv6");
const getPriorityInterface = callable<[], InterfaceResponse>(
  "get_priority_interface",
);
const isInternetAvailable = callable<[], boolean>("is_internet_available");
const getPrioritizedNetworkInfo = callable<[], NetworkResponse>(
  "get_prioritized_network_info",
);

const Content: FC = () => {
  const [loaded, setLoaded] = useState(false);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [priorityInterface, setPriorityInterface] = useState("N/A");
  const [priorityInterfaceLanIp, setPriorityInterfaceLanIp] = useState("N/A");
  const [canReachGateway, setCanReachGateway] = useState("N/A");
  const [canReachSteam, setCanReachSteam] = useState("N/A");
  const [priorityNetworkInfo, setPriorityNetworkInfo] = useState(["N/A"]);
  const [activeConnection, setActiveConnection] = useState<Connection>();
  const [ipv6Disabled, setIpv6Disabled] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(true);

  const isRefreshingRef = useRef(false);
  const timerRef = useRef<number | undefined>(undefined);
  const mountedRef = useRef(true);

  const collectNetworkInfo = () => {
    setIsRefreshing(true);
    clearTimeout(timerRef.current);
    schedulePoll(1000);
  };

  const tryCatchHandler = async <T,>(
    name: string,
    func: () => Promise<T>,
    defaultRes: T,
  ): Promise<T> => {
    try {
      return await func();
    } catch (e) {
      handleError(`Error handling function ${name}`, e);
      return defaultRes;
    }
  };

  const setRefreshState = () => {
    clearTimeout(timerRef.current);
    setIsRefreshing(true);
    setPriorityInterface("N/A");
    setPriorityInterfaceLanIp("N/A");
    setCanReachSteam("N/A");
    setCanReachGateway("N/A");
    setPriorityNetworkInfo(["N/A"]);
  };

  const getInterfaceData = async () => {
    isRefreshingRef.current = true;
    setIsRefreshing(true);
    console.debug("TunnelDeck - Collecting interface data");
    try {
      await tryCatchHandler(
        "reset_cached_data",
        () => resetCachedData(),
        false,
      );

      const pPriorityInterfaceLaneIp = tryCatchHandler<InterfaceResponse>(
        "get_priority_interface",
        () => getPriorityInterface(),
        { success: false, data: "N/A", ip: "N/A" },
      ).then((interfaceResponse) => {
        setPriorityInterfaceLanIp(
          interfaceResponse.success ? interfaceResponse.ip : "N/A",
        );
        setPriorityInterface(
          interfaceResponse.success ? interfaceResponse.data : "N/A",
        );
      });

      const pIsSteamAvailable = tryCatchHandler(
        "is_internet_available",
        () => isInternetAvailable(),
        false,
      ).then((steamAvailable) => {
        setCanReachSteam(steamAvailable ? "Yes" : "No");
      });

      const pPriorityNetworkInfo = tryCatchHandler<NetworkResponse>(
        "get_prioritized_network_info",
        () => getPrioritizedNetworkInfo(),
        { success: false, data: "N/A", gateway_ping: false },
      ).then((networkResponse) => {
        setPriorityNetworkInfo(
          networkResponse.success ? networkResponse.data.split("\n") : ["N/A"],
        );
        setCanReachGateway(
          networkResponse.success && networkResponse.gateway_ping
            ? "Yes"
            : "No",
        );
      });

      await Promise.all([
        pIsSteamAvailable,
        pPriorityInterfaceLaneIp,
        pPriorityNetworkInfo,
      ]);
    } catch (e) {
      handleError("Error refreshing interface data", e);
    } finally {
      console.debug("TunnelDeck - Finished refreshing");
      isRefreshingRef.current = false;
      setIsRefreshing(false);
    }
  };

  const schedulePoll = useCallback(
    (delay = 5000) => {
      clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(async () => {
        if (!mountedRef.current) return;
        if (isRefreshingRef.current) return schedulePoll(); // busy → retry, reads LIVE value
        await getInterfaceData();
        if (mountedRef.current) schedulePoll();
      }, delay);
    },
    [getInterfaceData],
  );

  const loadConnections = async () => {
    try {
      const activeConn = await getActiveConnection();
      if (activeConn) {
        setActiveConnection(activeConn);
        setIpv6Disabled(!!activeConn.ipv6_disabled);
      } else {
        setActiveConnection(undefined);
        setIpv6Disabled(false);
      }
    } catch (error) {
      handleError("Failed to get active connection", error);
    }

    try {
      const connections = await show();
      const filtered = connections
        .filter((connection) => ["vpn", "wireguard"].includes(connection.type))
        .sort((a, b) => {
          if (a.name < b.name) return -1;
          if (a.name > b.name) return 1;
          return 0;
        });

      setConnections(filtered);
    } catch (error) {
      handleError("Failed to get connections", error);
    }

    setLoaded(true);
    collectNetworkInfo();
  };

  const toggleConnection = async (
    connection: Connection,
    switchValue: boolean,
  ) => {
    setRefreshState();
    try {
      if (switchValue) {
        await up(connection.uuid);
      } else {
        await down(connection.uuid);
      }

      setConnections((prev) =>
        prev.map((c) =>
          c.uuid === connection.uuid ? { ...c, connected: switchValue } : c,
        ),
      );

      toaster.toast({
        title: `Connection ${switchValue ? "enabled" : "disabled"}`,
        body: `${connection.name} has been ${
          switchValue ? "enabled" : "disabled"
        }`,
      });
    } catch (error) {
      handleError("Connection toggle failed", error);
      await loadConnections();
    } finally {
      collectNetworkInfo();
    }
  };

  const toggleIpv6 = async (switchValue: boolean) => {
    setIpv6Disabled(switchValue);
    setRefreshState();
    try {
      if (switchValue) {
        await disableIpv6();
      } else {
        await enableIpv6();
      }
    } catch (e) {
      handleError("Failed to toggle IPV6", e);
    } finally {
      collectNetworkInfo();
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    loadConnections();
    return () => {
      mountedRef.current = false;
      clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <>
      <PanelSection title="Connections">
        {loaded && connections.length === 0 && (
          <PanelSectionRow>No Connections Found</PanelSectionRow>
        )}

        {connections.length > 0 &&
          connections.map((connection) => (
            <PanelSectionRow key={connection.uuid}>
              <ToggleField
                bottomSeparator="standard"
                checked={connection.connected}
                label={connection.name}
                description={`Type: ${connection.type}`}
                onChange={(switchValue: boolean) => {
                  toggleConnection(connection, switchValue);
                }}
              />
            </PanelSectionRow>
          ))}
      </PanelSection>

      <PanelSection title="Network Info" spinner={isRefreshing}>
        <PanelSectionRow>
          <Field
            label="Prioritized Network Interface"
            description={priorityInterface}
            focusable={true}
          ></Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field
            label="Prioritized Interface LAN IP"
            description={priorityInterfaceLanIp}
            focusable={true}
          ></Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field
            label="Can reach gateway"
            description={canReachGateway}
            focusable={true}
          ></Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field
            label="Can reach steampowered.com"
            description={canReachSteam}
            focusable={true}
          ></Field>
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="Settings">
        <PanelSectionRow>
          <ToggleField
            bottomSeparator="standard"
            checked={ipv6Disabled}
            label="Disable IPV6"
            disabled={!activeConnection || !loaded}
            description="Disables IPV6 support for the current connection. Required for some VPNs."
            onChange={toggleIpv6}
          />
        </PanelSectionRow>
      </PanelSection>
      <PanelSection title="Additional network info" spinner={isRefreshing}>
        {loaded && priorityNetworkInfo.length === 0 && (
          <PanelSectionRow>No Network Info found</PanelSectionRow>
        )}

        {priorityNetworkInfo.length > 0 &&
          priorityNetworkInfo.map((infoItem, index) => (
            <PanelSectionRow key={`${infoItem}-${index}`}>
              <Field description={infoItem} focusable={true} padding={"none"} />
            </PanelSectionRow>
          ))}
      </PanelSection>
    </>
  );
};

function handleError(title: string, error: unknown) {
  console.error(title, error);
  toaster.toast({
    title: title,
    body: error instanceof Error ? error.message : "Unknown error",
  });
}

export default definePlugin(() => {
  return {
    name: "TunnelDeck",
    titleView: <div className={staticClasses.Title}>TunnelDeck</div>,
    content: <Content />,
    icon: <BsShieldLock />,
  };
});
