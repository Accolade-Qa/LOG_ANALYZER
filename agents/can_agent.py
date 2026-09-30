import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent


class CANAgent(BaseAgent):
    """
    Automotive CAN Bus & UDS Diagnostic Subsystem Agent.
    Monitors ISO 14229 UDS timeouts, CAN bus error states, and DTC fault codes.
    """

    def __init__(self):
        super().__init__()
        self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "can"
        self.can_state = {
            "messages_received": 0,
            "uds_active": False,
            "uds_timeout": False,
            "last_dtc": None,
            "bus_state": 0,
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
            return config.get("can", config)
        except Exception as e:
            print(f"Warning: Could not load CAN parameters.yaml ({e})")
            return {}

    def _parse_can_line(self, line):
        params = {}

        if "UDS Session Timeout" in line or "UDS Timeout" in line:
            params["uds_timeout"] = True

        if "UDS Session Active" in line or "UDS Connected" in line or "UDS RX" in line:
            params["uds_active"] = True

        dtc_match = re.search(r"DTC(?:_|\s*CODE)?\s*[:=]\s*0x?([0-9A-Fa-f]+)", line)
        if dtc_match:
            params["dtc_code"] = dtc_match.group(1).upper()

        if "$CAN2," in line:
            parts = line.split("$CAN2,")[1].split(",")
            if len(parts) >= 2:
                try:
                    params["bus_state"] = int(parts[0].strip())
                    params["error_flag"] = int(parts[1].strip())
                except (ValueError, IndexError):
                    pass

        bus_off_match = re.search(r"CAN\s+(?:Bus\s*Off|Controller\s*Off|Error\s*Passive)", line, re.IGNORECASE)
        if bus_off_match:
            params["bus_state"] = 2

        return params

    def handle(self, event):
        line = event.get("raw", "")
        params = self._parse_can_line(line)
        if not params:
            return

        self.can_state["messages_received"] += 1

        if params.get("uds_timeout"):
            rule = self.anomaly_rules.get("uds_session_timeout", {})
            rule_id = rule.get("id", "CAN_KN_001")
            why = rule.get("why_it_happened", "UDS session timed out waiting for ECU response.")
            self.open_session(
                session_key=rule_id,
                issue=f"{rule_id}: {why}",
                source="CAN",
                category="can",
                severity="high",
                event=event,
            )
        elif params.get("uds_active"):
            self.close_session(
                "CAN_KN_001",
                recovery_event=event,
                recovery_message="UDS communication established / active",
            )

        if params.get("dtc_code"):
            dtc = params["dtc_code"]
            rule = self.anomaly_rules.get("diagnostic_trouble_code_active", {})
            rule_id = rule.get("id", "CAN_KN_002")
            why = rule.get("why_it_happened", f"DTC Fault Code 0x{dtc} logged by ECU.")
            self.open_session(
                session_key=f"CAN_DTC_{dtc}",
                issue=f"{rule_id}: Active DTC 0x{dtc} - {why}",
                source="CAN",
                category="can",
                severity="critical",
                event=event,
            )

        if params.get("bus_state") == 2:
            rule = self.anomaly_rules.get("can_bus_off", {})
            rule_id = rule.get("id", "CAN_KN_003")
            why = rule.get("why_it_happened", "CAN controller entered Bus-Off state due to Tx/Rx error count.")
            self.open_session(
                session_key=rule_id,
                issue=f"{rule_id}: {why}",
                source="CAN",
                category="can",
                severity="critical",
                event=event,
            )
        elif params.get("bus_state") == 0:
            self.close_session(
                "CAN_KN_003",
                recovery_event=event,
                recovery_message="CAN bus returned to Error-Active healthy state",
            )


can_agent = CANAgent()
