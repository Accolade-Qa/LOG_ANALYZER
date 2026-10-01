import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent


class BatteryAgent(BaseAgent):
    """
    Automotive Battery & Power Subsystem Agent.
    Monitors 12V/24V external vehicle battery rails, backup Li-ion voltage,
    SoC percentage, and thermal parameters against YAML rules.
    Publishes real-time voltage sag & brownout warnings to CANAgent, GPSAgent, and SystemAgent.
    """

    def __init__(self):
        super().__init__()
        self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "battery"
        self.battery_state = {
            "messages_received": 0,
            "last_int_voltage": 3.8,
            "last_int_soc": 80.0,
            "last_ext_voltage": 12.0,
            "last_temperature": 25.0,
        }
        self.system_in_sleep = False
        self.parameters_config = self._load_parameters()
        self.anomaly_rules = self.parameters_config.get("anomaly_rules", {})

    def register_reactive_subscriptions(self):
        """Subscribe to system power states to verify sleep quiescent power."""
        self.bus.subscribe("SYSTEM_SLEEP_ENTER", self._on_system_sleep)
        self.bus.subscribe("SYSTEM_SLEEP_EXIT", self._on_system_wake)

    def _on_system_sleep(self, payload, sender):
        self.system_in_sleep = True

    def _on_system_wake(self, payload, sender):
        self.system_in_sleep = False

    def _load_parameters(self):
        params_file = self.knowledge_dir / "parameters.yaml"
        if not params_file.exists():
            return {}
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            return config.get("battery", config)
        except Exception as e:
            print(f"Warning: Could not load battery parameters.yaml ({e})")
            return {}

    def _parse_battery_line(self, line):
        params = {}

        # 1. ATCU NMEA Format: $ANALOG,<ext_batt>,<int_batt>,<tmpr>,<an1>,<an2>
        if "$ANALOG," in line:
            parts = line.split("$ANALOG,")[1].split(",")
            if len(parts) >= 3:
                try:
                    params["ext_voltage"] = float(parts[0].strip())
                    params["int_voltage"] = float(parts[1].strip())
                    params["temperature"] = float(parts[2].strip())
                    return params
                except (ValueError, IndexError):
                    pass

        # 2. Telematics Component Execution Format:
        int_match = re.search(r"INT\s+BATT\s+([\d.]+)V\s+([\d.]+)\s*PERCENT", line, re.IGNORECASE)
        if int_match:
            params["int_voltage"] = float(int_match.group(1))
            params["int_soc"] = float(int_match.group(2))
        else:
            int_v = re.search(r"INT\s+BATT\s+([\d.]+)V", line, re.IGNORECASE)
            if int_v:
                params["int_voltage"] = float(int_v.group(1))

        ext_match = re.search(r"EXT\s+BATT\s+([\d.]+)V", line, re.IGNORECASE)
        if ext_match:
            params["ext_voltage"] = float(ext_match.group(1))

        tmpr_match = re.search(r"TMPR\s+([\d.-]+)", line, re.IGNORECASE)
        if tmpr_match:
            params["temperature"] = float(tmpr_match.group(1))

        return params

    def _eval_condition(self, condition_str, context):
        if not condition_str:
            return False
        expr = condition_str.replace("AND", "and").replace("OR", "or")
        try:
            return bool(eval(expr, {}, context))
        except Exception:
            return False

    def _evaluate_yaml_rules(self, params, event):
        int_v = params.get("int_voltage", self.battery_state["last_int_voltage"])
        soc = params.get("int_soc", self.battery_state["last_int_soc"])
        ext_v = params.get("ext_voltage", self.battery_state["last_ext_voltage"])
        tmpr = params.get("temperature", self.battery_state["last_temperature"])
        line_num = event.get("line_number")

        context = {
            "INT_BATT": int_v,
            "SOC": soc,
            "EXT_BATT": ext_v,
            "TMPR": tmpr,
        }

        # Broadcast reactive notifications on voltage thresholds
        if ext_v is not None and ext_v < 9.0:
            self.bus.publish("BATTERY_BROWNOUT", {"voltage": ext_v, "line_number": line_num}, sender="BATTERY")
        elif ext_v is not None and ext_v < 11.5:
            self.bus.publish("BATTERY_VOLTAGE_LOW", {"voltage": ext_v, "line_number": line_num}, sender="BATTERY")

        for rule_key, rule_def in self.anomaly_rules.items():
            rule_id = rule_def.get("id", rule_key)
            condition_str = rule_def.get("condition")
            severity = rule_def.get("severity", "MEDIUM").lower()
            why = rule_def.get("why_it_happened", f"Rule {rule_id} triggered")

            if condition_str and self._eval_condition(condition_str, context):
                self.open_session(
                    session_key=rule_id,
                    issue=f"{rule_id}: {why}",
                    source="BATTERY",
                    category="battery",
                    severity=severity,
                    event=event,
                )

        # Dynamic Recovery Trigger
        if ext_v >= 11.5 and int_v >= 3.6:
            for rule_def in self.anomaly_rules.values():
                rule_id = rule_def.get("id")
                if rule_id in ["BATT_KN_001", "BATT_KN_003"]:
                    self.close_session(
                        rule_id,
                        recovery_event=event,
                        recovery_message=f"Battery rails healthy: EXT={ext_v}V, INT={int_v}V",
                    )

    def handle(self, event):
        line = event.get("raw", "")
        line_num = event.get("line_number")
        params = self._parse_battery_line(line)
        if not params:
            return

        self.battery_state["messages_received"] += 1

        if "int_voltage" in params:
            self.battery_state["last_int_voltage"] = params["int_voltage"]
        if "int_soc" in params:
            self.battery_state["last_int_soc"] = params["int_soc"]
        if "ext_voltage" in params:
            self.battery_state["last_ext_voltage"] = params["ext_voltage"]
        if "temperature" in params:
            self.battery_state["last_temperature"] = params["temperature"]

        self.blackboard.set_battery(
            ext_v=params.get("ext_voltage"),
            int_v=params.get("int_voltage"),
            line_number=line_num,
        )

        self._evaluate_yaml_rules(params, event)


battery_agent = BatteryAgent()
