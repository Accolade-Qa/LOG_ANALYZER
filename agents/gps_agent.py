import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent


class GPSAgent(BaseAgent):
    """
    Automotive GPS & GNSS Positioning Telemetry Agent.
    Monitors satellite acquisition, fix quality, coordinates, and speed.
    Reactively collaborates with SystemAgent and BatteryAgent to separate
    intentional RF receiver sleep shutdowns from true coaxial antenna faults.
    """

    def __init__(self):
        super().__init__()
        self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "gps"
        self.gps_state = {
            "messages_received": 0,
            "last_fix_quality": 0,
            "last_satellite_count": 0,
            "last_lat": 0.0,
            "last_long": 0.0,
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
            return config.get("gps", config)
        except Exception as e:
            print(f"Warning: Could not load GPS parameters.yaml ({e})")
            return {}

    def _parse_gps_line(self, line):
        params = {}

        # 1. Format: $GPS,1,1,19.1234,72.9876,8 ...
        if "$GPS," in line:
            parts = line.split("$GPS,")[1].split(",")
            if len(parts) >= 6:
                try:
                    params["fix_quality"] = int(parts[2].strip())
                    params["latitude"] = float(parts[3].strip())
                    params["longitude"] = float(parts[4].strip())
                    params["satellite_count"] = int(parts[5].strip().split()[0])
                    return params
                except (ValueError, IndexError):
                    pass

        # 2. Log format: LAT 0.0, LONG 0.0, FIX QUA 0, SAT 0
        key_patterns = {
            "fix_quality": r"FIX\s+QUA\s+([\d]+)",
            "satellite_count": r"SAT\s+([\d]+)",
            "latitude": r"LAT\s+([\-\d.]+)",
            "longitude": r"LONG\s+([\-\d.]+)",
            "speed_kmph": r"SPEED_KMPH\s+([\-\d.]+)",
            "altitude": r"ALT\s+([\-\d.]+)",
            "hdop": r"HDOP\s+([\-\d.]+)",
        }

        for key, pattern in key_patterns.items():
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                try:
                    val = match.group(1)
                    params[key] = int(val) if key in ["fix_quality", "satellite_count"] else float(val)
                except ValueError:
                    pass

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
        sat = params.get("satellite_count", self.gps_state["last_satellite_count"])
        fix = params.get("fix_quality", self.gps_state["last_fix_quality"])
        lat = params.get("latitude", self.gps_state["last_lat"])
        long = params.get("longitude", self.gps_state["last_long"])
        line_num = event.get("line_number")

        context = {
            "SAT": sat,
            "FIX_QUA": fix,
            "LAT": lat,
            "LONG": long,
        }

        is_sleeping = self.system_in_sleep or self.blackboard.is_vehicle_sleeping()

        for rule_key, rule_def in self.anomaly_rules.items():
            rule_id = rule_def.get("id", rule_key)
            condition_str = rule_def.get("condition")
            why = rule_def.get("why_it_happened", f"Rule {rule_id} triggered")

            if condition_str and self._eval_condition(condition_str, context):
                if is_sleeping:
                    # Collaborating with SystemAgent
                    self.bus.record_collaboration(
                        consumer_agent="GPS",
                        upstream_agent="SYSTEM",
                        relationship="STANDBY_CASCADE",
                        evidence=f"GPS fix drop at Line {line_num} coincides with vehicle parked sleep mode (IGN=0).",
                        line_number=line_num,
                    )
                    causal_dep = "SystemAgent:SYS_KN_004"
                    collab_ctx = (
                        f"Secondary cascade: SystemAgent confirmed vehicle entered low-power standby sleep "
                        f"(IGN=0 around Line {self.sleep_line or 2}). GNSS RF receiver is intentionally in standby."
                    )
                    severity = "low"
                    issue_text = f"{rule_id}: {why} (Expected Standby Cascade - Vehicle Sleeping)"
                elif self.battery_brownout or self.blackboard.is_battery_brownout:
                    self.bus.record_collaboration(
                        consumer_agent="GPS",
                        upstream_agent="BATTERY",
                        relationship="POWER_SAG_CASCADE",
                        evidence=f"GPS fix drop at Line {line_num} triggered by main battery rail undervoltage.",
                        line_number=line_num,
                    )
                    causal_dep = "BatteryAgent:BATT_KN_001"
                    collab_ctx = "Secondary cascade: BatteryAgent reported main rail voltage sag below operating threshold."
                    severity = "high"
                    issue_text = f"{rule_id}: {why} (Battery Undervoltage Induced)"
                else:
                    causal_dep = None
                    collab_ctx = "Primary fault: Vehicle active (IGN=ON); GNSS receiver lost satellite constellation."
                    severity = rule_def.get("severity", "MEDIUM").lower()
                    issue_text = f"{rule_id}: {why}"

                self.open_session(
                    session_key=rule_id,
                    issue=issue_text,
                    source="GPS",
                    category="gps",
                    severity=severity,
                    event=event,
                    causal_dependency=causal_dep,
                    collaborative_context=collab_ctx,
                )

        # Dynamic Recovery Trigger: When lock is established (SAT >= 4, FIX_QUA == 1, LAT/LONG != 0)
        if sat >= 4 and fix == 1 and lat != 0.0 and long != 0.0:
            self.bus.publish("GNSS_FIX_ACQUIRED", {"satellites": sat, "line_number": line_num}, sender="GPS")
            for rule_def in self.anomaly_rules.values():
                rule_id = rule_def.get("id")
                if rule_id:
                    self.close_session(
                        rule_id,
                        recovery_event=event,
                        recovery_message=f"GPS state recovered: SAT={sat}, FIX_QUA={fix}",
                    )

    def handle(self, event):
        line = event.get("raw", "")
        line_num = event.get("line_number")
        params = self._parse_gps_line(line)
        if not params:
            return

        self.gps_state["messages_received"] += 1

        if "fix_quality" in params:
            self.gps_state["last_fix_quality"] = params["fix_quality"]
        if "satellite_count" in params:
            self.gps_state["last_satellite_count"] = params["satellite_count"]
        if "latitude" in params:
            self.gps_state["last_lat"] = params["latitude"]
        if "longitude" in params:
            self.gps_state["last_long"] = params["longitude"]

        self.blackboard.set_gps(
            self.gps_state["last_fix_quality"],
            self.gps_state["last_satellite_count"],
            line_number=line_num,
        )

        self._evaluate_yaml_rules(params, event)


gps_agent = GPSAgent()
