import re
from pathlib import Path

import yaml  # type: ignore

from agents.base_agent import BaseAgent
from reports.anomaly_collector import collect


class BatteryAgent(BaseAgent):
    """Battery telemetry analysis agent."""

    def __init__(self):
        super().__init__()
        self.events_received = 0
        self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "battery"
        self.parameters = self._load_parameters()
        self.anomaly_rules = self.parameters.get("anomaly_rules", {})

    def _load_parameters(self):
        params_file = self.knowledge_dir / "parameters.yaml"
        if not params_file.exists():
            return {}

        with open(params_file, "r") as f:
            return yaml.safe_load(f) or {}

    def _parse_battery_line(self, line):
        params = {}

        if "$ANALOG," in line:
            parts = line.split("$ANALOG,")[1].split(",")
            if len(parts) >= 3:
                try:
                    params["voltage"] = float(parts[2].strip())
                    params["temperature"] = float(parts[3].strip())
                    return params
                except (ValueError, IndexError):
                    pass

        voltage_match = re.search(r"INT\s+BATT\s*([\d.]+)V", line, re.IGNORECASE)
        soc_match = re.search(
            r"INT\s+BATT\s*[\d.]+V\s*([\d.]+)\s*PERCENT", line, re.IGNORECASE
        )
        temp_match = re.search(r"TMPR\s*([\d.-]+)", line, re.IGNORECASE)

        if voltage_match:
            params["voltage"] = float(voltage_match.group(1))

        if soc_match:
            params["state_of_charge"] = float(soc_match.group(1))

        if temp_match:
            params["temperature"] = float(temp_match.group(1))

        return params

    def _validate_parameter_range(self, param_name, value):
        param_defs = self.parameters.get("parameters", {})
        param_def = param_defs.get(param_name, {})
        valid_range = param_def.get("valid_range")
        if valid_range is None or value is None:
            return None

        min_val, max_val = valid_range
        if value < min_val or value > max_val:
            return f"Battery {param_name} out of range: {value} (expected {min_val}-{max_val})"

        return None

    def _check_critical_parameters(self, params, event=None):
        param_defs = self.parameters.get("parameters", {})
        for param_name, param_def in param_defs.items():
            if not param_def.get("critical", False):
                continue
            if param_name not in params:
                issue = f"Critical battery parameter missing: {param_name}"
                self.add_anomaly(issue)
                collect(
                    issue,
                    source="BATTERY",
                    category="battery",
                    severity="low",
                    event=event,
                )
                continue
            error = self._validate_parameter_range(param_name, params[param_name])
            if error:
                self.add_anomaly(error)
                collect(
                    error,
                    source="BATTERY",
                    category="battery",
                    severity="medium",
                    event=event,
                )

    def _check_anomaly_rules(self, params, event=None):
        voltage = params.get("voltage")
        temperature = params.get("temperature")

        if voltage is not None and voltage < 3.0:
            rule = self.anomaly_rules.get("low_voltage", {})
            issue = f"{rule.get('id', 'BATT_KN_001')}: Low battery voltage ({voltage}V)"
            if rule and rule.get("root_causes"):
                issue += f" - {', '.join(rule.get('root_causes', []))}"
            self.open_session(
                session_key="BATT_KN_001",
                issue=issue,
                source="BATTERY",
                category="battery",
                severity="high",
                event=event,
            )
        elif voltage is not None and voltage >= 3.3:
            self.close_session(
                "BATT_KN_001",
                recovery_event=event,
                recovery_message=f"Battery voltage restored: {voltage}V",
            )

        if temperature is not None and temperature > 50:
            rule = self.anomaly_rules.get("over_temperature", {})
            issue = f"{rule.get('id', 'BATT_KN_002')}: High battery temperature ({temperature}C)"
            if rule and rule.get("root_causes"):
                issue += f" - {', '.join(rule.get('root_causes', []))}"
            self.open_session(
                session_key="BATT_KN_002",
                issue=issue,
                source="BATTERY",
                category="battery",
                severity="high",
                event=event,
            )
        elif temperature is not None and temperature <= 45:
            self.close_session(
                "BATT_KN_002",
                recovery_event=event,
                recovery_message=f"Battery temperature normalized: {temperature}C",
            )


    def handle(self, event):
        self.events_received += 1
        params = self._parse_battery_line(event["raw"])
        if not params:
            return

        self._check_critical_parameters(params, event)
        self._check_anomaly_rules(params, event)



battery_agent = BatteryAgent()
