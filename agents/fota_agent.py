import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent


class FOTAAgent(BaseAgent):
    """
    Automotive FOTA (Firmware Over-The-Air) & Parameter Configuration Subsystem Agent.
    Monitors remote TCP OTA commands, console OTA requests, FOTA transmission queues,
    download progress state machines, eMMC block writing, and CRC validation.
    Reactively collaborates with NetAgent, SystemAgent, and BatteryAgent.
    """

    def __init__(self):
        super().__init__()
        self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "fota"
        self.fota_state = {
            "messages_received": 0,
            "tcp_ota_requests": [],
            "console_ota_requests": [],
            "current_state": "idle",
            "queue_full_count": 0,
            "current_pct": 0.0,
            "current_offset": 0,
            "resumes": [],
        }
        self.last_tcp_drop_line = None
        self.battery_brownout = False
        self.system_in_sleep = False

        self.parameters_config = self._load_parameters()
        self.anomaly_rules = self.parameters_config.get("anomaly_rules", {})

    def register_reactive_subscriptions(self):
        """Subscribe to cellular transport, system power, and battery health."""
        self.bus.subscribe("TCP_SOCKET_DROPPED", self._on_tcp_socket_dropped)
        self.bus.subscribe("CELLULAR_DISCONNECTED", self._on_cellular_disconnected)
        self.bus.subscribe("BATTERY_BROWNOUT", self._on_battery_brownout)
        self.bus.subscribe("SYSTEM_SLEEP_ENTER", self._on_system_sleep)

    def _on_tcp_socket_dropped(self, payload, sender):
        self.last_tcp_drop_line = payload.get("line_number")

    def _on_cellular_disconnected(self, payload, sender):
        self.last_tcp_drop_line = payload.get("line_number")

    def _on_battery_brownout(self, payload, sender):
        self.battery_brownout = True

    def _on_system_sleep(self, payload, sender):
        self.system_in_sleep = True

    def _load_parameters(self):
        params_file = self.knowledge_dir / "parameters.yaml"
        if not params_file.exists():
            return {}
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            return config.get("fota", config)
        except Exception as e:
            print(f"Warning: Could not load FOTA parameters.yaml ({e})")
            return {}

    def _parse_fota_line(self, line):
        params = {}

        # 1. Match TCP OTA requests
        tcp_req = re.search(r"tcp\s+ota\s+request\s*[:=]\s*(.+)$", line, re.IGNORECASE)
        if tcp_req:
            params["tcp_ota_cmd"] = tcp_req.group(1).strip()

        # 2. Match Console OTA requests
        con_req = re.search(r"console\s+ota\s+request\s*[:=]\s*(.+)$", line, re.IGNORECASE)
        if con_req:
            params["console_ota_cmd"] = con_req.group(1).strip()

        # 3. Match FOTA queue overflow
        if "fota net queue is full" in line.lower():
            params["queue_full"] = True

        # 4. Match FOTA task state
        if "fota task is now active" in line.lower():
            params["task_state"] = "active"
        elif "fota task is now idle" in line.lower():
            params["task_state"] = "idle"

        # 5. Match FOTA progress
        dl_match = re.search(r"downloading\s+([\d.]+)%", line, re.IGNORECASE)
        if dl_match:
            params["downloading_pct"] = float(dl_match.group(1))

        off_match = re.search(r"offset\s*-\s*(\d+)", line, re.IGNORECASE)
        if off_match:
            params["offset"] = int(off_match.group(1))

        # 6. Match Resume
        res_match = re.search(r"Resume downloading from\s+([\d.]+)%,\s+Offset\s+(\d+)", line, re.IGNORECASE)
        if res_match:
            params["resume_pct"] = float(res_match.group(1))
            params["resume_offset"] = int(res_match.group(2))

        # 7. Match TCP disconnect
        if "got tcp disconnected" in line.lower():
            params["tcp_disconnected"] = True

        return params

    def handle(self, event):
        line = event.get("raw", "")
        line_num = event.get("line_number")
        params = self._parse_fota_line(line)
        if not params:
            return

        self.fota_state["messages_received"] += 1

        if "downloading_pct" in params:
            pct = params["downloading_pct"]
            self.fota_state["current_pct"] = pct
            off = params.get("offset", self.fota_state["current_offset"])
            self.fota_state["current_offset"] = off

            self.blackboard.set_fota(
                active=True,
                downloading=True,
                pct=pct,
                offset=off,
                line_number=line_num,
            )
            self.bus.publish(
                "FOTA_DOWNLOAD_ACTIVE",
                {"pct": pct, "offset": off, "line_number": line_num},
                sender="FOTA",
            )

        if "resume_pct" in params:
            rpct = params["resume_pct"]
            roff = params["resume_offset"]
            self.fota_state["resumes"].append({"pct": rpct, "offset": roff, "line": line_num})
            # Collaborating with NetAgent: Download resumed after link recovery
            self.bus.record_collaboration(
                consumer_agent="FOTA",
                upstream_agent="NET",
                relationship="CELLULAR_RECONNECT_RESUME",
                evidence=f"FOTA download session resumed at Line {line_num} from {rpct}% following cellular socket re-establishment.",
                line_number=line_num,
            )

        if "tcp_ota_cmd" in params:
            cmd = params["tcp_ota_cmd"]
            self.fota_state["tcp_ota_requests"].append({
                "cmd": cmd,
                "line": line_num,
                "raw": line.strip(),
            })

        if "console_ota_cmd" in params:
            cmd = params["console_ota_cmd"]
            self.fota_state["console_ota_requests"].append({
                "cmd": cmd,
                "line": line_num,
                "raw": line.strip(),
            })

        if params.get("queue_full"):
            self.fota_state["queue_full_count"] += 1
            rule = self.anomaly_rules.get("fota_queue_overflow", {})
            rule_id = rule.get("id", "FOTA_KN_001")

            # Check collaborative dependency on NetAgent
            if self.last_tcp_drop_line or not self.blackboard.tcp_connected:
                self.bus.record_collaboration(
                    consumer_agent="FOTA",
                    upstream_agent="NET",
                    relationship="TRANSPORT_CONGESTION",
                    evidence=f"FOTA packet dropped at Line {line_num} due to NetAgent cellular TCP socket closure/stall.",
                    line_number=line_num,
                )
                causal_dep = "NetAgent:NET_KN_004"
                collab_ctx = "Transport congestion: NetAgent reported cellular TCP socket closed or fragmented; outgoing FOTA packet dropped."
                severity = "medium"
            else:
                causal_dep = None
                collab_ctx = "RTOS task queue congestion: Telematics RTOS TCP transmit buffer depth exceeded."
                severity = "high"

            self.open_session(
                session_key="FOTA_KN_001",
                issue=f"{rule_id}: FOTA net queue full; outgoing packet dropped",
                source="FOTA",
                category="fota",
                severity=severity,
                event=event,
                causal_dependency=causal_dep,
                collaborative_context=collab_ctx,
            )

        if params.get("task_state"):
            self.fota_state["current_state"] = params["task_state"]


fota_agent = FOTAAgent()
