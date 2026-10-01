import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent
from reports.anomaly_collector import collect


class MQTTAgent(BaseAgent):
    """
    MQTT Cloud Telemetry Analysis Agent.
    Monitors MQTT broker connection state, packet keep-alive latency, and payload drops.
    Reactively collaborates with NetAgent and SystemAgent.
    """

    def __init__(self):
        super().__init__()
        self.events_received = 0
        self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "mqtt"
        self.parameters = self._load_parameters()
        self.anomaly_rules = self.parameters.get("anomaly_rules", {})

    def register_reactive_subscriptions(self):
        """Subscribe to cellular network drops and system sleep."""
        self.bus.subscribe("CELLULAR_DISCONNECTED", self._on_net_drop)
        self.bus.subscribe("TCP_SOCKET_DROPPED", self._on_net_drop)
        self.bus.subscribe("SYSTEM_SLEEP_ENTER", self._on_system_sleep)

    def _on_net_drop(self, payload, sender):
        pass

    def _on_system_sleep(self, payload, sender):
        pass

    def _load_parameters(self):
        params_file = self.knowledge_dir / "parameters.yaml"
        if not params_file.exists():
            return {}
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _parse_mqtt_line(self, line):
        params = {}

        count_match = re.search(r"MQTT\s*[:=]\s*(\d+)", line, re.IGNORECASE)
        status_match = re.search(r"MQTT_STATUS\s*[:=]\s*(\w+)", line, re.IGNORECASE)
        latency_match = re.search(
            r"MQTT_LATENCY\s*[:=]\s*([\d.]+)", line, re.IGNORECASE
        )

        if count_match:
            params["message_count"] = int(count_match.group(1))

        if status_match:
            params["connection_status"] = status_match.group(1).lower()

        if latency_match:
            params["message_latency"] = float(latency_match.group(1))

        return params

    def _check_anomalies(self, params, event=None):
        status = params.get("connection_status")
        line_num = event.get("line_number") if event else None

        if status == "disconnected":
            rule = self.anomaly_rules.get("mqtt_disconnected", {})
            rule_id = rule.get("id", "MQTT_KN_001")

            # Cross-agent reactive evaluation
            if self.blackboard.is_vehicle_sleeping():
                causal_dep = "SystemAgent:SYS_KN_004"
                collab_ctx = "MQTT broker connection closed: Vehicle entered low-power sleep mode (IGN=0)."
                severity = "low"
            elif not self.blackboard.tcp_connected:
                self.bus.record_collaboration(
                    consumer_agent="MQTT",
                    upstream_agent="NET",
                    relationship="TRANSPORT_DROP",
                    evidence=f"MQTT broker disconnect at Line {line_num} directly follows cellular link drop.",
                    line_number=line_num,
                )
                causal_dep = "NetAgent:NET_KN_004"
                collab_ctx = "MQTT broker disconnect caused by cellular modem network detachment."
                severity = "medium"
            else:
                causal_dep = None
                collab_ctx = "Cloud broker connection failure while cellular connection is active."
                severity = "high"

            issue = f"{rule_id}: MQTT disconnected"
            if rule and rule.get("root_causes"):
                issue += f" - {', '.join(rule.get('root_causes', []))}"

            self.open_session(
                session_key="MQTT_KN_001",
                issue=issue,
                source="MQTT",
                category="mqtt",
                severity=severity,
                event=event,
                causal_dependency=causal_dep,
                collaborative_context=collab_ctx,
            )
        elif status == "connected":
            self.close_session(
                "MQTT_KN_001",
                recovery_event=event,
                recovery_message="MQTT reconnected to cloud broker",
            )

        latency = params.get("message_latency")
        if latency is not None and latency > 5000:
            rule = self.anomaly_rules.get("high_latency", {})
            issue = f"{rule.get('id', 'MQTT_KN_002')}: High MQTT latency ({latency} ms)"
            if rule and rule.get("root_causes"):
                issue += f" - {', '.join(rule.get('root_causes', []))}"
            self.add_anomaly(issue)
            collect(
                issue,
                source="MQTT",
                category="mqtt",
                severity="medium",
                event=event,
            )

    def handle(self, event):
        self.events_received += 1
        params = self._parse_mqtt_line(event["raw"])
        if not params:
            return

        self._check_anomalies(params, event)


mqtt_agent = MQTTAgent()
