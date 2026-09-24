import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent


class GPSAgent(BaseAgent):
    """
    Data-Driven GPS Telemetry Agent.
    Reads knowledge, parameter definitions, and anomaly rules directly from parameters.yaml.
    Dynamically evaluates rules against incoming telemetry lines without hardcoding validation logic.
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
        
        # Load rules & parameter definitions dynamically from YAML
        self.parameters_config = self._load_parameters()
        self.anomaly_rules = self.parameters_config.get("anomaly_rules", {})

    def _load_parameters(self):
        """Load parameters.yaml knowledge configuration."""
        params_file = self.knowledge_dir / "parameters.yaml"
        if not params_file.exists():
            return {}
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            return config.get("gps", config)
        except Exception as e:
            print(f"Warning: Could not load parameters.yaml ({e})")
            return {}

    def _parse_gps_line(self, line):
        """Extract telemetry fields into normalized dictionary."""
        params = {}

        # 1. NMEA format: $GPS,part1,fix_quality,lat,long,sat_count
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
        """
        Dynamically evaluate YAML condition strings like 'SAT == 0 AND FIX_QUA == 0'.
        Replaces symbols with live telemetry values.
        """
        if not condition_str:
            return False
        
        # Prepare expression for python evaluation
        expr = condition_str.replace("AND", "and").replace("OR", "or")
        try:
            return bool(eval(expr, {}, context))
        except Exception:
            return False

    def _evaluate_yaml_rules(self, params, event):
        """
        Dynamically evaluate all anomaly rules declared in parameters.yaml.
        """
        sat = params.get("satellite_count", self.gps_state["last_satellite_count"])
        fix = params.get("fix_quality", self.gps_state["last_fix_quality"])
        lat = params.get("latitude", self.gps_state["last_lat"])
        long = params.get("longitude", self.gps_state["last_long"])

        # Context map linking YAML symbols to parsed telemetry values
        context = {
            "SAT": sat,
            "FIX_QUA": fix,
            "LAT": lat,
            "LONG": long,
        }

        # Iterate over all anomaly rules dynamically defined in parameters.yaml
        for rule_key, rule_def in self.anomaly_rules.items():
            rule_id = rule_def.get("id", rule_key)
            condition_str = rule_def.get("condition")
            severity = rule_def.get("severity", "MEDIUM").lower()
            why = rule_def.get("why_it_happened", f"Rule {rule_id} triggered")

            if condition_str and self._eval_condition(condition_str, context):
                self.open_session(
                    session_key=rule_id,
                    issue=f"{rule_id}: {why}",
                    source="GPS",
                    category="gps",
                    severity=severity,
                    event=event,
                )

        # Dynamic Recovery Trigger: When lock is established (SAT >= 4, FIX_QUA == 1, LAT/LONG != 0)
        if sat >= 4 and fix == 1 and lat != 0.0 and long != 0.0:
            for rule_def in self.anomaly_rules.values():
                rule_id = rule_def.get("id")
                if rule_id:
                    self.close_session(
                        rule_id,
                        recovery_event=event,
                        recovery_message=f"GPS state recovered: SAT={sat}, FIX_QUA={fix}",
                    )

    def handle(self, event):
        """Process incoming GPS log line."""
        line = event.get("raw", "")
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

        # Dynamically evaluate rules from parameters.yaml
        self._evaluate_yaml_rules(params, event)


gps_agent = GPSAgent()

