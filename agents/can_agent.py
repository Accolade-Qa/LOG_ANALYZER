import re

from agents.base_agent import BaseAgent
from reports.anomaly_collector import collect


class CANAgent(BaseAgent):
    """CAN telemetry analysis agent."""

    def __init__(self):
        super().__init__()
        self.events_received = 0

    def _parse_can_line(self, line):
        parsed = {}

        if "UDS Session Timeout" in line:
            parsed["uds_timeout"] = True

        dtc_match = re.search(r"DTC(?:_|\s*CODE)?\s*[:=]\s*0x([0-9A-Fa-f]+)", line)
        if dtc_match:
            parsed["dtc_code"] = dtc_match.group(1)

        status_match = re.search(r"DTC\s+STAT\s*[:,]?\s*(\d+)", line, re.IGNORECASE)
        if status_match:
            parsed["dtc_status"] = int(status_match.group(1))

        return parsed

    def _check_can_anomalies(self, parsed):
        if parsed.get("uds_timeout"):
            issue = "CAN_KN_001: UDS session timeout detected"
            self.add_anomaly(issue)
            collect(issue)

        if parsed.get("dtc_code"):
            code = parsed["dtc_code"]
            issue = f"CAN_KN_002: DTC reported (code=0x{code})"
            self.add_anomaly(issue)
            collect(issue)

    def handle(self, event):
        self.events_received += 1
        parsed = self._parse_can_line(event["raw"])
        if not parsed:
            return

        self._check_can_anomalies(parsed)


can_agent = CANAgent()
