import re
from pathlib import Path

import yaml  # type: ignore

from agents.base_agent import BaseAgent
from reports.anomaly_collector import collect


class MQTTAgent(BaseAgent):
    """MQTT telemetry analysis agent."""

    def __init__(self):
        super().__init__()
        self.events_received = 0
        self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "mqtt"
        self.parameters = self._load_parameters()
        self.anomaly_rules = self.parameters.get("anomaly_rules", {})

    def _load_parameters(self):
        params_file = self.knowledge_dir / "parameters.yaml"
        if not params_file.exists():
            return {}

        with open(params_file, "r") as f:
            return yaml.safe_load(f) or {}

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

    def _check_anomalies(self, params):
        if params.get("connection_status") == "disconnected":
            rule = self.anomaly_rules.get("mqtt_disconnected", {})
            issue = f"{rule.get('id', 'MQTT_KN_001')}: MQTT disconnected"
            if rule:
                issue += f" - {', '.join(rule.get('root_causes', []))}"
            self.add_anomaly(issue)
            collect(issue)

        latency = params.get("message_latency")
        if latency is not None and latency > 5000:
            rule = self.anomaly_rules.get("high_latency", {})
            issue = f"{rule.get('id', 'MQTT_KN_002')}: High MQTT latency ({latency} ms)"
            if rule:
                issue += f" - {', '.join(rule.get('root_causes', []))}"
            self.add_anomaly(issue)
            collect(issue)

    def handle(self, event):
        self.events_received += 1
        params = self._parse_mqtt_line(event["raw"])
        if not params:
            return

        self._check_anomalies(params)


mqtt_agent = MQTTAgent()
