import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent


class NetAgent(BaseAgent):
    """
    Automotive Cellular Network & Cloud MQTT Telemetry Agent.
    Monitors CSQ RF signal strength, CREG network registration, CGREG data attach,
    and MQTT broker connectivity.
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
            "last_mqtt": 1,
            "last_operator": "",
        }
        self.parameters_config = self._load_parameters()
        self.anomaly_rules = self.parameters_config.get("anomaly_rules", {})

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
        # [PLA] NET     CSQ 26, CREG: 2, CGREG: 2, TCP SKT: 000, MQTT: 0, OPR NM:
        csq_match = re.search(r"CSQ\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        creg_match = re.search(r"CREG\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        cgreg_match = re.search(r"CGREG\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        tcp_match = re.search(r"TCP\s+SKT\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        mqtt_match = re.search(r"MQTT\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        opr_match = re.search(r"OPR\s+NM\s*[:]?\s*(.*)$", line, re.IGNORECASE)

        if csq_match:
            params["csq"] = int(csq_match.group(1))
        if creg_match:
            params["creg"] = int(creg_match.group(1))
        if cgreg_match:
            params["cgreg"] = int(cgreg_match.group(1))
        if tcp_match:
            params["tcp_skt"] = int(tcp_match.group(1))
        if mqtt_match:
            params["mqtt"] = int(mqtt_match.group(1))
        if opr_match:
            params["operator"] = opr_match.group(1).strip()

        return params

    def handle(self, event):
        line = event.get("raw", "")
        params = self._parse_net_line(line)
        if not params:
            return

        self.net_state["messages_received"] += 1
        csq = params.get("csq")
        creg = params.get("creg")
        cgreg = params.get("cgreg")
        mqtt = params.get("mqtt")

        if csq is not None:
            self.net_state["last_csq"] = csq
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
            if creg in [0, 2, 3]:
                status_desc = {0: "Not registered", 2: "Searching", 3: "Registration denied"}.get(creg, str(creg))
                self.open_session(
                    session_key="NET_KN_002",
                    issue=f"NET_KN_002: Cellular network unattached (CREG={creg}: {status_desc})",
                    source="NET",
                    category="net",
                    severity="high",
                    event=event,
                )
            elif creg in [1, 5]:
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
                    severity="high",
                    event=event,
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
                self.open_session(
                    session_key="NET_KN_004",
                    issue="NET_KN_004: MQTT telemetry broker disconnected",
                    source="NET",
                    category="net",
                    severity="high",
                    event=event,
                )
            elif mqtt == 1:
                self.close_session(
                    "NET_KN_004",
                    recovery_event=event,
                    recovery_message="MQTT telemetry broker reconnected and authenticated",
                )


net_agent = NetAgent()
