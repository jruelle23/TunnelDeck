import {
  PanelSection,
  PanelSectionRow,
  staticClasses,
  ToggleField,
  ButtonItem,
  Navigation,
  Field
} from "@decky/ui";

import { callable, definePlugin } from "@decky/api";

import {
  FC,
  useEffect,
  useState
} from "react";

import { FaShieldAlt } from "react-icons/fa";

type Connection = {
  name: string,
  uuid: string,
  type: string,
  connected: boolean,
  ipv6_disabled?: boolean
}

interface PluginResponse {
  success: boolean,
  data: string,
}

interface InterfaceResponse extends PluginResponse {
  ip: string,
}

interface NetworkResponse extends PluginResponse {
  gateway_ping: boolean,
}

const show = callable<[], Connection[]>("show");
const up = callable<[uuid: string], void>("up");
const down = callable<[uuid: string], void>("down");
const getActiveConnection = callable<[], Connection>("active_connection");
const resetCachedData = callable<[], boolean>("reset_cached_data");
const disableIpv6 = callable<[], void>("disable_ipv6");
const enableIpv6 = callable<[], void>("enable_ipv6");
const isOpenvpnPacmanInstalled = callable<[], boolean>("is_openvpn_pacman_installed");
const isOpenvpnEnabled = callable<[], boolean>("is_openvpn_enabled");
const enableOpenvpn = callable<[], void>("enable_openvpn");
const disableOpenvpn = callable<[], void>("disable_openvpn");
const getPriorityInterface = callable<[], InterfaceResponse>("get_priority_interface");
const isInternetAvailable = callable<[], boolean>("is_internet_available");
const getPrioritizedNetworkInfo = callable<[], NetworkResponse>("get_prioritized_network_info");


let interfaceCheckerId: number;
// For some reason, setting setIsRefreshing doesn't update the code side of the understanding.
// So have to make my own variable that does the exact same thing... lol...
let isActuallyRefreshing = true;
const Content: FC = () => {

  const [ loaded, setLoaded ] = useState(false);
  const [ connections, setConnections ] = useState<Connection[]>([]);
  const [ priorityInterface, setPriorityInterface ] = useState('N/A');
  const [ priorityInterfaceLanIp, setPriorityInterfaceLanIp ] = useState('N/A');
  const [ canReachGateway, setCanReachGateway ] = useState('N/A');
  const [ canReachSteam, setCanReachSteam ] = useState('N/A');
  const [ priorityNetworkInfo, setPriorityNetworkInfo ] = useState(['N/A']);
  const [ activeConnection, setActiveConnection ] = useState<Connection>();
  const [ ipv6Disabled, setIpv6Disabled ] = useState(false);
  const [ openVPNEnabled, setOpenVPNEnabled ] = useState(false);
  const [ openVPNDisabled, setOpenVPNDisabled ] = useState(false);
  const [ isRefreshing, setIsRefreshing ] = useState(true); // This is always true on the code-side... idk why.


  const interfaceChecker = () => {
    clearTimeout(interfaceCheckerId);
    interfaceCheckerId = window.setTimeout(() => {
      if (isActuallyRefreshing) {
        return interfaceChecker();
      }

      getInterfaceData().finally(interfaceChecker);
    }, 5000);
  }

  const collectNetworkInfo = () => {
    if (isActuallyRefreshing && loaded) {
      return;
    }
    isActuallyRefreshing = true;

    clearTimeout(interfaceCheckerId);
    window.setTimeout(() => {
      getInterfaceData().finally(interfaceChecker);
    }, 1000);
  }

  const tryCatchHandler = async <T,>(name: string, func: () => Promise<T>, defaultRes: T): Promise<T> => {
    try {
      return await func();
    } catch (e) {
      console.error('Error handling function', name);
      return defaultRes;
    }
  }

  const setRefreshState = () => {
    clearTimeout(interfaceCheckerId);
    setIsRefreshing(true);
    setPriorityInterface('N/A');
    setPriorityInterfaceLanIp('N/A');
    setCanReachSteam('N/A');
    setCanReachGateway('N/A');
    setPriorityNetworkInfo(['N/A']);
  }

  const getInterfaceData = async () => {
    setIsRefreshing(true);
    isActuallyRefreshing = true;
    console.log('TunnelDeck - Collecting interface data');
    try {


    await tryCatchHandler('reset_cached_data', () => resetCachedData(), false)

    const pPriorityInterfaceLaneIp = tryCatchHandler<InterfaceResponse>('get_priority_interface', () => getPriorityInterface(), {success:false, data: 'N/A', ip: 'N/A'})
        .then((interfaceResponse) => {
          setPriorityInterfaceLanIp(interfaceResponse.success ? interfaceResponse.ip : 'N/A');
          setPriorityInterface(interfaceResponse.success ? interfaceResponse.data : 'N/A');
        });

    const pIsSteamAvailable = tryCatchHandler('is_internet_available', () => isInternetAvailable(), false)
        .then((steamAvailable)  => {
          setCanReachSteam(steamAvailable ? 'Yes' : 'No');
        });

    const pPriorityNetworkInfo = tryCatchHandler<NetworkResponse>('get_prioritized_network_info', () => getPrioritizedNetworkInfo(), {success:false, data: 'N/A', gateway_ping: false})
        .then((networkResponse) => {
          setPriorityNetworkInfo(networkResponse.success ? networkResponse.data.split('\n') : ['N/A']);
          setCanReachGateway(networkResponse.success && networkResponse.gateway_ping ? 'Yes' : 'No');
        });


    await Promise.all([pIsSteamAvailable, pPriorityInterfaceLaneIp, pPriorityNetworkInfo])
    } catch (e) {
      console.error('TunnelDeck - Error: ', e);
    } finally {
      console.log('TunnelDeck - Finished refreshing');
      setIsRefreshing(false);
      isActuallyRefreshing = false;
    }
  }

  const loadConnections = async () => {
    try {
      const activeConn = await getActiveConnection();
      setActiveConnection(activeConn);
      setIpv6Disabled(!!(activeConn.ipv6_disabled));
    } catch (error) {
      console.error(error);
    }

    try {
      const openVPNDisabledState = await isOpenvpnPacmanInstalled();
      setOpenVPNDisabled(openVPNDisabledState);
    } catch (error) {
      console.error(error);
    }

    if(!openVPNDisabled) {
      try {
        setOpenVPNEnabled(await isOpenvpnEnabled());
      } catch (error) {
        console.error(error);
      }
    }

    try {
      const connections = await show();
      const filtered = connections
      .filter((connection) => ['vpn', 'wireguard'].includes(connection.type))
      .sort((a, b) => {
        if(a.name < b.name) return -1;
        if(a.name > b.name) return 1;
        return 0;
      });

      setConnections(filtered);
    } catch (error) {
      console.error(error);
    }

    setLoaded(true);
    collectNetworkInfo();
  }

  const toggleConnection = async (connection: Connection, switchValue: boolean) => {
    setRefreshState();
    if (switchValue) {
      await up(connection.uuid);
    } else {
      await down(connection.uuid);
    }
    collectNetworkInfo();
  }

  const toggleIpv6 = async(switchValue: boolean) => {
    setIpv6Disabled(switchValue);
    setRefreshState();
    if (switchValue) {
      await disableIpv6();
    } else {
      await enableIpv6();
    }
    collectNetworkInfo();
  }

  const toggleOpenVPN = async(switchValue: boolean) => {
    setOpenVPNEnabled(switchValue);
    setRefreshState();
    if (switchValue) {
      await enableOpenvpn();
    } else {
      await disableOpenvpn();
    }
    collectNetworkInfo();
  }

  useEffect(() => {
    loadConnections();
    return () => {
      clearTimeout(interfaceCheckerId);
    }
  }, []);

  return (
    <>
      <PanelSection title="Connections">

        {loaded && connections.length == 0 && <PanelSectionRow>
          No Connections Found
        </PanelSectionRow>}

        {connections.length > 0 && connections.map((connection) => (
          <PanelSectionRow>
            <ToggleField
            bottomSeparator='standard'
            checked={connection.connected}
            label={connection.name}
            description={`Type: ${connection.type}`}
            onChange={(switchValue: boolean) => {
              toggleConnection(connection, switchValue);
            }} />
          </PanelSectionRow>
        ))}

        <PanelSectionRow>
          <ButtonItem onClick={() => {
            Navigation.NavigateToExternalWeb('https://github.com/bkohler616/TunnelDeck#readme');
            Navigation.CloseSideMenus();
          }}>
            How Do I Add Connections?
          </ButtonItem>
        </PanelSectionRow>

      </PanelSection>

      <PanelSection title="Network Info" spinner={isRefreshing}>
        <PanelSectionRow>
          <Field
            label='Prioritized Network Interface'
            description={priorityInterface}
            focusable={true}>
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field
              label='Prioritized Interface LAN IP'
              description={priorityInterfaceLanIp}
              focusable={true}>
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field
              label='Can reach gateway'
              description={canReachGateway}
              focusable={true}>
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field
              label='Can reach steampowered.com'
              description={canReachSteam}
              focusable={true}>
          </Field>
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="Settings">
        <PanelSectionRow>
          <ToggleField
          bottomSeparator='standard'
          checked={openVPNEnabled || openVPNDisabled}
          label='Enable OpenVPN'
          disabled={!loaded || openVPNDisabled}
          description='Installs OpenVPN support for Network Manager'
          onChange={toggleOpenVPN} />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
          bottomSeparator='standard'
          checked={ipv6Disabled}
          label='Disable IPV6'
          disabled={!activeConnection || !loaded}
          description='Disables IPV6 support for the current connection. Required for some VPNs.'
          onChange={toggleIpv6} />
        </PanelSectionRow>
      </PanelSection>
      <PanelSection title="Additional network info" spinner={isRefreshing}>

        {loaded && priorityNetworkInfo.length == 0 && <PanelSectionRow>
          No Network Info found
        </PanelSectionRow>}

        {priorityNetworkInfo.length > 0 && priorityNetworkInfo.map((infoItem) => (
            <PanelSectionRow>
              <Field
                  description={infoItem}
                  focusable={true}
                  padding={"none"}/>
            </PanelSectionRow>
        ))}
      </PanelSection>
    </>
  );
};

export default definePlugin(() => {
  return {
    name: "TunnelDeck",
    titleView: <div className={staticClasses.Title}>TunnelDeck</div>,
    content: <Content />,
    icon: <FaShieldAlt />,
    onDismount() {
      clearTimeout(interfaceCheckerId);
    },
  };
});
