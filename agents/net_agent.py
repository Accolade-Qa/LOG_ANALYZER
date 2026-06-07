import re

from agents.base_agent import BaseAgent
from reports.anomaly_collector import collect


class NetAgent(BaseAgent):
    """Network telemetry analysis agent."""

    def __init__(self):
        super().__init__()
        self.events_received = 0

    def _parse_net_line(self, line):
        parsed = {}

        csq_match = re.search(r"CSQ\s*(\d+)", line, re.IGNORECASE)
        creg_match = re.search(r"CREG\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        cgreg_match = re.search(r"CGREG\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        tcp_match = re.search(r"TCP\s+SKT\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        mqtt_match = re.search(r"MQTT\s*[:]?\s*(\d+)", line, re.IGNORECASE)
        opr_match = re.search(r"OPR\s+NM\s*[:]?\s*(.*)$", line, re.IGNORECASE)

        if csq_match:
            parsed["csq"] = int(csq_match.group(1))
        if creg_match:
            parsed["creg"] = int(creg_match.group(1))
        if cgreg_match:
            parsed["cgreg"] = int(cgreg_match.group(1))
        if tcp_match:
            parsed["tcp_skt"] = int(tcp_match.group(1))
        if mqtt_match:
            parsed["mqtt_count"] = int(mqtt_match.group(1))
        if opr_match:
            parsed["operator"] = opr_match.group(1).strip()

        return parsed

    def _check_net_anomalies(self, parsed):
        if parsed.get("csq") is not None and parsed["csq"] < 5:
            issue = f"NET_KN_001: Poor signal quality (CSQ={parsed['csq']})"
            self.add_anomaly(issue)
            collect(issue)

        if parsed.get("creg") == 0:
            issue = "NET_KN_002: GSM registration failed (CREG=0)"
            self.add_anomaly(issue)
            collect(issue)

        if parsed.get("cgreg") == 0:
            issue = "NET_KN_003: GPRS registration failed (CGREG=0)"
            self.add_anomaly(issue)
            collect(issue)

        operator = parsed.get("operator")
        if operator == "" or operator is None:
            issue = "NET_KN_004: Operator name missing"
            self.add_anomaly(issue)
            collect(issue)

        if parsed.get("tcp_skt") == 0 and parsed.get("mqtt_count") == 0:
            issue = "NET_KN_005: No active TCP socket or MQTT traffic"
            self.add_anomaly(issue)
            collect(issue)

    def handle(self, event):
        self.events_received += 1
        parsed = self._parse_net_line(event["raw"])
        if not parsed:
            return

        self._check_net_anomalies(parsed)


net_agent = NetAgent()
