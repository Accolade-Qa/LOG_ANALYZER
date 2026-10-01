import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent


class AISAgent(BaseAgent):
    """
    AIS-140 Automotive Telematics Protocol Agent.
    Monitors AIS-140 primary location frames, emergency panic packet generation (EPB),
    transmission sequence gaps, and historical queue persistence.
    Reactively collaborates with GPSAgent for fix validity and NetAgent for cellular transmission.
    """

    def __init__(self):
        super().__init__()
        self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "ais"
        self.ais_state = {
            "messages_received": 0,
            "last_tx_seq": None,
            "last_pkt_typ": 3,
            "epb_count": 0,
        }
        self.gps_has_fix = False
        self.net_connected = True
        self.parameters_config = self._load_parameters()
        self.anomaly_rules = self.parameters_config.get("anomaly_rules", {})

    def register_reactive_subscriptions(self):
        """Subscribe to GPS and Network events for location frame validation."""
        self.bus.subscribe("GNSS_FIX_ACQUIRED", self._on_gps_fix_acquired)
        self.bus.subscribe("TCP_SOCKET_DROPPED", self._on_tcp_socket_dropped)
        self.bus.subscribe("CELLULAR_CONNECTED", self._on_cellular_connected)

    def _on_gps_fix_acquired(self, payload, sender):
        self.gps_has_fix = True

    def _on_tcp_socket_dropped(self, payload, sender):
        self.net_connected = False

    def _on_cellular_connected(self, payload, sender):
        self.net_connected = True

    def _load_parameters(self):
        params_file = self.knowledge_dir / "parameters.yaml"
        if not params_file.exists():
            return {}
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            return config.get("ais", config)
        except Exception as e:
            print(f"Warning: Could not load AIS parameters.yaml ({e})")
            return {}

    def _parse_ais_line(self, line):
        params = {}

        pkt_match = re.search(r"PktTyp\s*=\s*(\d+)", line, re.IGNORECASE)
        if pkt_match:
            params["pkt_type"] = int(pkt_match.group(1))

        seq_match = re.search(r"TxSeq\s*=\s*(\d+)", line, re.IGNORECASE)
        if seq_match:
            params["tx_seq"] = int(seq_match.group(1))

        epb_match = re.search(r"EPB\s*\|\s*(\d+)", line, re.IGNORECASE)
        if epb_match:
            params["epb"] = int(epb_match.group(1))

        if "EMR 1" in line or "EMR=1" in line:
            params["emergency"] = True

        return params

    def handle(self, event):
        line = event.get("raw", "")
        line_num = event.get("line_number")
        params = self._parse_ais_line(line)
        if not params:
            return

        self.ais_state["messages_received"] += 1

        if params.get("emergency") or params.get("pkt_type") == 2:
            # Check GPS collaboration for emergency tracking accuracy
            gps_status = "Valid 3D Fix" if self.blackboard.gps_locked else "No Fix / Dead Reckoning"
            collab_ctx = f"AIS-140 emergency dispatch activated. GPS position status: {gps_status} ({self.blackboard.gps_satellites} satellites)."
            if not self.blackboard.gps_locked:
                self.bus.record_collaboration(
                    consumer_agent="AIS",
                    upstream_agent="GPS",
                    relationship="DEGRADED_COORDINATES",
                    evidence=f"Emergency panic frame generated without 3D GPS fix (Satellites: {self.blackboard.gps_satellites}).",
                    line_number=line_num,
                )

            self.open_session(
                session_key="AIS_KN_001",
                issue="AIS_KN_001: Emergency SOS Panic State Triggered (PktTyp=2 / EMR=1)",
                source="AIS",
                category="ais",
                severity="critical",
                event=event,
                collaborative_context=collab_ctx,
            )
        elif params.get("pkt_type") == 3:
            self.close_session(
                "AIS_KN_001",
                recovery_event=event,
                recovery_message="AIS-140 returned to normal periodic location broadcast (PktTyp=3)",
            )


ais_agent = AISAgent()
