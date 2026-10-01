import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent


class CANAgent(BaseAgent):
    """
    Automotive CAN Bus & UDS Diagnostic Subsystem Agent.
    Monitors ISO 14229 UDS timeouts, CAN bus error states, and DTC fault codes.
    Reactively synchronizes with SystemAgent and BatteryAgent to distinguish
    normal vehicle standby states from genuine CAN bus transceivers/wiring faults.
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
        line_num = event.get("line_number")
        params = self._parse_can_line(line)
        if not params:
            return

        self.can_state["messages_received"] += 1

        if params.get("uds_timeout"):
            rule = self.anomaly_rules.get("uds_session_timeout", {})
            rule_id = rule.get("id", "CAN_KN_001")
            
            # Collaborative cross-agent dependency check:
            # Did the vehicle enter sleep mode or is ignition OFF?
            is_sleeping = self.system_in_sleep or self.blackboard.is_vehicle_sleeping()
            if is_sleeping:
                # Collaborating with SystemAgent: UDS timeout is an expected reaction to vehicle sleep
                self.bus.record_collaboration(
                    consumer_agent="CAN",
                    upstream_agent="SYSTEM",
                    relationship="STANDBY_CASCADE",
                    evidence=f"UDS session timeout at Line {line_num} coincides with vehicle parked sleep mode (IGN=0).",
                    line_number=line_num,
                )
                causal_dep = "SystemAgent:SYS_KN_004"
                collab_ctx = (
                    f"Secondary cascade: SystemAgent confirmed vehicle entered low-power standby sleep "
                    f"(IGN=0 around Line {self.sleep_line or 2}). Vehicle ECU intentionally ceased CAN communication."
                )
                severity = "low"
                issue_text = f"{rule_id}: UDS Session Timeout (Expected Standby Cascade - Vehicle Sleeping)"
            elif self.battery_brownout or self.blackboard.is_battery_brownout:
                # Collaborating with BatteryAgent
                self.bus.record_collaboration(
                    consumer_agent="CAN",
                    upstream_agent="BATTERY",
                    relationship="POWER_SAG_CASCADE",
                    evidence=f"UDS session timeout at Line {line_num} triggered by main battery brownout sag.",
                    line_number=line_num,
                )
                causal_dep = "BatteryAgent:BATT_KN_001"
                collab_ctx = "Secondary cascade: BatteryAgent reported main rail voltage sag below operating threshold."
                severity = "high"
                issue_text = f"{rule_id}: UDS Session Timeout (Battery Brownout Induced)"
            else:
                causal_dep = None
                collab_ctx = "Primary fault: Vehicle is active with IGN=ON; ECU failed to respond over CAN bus."
                severity = "critical"
                issue_text = f"{rule_id}: UDS Session Timeout (Unexpected ECU Unresponsiveness)"

            self.open_session(
                session_key=rule_id,
                issue=issue_text,
                source="CAN",
                category="can",
                severity=severity,
                event=event,
                causal_dependency=causal_dep,
                collaborative_context=collab_ctx,
            )
        elif params.get("uds_active"):
            self.close_session(
                "CAN_KN_001",
                recovery_event=event,
                recovery_message="UDS communication established / active",
            )

        if params.get("dtc_code"):
            dtc = params["dtc_code"]
            self.blackboard.add_dtc(dtc)
            self.bus.publish("DTC_DETECTED", {"dtc_code": dtc, "line_number": line_num}, sender="CAN")

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
            self.bus.publish("CAN_BUS_OFF", {"line_number": line_num}, sender="CAN")
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
