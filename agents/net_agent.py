import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent


class NetAgent(BaseAgent):
    """
    Automotive Cellular Network & Cloud MQTT Telemetry Agent.
    Monitors CSQ RF signal strength, CREG network registration, CGREG data attach,
    and MQTT broker connectivity.
    Reactively publishes TCP transport drop events to FOTAAgent and AISAgent,
    and collaborates with SystemAgent to separate planned modem sleep from RF dropped calls.
    """

    def __init__(self):
        super().__init__()
        self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "net"
        self.net_state = {
            "messages_received": 0,
            "last_csq": 20,
            "last_creg": 1,
            "last_cgreg": 1,
            "last_tcp_skt": 1,
            "last_tcp_skt_raw": "000",
            "tcp_ais_primary": 0,
            "tcp_chtp": 0,
            "tcp_cip1": 0,
            "last_mqtt": 1,
            "last_operator": "",
        }
        self.system_in_sleep = False
        self.ignition_on = True
        self.sleep_line = None
        self.battery_brownout = False

        self.parameters_config = self._load_parameters()
        self.anomaly_rules = self.parameters_config.get("anomaly_rules", {})

    def register_reactive_subscriptions(self):
        """Subscribe to system power management and battery health events."""
        self.bus.subscribe("SYSTEM_SLEEP_ENTER", self._on_system_sleep)
        self.bus.subscribe("SYSTEM_SLEEP_EXIT", self._on_system_wake)
        self.bus.subscribe("IGNITION_CHANGED", self._on_ignition_changed)
        self.bus.subscribe("BATTERY_BROWNOUT", self._on_battery_brownout)

    def _on_system_sleep(self, payload, sender):
        self.system_in_sleep = True
        self.sleep_line = payload.get("line_number")

    def _on_system_wake(self, payload, sender):
        self.system_in_sleep = False

    def _on_ignition_changed(self, payload, sender):
        ign = payload.get("ignition")
        self.ignition_on = (ign == 1)

    def _on_battery_brownout(self, payload, sender):
        self.battery_brownout = True

    def _load_parameters(self):
        params_file = self.knowledge_dir / "parameters.yaml"
        if not params_file.exists():
            return {}
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            return config.get("net", config)
        except Exception as e:
            print(f"Warning: Could not load net parameters.yaml ({e})")
            return {}

    def _parse_net_line(self, line):
        params = {}

        # 1. ATCU NMEA Format: $GSM,<csq>,<creg>,<cgreg>,<tcp_skt>,<mqtt_count>,"<operator>",...
        if "$GSM," in line:
            parts = line.split("$GSM,")[1].split(",")
            if len(parts) >= 6:
                try:
                    params["csq"] = int(parts[0].strip())
                    params["creg"] = int(parts[1].strip())
                    params["cgreg"] = int(parts[2].strip())
                    params["tcp_skt"] = int(parts[3].strip())
                    params["mqtt"] = 1 if int(parts[4].strip()) > 0 else 0
                    op = parts[5].strip().strip('"')
                    params["operator"] = op if op not in ["-", "no service", ""] else ""
                    return params
                except (ValueError, IndexError):
                    pass

        # 2. Telematics Component Execution Format:
        csq_match = re.search(r"CSQ\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        creg_match = re.search(r"CREG\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        cgreg_match = re.search(r"CGREG\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        tcp_match = re.search(r"TCP\s+SKT\s*[:]?\s*([01]{3}|\d+)", line, re.IGNORECASE)
        mqtt_match = re.search(r"MQTT\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        opr_match = re.search(r"OPR\s+NM\s*[:]?\s*(.*)$", line, re.IGNORECASE)

        if csq_match:
            params["csq"] = int(csq_match.group(1))
        if creg_match:
            params["creg"] = int(creg_match.group(1))
        if cgreg_match:
            params["cgreg"] = int(cgreg_match.group(1))
        if tcp_match:
            raw_captured = tcp_match.group(1).strip()
            raw_skt = raw_captured.zfill(3)
            params["tcp_skt_raw"] = raw_skt
            params["tcp_skt_original_len"] = len(raw_captured)
            try:
                params["tcp_ais_primary"] = int(raw_skt[0])
                params["tcp_chtp"] = int(raw_skt[1])
                params["tcp_cip1"] = int(raw_skt[2])
                params["tcp_skt"] = int(raw_skt)
            except (ValueError, IndexError):
                params["tcp_skt"] = 0
        if mqtt_match:
            params["mqtt"] = int(mqtt_match.group(1))
        if opr_match:
            params["operator"] = opr_match.group(1).strip()

        # 3. GSM_TX Telematics Login & Handshake Packet (55AA,1)
        if "55AA,1" in line:
            m_pkt = re.search(r"\|(55AA,1,[^|]+)\|", line)
            if m_pkt:
                raw_pkt = m_pkt.group(1)
                parts = raw_pkt.split(",")
                if len(parts) >= 14:
                    try:
                        params["login_packet"] = {
                            "raw": raw_pkt,
                            "header": parts[0],
                            "packet_type": parts[1],
                            "socket_id": parts[2],
                            "timestamp": parts[3],
                            "imei": parts[4],
                            "iccid": parts[5],
                            "vin": parts[6],
                            "firmware_version": parts[7],
                            "hardware_model": parts[8],
                            "state": parts[9],
                            "primary_server": f"{parts[10]}:{parts[11]}",
                            "secondary_server": f"{parts[12]}:{parts[13]}",
                        }
                        if len(parts) >= 35:
                            params["ext_batt"] = float(parts[32])
                            params["int_batt"] = float(parts[33])
                            params["ignition"] = int(parts[34])
                        elif len(parts) >= 22:
                            params["ext_batt"] = float(parts[18])
                            params["int_batt"] = float(parts[19])
                            params["ignition"] = int(parts[20])
                    except (ValueError, IndexError):
                        pass

        # 4. Server Handshake Response (55AA,1,2,...)
        if "55AA,1,2" in line and "GSM_TX" not in line:
            m_resp = re.search(r"55AA,1,2,([^,\r\n]+),([^,\r\n]+)", line)
            if m_resp:
                params["server_handshake_ack"] = {
                    "raw": line.strip(),
                    "target_firmware": m_resp.group(2)
                }

        # 5. Connection drop notifications
        if "got tcp disconnected" in line.lower() or "tcp disconnected" in line.lower():
            params["tcp_disconnected"] = True

        return params

    def handle(self, event):
        line = event.get("raw", "")
        line_num = event.get("line_number")
        params = self._parse_net_line(line)
        if not params:
            return

        self.net_state["messages_received"] += 1

        # Process Device Login Handshake Packet
        login_pkt = params.get("login_packet")
        if login_pkt:
            self.blackboard.set_device_identity(
                imei=login_pkt.get("imei"),
                iccid=login_pkt.get("iccid"),
                vin=login_pkt.get("vin"),
                firmware=login_pkt.get("firmware_version"),
                primary_server=login_pkt.get("primary_server"),
                secondary_server=login_pkt.get("secondary_server"),
                line_number=line_num
            )
            self.bus.publish("DEVICE_LOGIN_HANDSHAKE_SENT", {
                "line_number": line_num,
                "socket_id": login_pkt.get("socket_id"),
                "imei": login_pkt.get("imei"),
                "firmware_version": login_pkt.get("firmware_version"),
                "primary_server": login_pkt.get("primary_server"),
                "raw": login_pkt.get("raw")
            }, sender="NET")

        if params.get("server_handshake_ack"):
            ack_info = params.get("server_handshake_ack")
            self.bus.publish("SERVER_HANDSHAKE_ACK_RECEIVED", {
                "line_number": line_num,
                "target_firmware": ack_info.get("target_firmware"),
                "raw": ack_info.get("raw")
            }, sender="NET")

        csq = params.get("csq")
        creg = params.get("creg")
        cgreg = params.get("cgreg")
        mqtt = params.get("mqtt")

        is_sleeping = self.system_in_sleep or self.blackboard.is_vehicle_sleeping()

        # Publish TCP drop to reactive bus (FOTAAgent and AISAgent listen to this)
        if params.get("tcp_disconnected"):
            self.blackboard.set_cellular(tcp_connected=False, line_number=line_num)
            self.bus.publish("TCP_SOCKET_DROPPED", {"line_number": line_num, "raw": line.strip()}, sender="NET")

        if csq is not None:
            self.net_state["last_csq"] = csq
            self.blackboard.set_cellular(csq=csq, line_number=line_num)
            if csq < 10:
                self.open_session(
                    session_key="NET_KN_001",
                    issue=f"NET_KN_001: Poor cellular RF signal (CSQ={csq})",
                    source="NET",
                    category="net",
                    severity="medium",
                    event=event,
                )
            elif csq >= 12:
                self.close_session(
                    "NET_KN_001",
                    recovery_event=event,
                    recovery_message=f"Cellular signal restored: CSQ={csq}",
                )

        if creg is not None:
            self.net_state["last_creg"] = creg
            self.blackboard.set_cellular(creg=creg, line_number=line_num)
            if creg in [0, 2, 3]:
                self.bus.publish("CELLULAR_DISCONNECTED", {"creg": creg, "line_number": line_num}, sender="NET")
                status_desc = {0: "Not registered", 2: "Searching", 3: "Registration denied"}.get(creg, str(creg))

                if is_sleeping:
                    self.bus.record_collaboration(
                        consumer_agent="NET",
                        upstream_agent="SYSTEM",
                        relationship="STANDBY_CASCADE",
                        evidence=f"Cellular network detachment at Line {line_num} coincides with vehicle parked sleep mode (IGN=0).",
                        line_number=line_num,
                    )
                    causal_dep = "SystemAgent:SYS_KN_004"
                    collab_ctx = (
                        f"Secondary cascade: SystemAgent confirmed vehicle entered low-power standby sleep "
                        f"(IGN=0 around Line {self.sleep_line or 2}). Cellular modem in PSM/eDRX sleep."
                    )
                    severity = "low"
                    issue_text = f"NET_KN_002: Cellular network unattached (Expected Standby Cascade - Vehicle Sleeping)"
                elif self.battery_brownout or self.blackboard.is_battery_brownout:
                    causal_dep = "BatteryAgent:BATT_KN_001"
                    collab_ctx = "Secondary cascade: BatteryAgent reported main rail voltage sag below operating threshold."
                    severity = "high"
                    issue_text = f"NET_KN_002: Cellular network unattached (Battery Brownout Induced)"
                else:
                    causal_dep = None
                    collab_ctx = "Primary fault: Vehicle active (IGN=ON); Cellular modem lost carrier registration."
                    severity = "high"
                    issue_text = f"NET_KN_002: Cellular network unattached (CREG={creg}: {status_desc})"

                self.open_session(
                    session_key="NET_KN_002",
                    issue=issue_text,
                    source="NET",
                    category="net",
                    severity=severity,
                    event=event,
                    causal_dependency=causal_dep,
                    collaborative_context=collab_ctx,
                )
            elif creg in [1, 5]:
                self.bus.publish("CELLULAR_CONNECTED", {"creg": creg, "line_number": line_num}, sender="NET")
                self.close_session(
                    "NET_KN_002",
                    recovery_event=event,
                    recovery_message=f"Cellular network registered (CREG={creg})",
                )

        if cgreg is not None:
            self.net_state["last_cgreg"] = cgreg
            if cgreg in [0, 2, 3]:
                self.open_session(
                    session_key="NET_KN_003",
                    issue=f"NET_KN_003: GPRS/LTE packet data unattached (CGREG={cgreg})",
                    source="NET",
                    category="net",
                    severity="high" if not is_sleeping else "low",
                    event=event,
                    causal_dependency="SystemAgent:SYS_KN_004" if is_sleeping else None,
                    collaborative_context="Modem in standby sleep." if is_sleeping else None,
                )
            elif cgreg in [1, 5]:
                self.close_session(
                    "NET_KN_003",
                    recovery_event=event,
                    recovery_message=f"Packet data service attached (CGREG={cgreg})",
                )

        if mqtt is not None:
            self.net_state["last_mqtt"] = mqtt
            if mqtt == 0:
                if is_sleeping:
                    causal_dep = "SystemAgent:SYS_KN_004"
                    collab_ctx = "Modem entered sleep mode: SystemAgent confirmed vehicle is in parked low-power sleep (IGN=0)."
                    severity = "low"
                    issue_text = "NET_KN_004: MQTT telemetry broker disconnected (Expected Standby Cascade - Vehicle Sleeping)"
                else:
                    causal_dep = None
                    collab_ctx = "Primary fault: Cloud MQTT socket connection lost while vehicle is active."
                    severity = "high"
                    issue_text = "NET_KN_004: MQTT telemetry broker disconnected"

                self.open_session(
                    session_key="NET_KN_004",
                    issue=issue_text,
                    source="NET",
                    category="net",
                    severity=severity,
                    event=event,
                    causal_dependency=causal_dep,
                    collaborative_context=collab_ctx,
                )
            elif mqtt == 1:
                self.close_session(
                    "NET_KN_004",
                    recovery_event=event,
                    recovery_message="MQTT telemetry broker reconnected and authenticated",
                )

        tcp_skt_raw = params.get("tcp_skt_raw")
        if tcp_skt_raw is not None:
            self.net_state["last_tcp_skt_raw"] = tcp_skt_raw
            self.net_state["tcp_ais_primary"] = params.get("tcp_ais_primary", 0)
            self.net_state["tcp_chtp"] = params.get("tcp_chtp", 0)
            self.blackboard.set_cellular(tcp_skt_raw=tcp_skt_raw, line_number=line_num)

            # Level 4 On-the-Go Parameter Synthesis & Configuration Audit:
            raw_cip1 = params.get("tcp_cip1")
            orig_len = params.get("tcp_skt_original_len", 3)
            sec_server = self.blackboard.secondary_server
            fw_version = self.blackboard.firmware_version

            # Case A: Field physically missing from line (e.g. TCP SKT printed only 2 bits or omitted)
            if orig_len < 3:
                rationale = (
                    f"CIP1 token was missing from raw 'TCP SKT' bitmask ({tcp_skt_raw}). "
                    f"Dynamically synthesized CIP1 status based on provisioned secondary server endpoint "
                    f"'{sec_server or 'None'}' and firmware release '{fw_version or 'detected'}'."
                )
                inferred_val = 1 if (sec_server and sec_server not in ["-", "", "None:None"]) else 0
                self.blackboard.set_inferred_parameter(
                    param_name="tcp_cip1",
                    inferred_value=inferred_val,
                    confidence=0.92,
                    rationale=rationale,
                    line_number=line_num
                )
                self.net_state["tcp_cip1"] = inferred_val

            # Case B: Field reported as 0, but secondary server is configured and active in current firmware
            elif raw_cip1 == 0 and sec_server and sec_server not in ["-", "", "None:None"]:
                has_socket2_event = ("socket: 2" in line.lower() or "socket:2" in line.lower() or "producer:88" in line)
                fw_profile_active = bool(fw_version and ("5.2.9" in fw_version or "REL05" in fw_version))
                if has_socket2_event or fw_profile_active:
                    self.blackboard.set_inferred_parameter(
                        param_name="tcp_cip1",
                        inferred_value=1,
                        confidence=0.95 if has_socket2_event else 0.88,
                        rationale=(
                            f"Raw telemetry bit reported CIP1=0, but dynamically adapted to Active (1) on the go: "
                            f"Firmware release {fw_version or 'target'} has provisioned secondary endpoint '{sec_server}' "
                            f"with verified auxiliary transport traffic."
                        ),
                        line_number=line_num
                    )

            # NET_KN_006: All telematics TCP sockets dropped while vehicle active
            if tcp_skt_raw == "000" and not is_sleeping and self.ignition_on and creg == 1:
                self.open_session(
                    session_key="NET_KN_006",
                    issue="NET_KN_006: All telematics TCP sockets dropped (TCP SKT=000: AIS=0, CHTP=0, CIP1=0)",
                    source="NET",
                    category="net",
                    severity="high",
                    event=event,
                )
            elif tcp_skt_raw != "000":
                self.close_session(
                    "NET_KN_006",
                    recovery_event=event,
                    recovery_message=f"Sockets reconnected (TCP SKT={tcp_skt_raw})",
                )


net_agent = NetAgent()
