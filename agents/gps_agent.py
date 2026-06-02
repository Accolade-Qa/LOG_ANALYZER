from agents.base_agent import BaseAgent
from reports.anomaly_collector import collect
from pathlib import Path
import re
import yaml  # type: ignore


class GPSAgent(BaseAgent):
    """GPS telemetry analysis agent with scalable YAML-based parameter validation"""

    def __init__(self):
        super().__init__()
        try:
            self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "gps"
        except (NameError, TypeError):
            # Fallback if __file__ is not available
            self.knowledge_dir = Path.cwd() / "knowledge" / "gps"

        self.gps_state = {
            "boot_time": None,
            "last_fix_quality": None,
            "last_satellite_count": None,
            "last_lat": None,
            "last_long": None,
            "messages_received": 0,
            "fix_acquired": False,
            "fix_acquisition_time": None,
        }
        # Load from YAML config (scalable approach)
        self.parameters = self._load_parameters()
        self.rules = self._load_rules()
        self.anomaly_rules = self.parameters.get("anomaly_rules", {})
        self.baseline = self.parameters.get("baseline_expectations", {})
        self.knowledge = self._load_knowledge()

    def _load_parameters(self):
        """Load parameter definitions from parameters.yaml (scalable)"""
        params_file = self.knowledge_dir / "parameters.yaml"
        if not params_file.exists():
            return {}

        with open(params_file, "r") as f:
            config = yaml.safe_load(f) or {}
        return config

    def _load_rules(self):
        """Load GPS validation rules from rules.md"""
        rules_file = self.knowledge_dir / "rules.md"
        if not rules_file.exists():
            return {}

        # Extract from parameters.yaml which now contains rules
        params_file = self.knowledge_dir / "parameters.yaml"
        if params_file.exists():
            with open(params_file, "r") as f:
                config = yaml.safe_load(f) or {}
                params = config.get("parameters", {})

                rules = {
                    "fix_acquisition_timeout": 120,
                    "required_fields": [
                        p.get("symbol") for p in params.values() if p.get("critical")
                    ],
                    "acceptable_satellite_count_min": 4,
                    "strong_satellite_count_min": 8,
                    "parameters": params,
                }
                return rules

        return {}

    def _load_knowledge(self):
        """Load GPS domain knowledge from knowledge.md"""
        knowledge_file = self.knowledge_dir / "knowledge.md"
        if not knowledge_file.exists():
            return {}

        return {
            "fix_quality_levels": {0: "No Fix", 1: "Valid Fix"},
            "satellite_thresholds": {
                "weak": (0, 3),
                "acceptable": (4, 7),
                "strong": (8, float("inf")),
            },
            "known_patterns": {
                "GPS_KN_001": "SAT=0, FIX=0 → No satellite acquisition",
                "GPS_KN_002": "SAT>4, FIX=0 → Satellite visible but fix not acquired",
            },
        }

    def _parse_gps_line(self, line):
        """Extract GPS parameters from log line using YAML schema"""
        params = {}
        param_defs = self.parameters.get("parameters", {})

        # Build regex patterns from YAML parameter definitions
        for param_name, param_def in param_defs.items():
            symbol = param_def.get("symbol", "")
            param_type = param_def.get("type", "")

            # Create regex pattern based on symbol
            pattern = rf"{re.escape(symbol)}\s+([-\d.]+)"
            match = re.search(pattern, line, re.IGNORECASE)

            if match:
                try:
                    value = match.group(1)
                    # Convert to appropriate type
                    if param_type == "integer":
                        params[param_name] = int(value)
                    elif param_type == "float":
                        params[param_name] = float(value)
                    else:
                        params[param_name] = value
                except ValueError:
                    params[param_name] = match.group(1)

        return params

    def _validate_parameter_range(self, param_name, value):
        """Validate parameter against YAML-defined range"""
        param_defs = self.parameters.get("parameters", {})
        if param_name not in param_defs:
            return None

        param_def = param_defs[param_name]
        valid_range = param_def.get("valid_range", [])

        if not valid_range or value is None:
            return None

        min_val, max_val = valid_range[0], valid_range[1]
        if value < min_val or value > max_val:
            return f"{param_name} out of range: {value} (expected {min_val}-{max_val})"

        return None

    def _check_critical_parameters(self, params):
        """Validate critical parameters using YAML schema"""
        param_defs = self.parameters.get("parameters", {})

        for param_name, param_def in param_defs.items():
            if not param_def.get("critical", False):
                continue

            if param_name not in params:
                issue = f"Critical parameter missing: {param_name}"
                self.add_anomaly(issue)
                collect(issue)
                continue

            # Check range
            error = self._validate_parameter_range(param_name, params[param_name])
            if error:
                self.add_anomaly(error)
                collect(error)

    def _check_coordinate_validity(self, params):
        """Check for invalid coordinate patterns"""
        lat = params.get("latitude", 0)
        long = params.get("longitude", 0)
        fix_quality = params.get("fix_quality")

        # Pattern: FIX=1 but LAT/LONG=0 (invalid coordinates)
        if fix_quality == 1 and (lat == 0 or long == 0):
            issue = f"GPS invalid coordinates: LAT={lat}, LONG={long} (FIX QUA={fix_quality})"
            self.add_anomaly(issue)
            collect(issue)

    def _check_satellite_health(self, params):
        """Check satellite count against baseline expectations"""
        sat = params.get("satellite_count")
        if sat is None:
            return

        baseline = self.baseline.get("normal_satellite_range", {})
        if not baseline:
            return

        normal_range = baseline.get("range", [5, 15])
        normal_min, normal_max = normal_range[0], normal_range[1]

        if sat < normal_min and sat > 0:
            health = "weak" if sat < 4 else "acceptable"
            issue = f"GPS low satellite count: {sat} (expected {normal_min}-{normal_max}, {health} signal)"
            self.add_anomaly(issue)
            collect(issue)

    def _match_anomaly_patterns(self, params):
        """Match against known anomaly patterns from YAML"""
        sat = params.get("satellite_count", 0)
        fix_quality = params.get("fix_quality")

        anomaly_rules = self.anomaly_rules or {}

        # Pattern GPS_KN_001: SAT=0, FIX=0
        if sat == 0 and fix_quality == 0:
            pattern = anomaly_rules.get("no_satellite_acquisition", {})
            issue = f"GPS_KN_001: No satellite acquisition (SAT=0, FIX=0)"
            if pattern:
                causes = pattern.get("root_causes", [])
                issue += f" - {', '.join(causes)}"
            self.add_anomaly(issue)
            collect(issue)

        # Pattern GPS_KN_002: SAT>4, FIX=0
        elif sat >= 4 and fix_quality == 0:
            pattern = anomaly_rules.get("satellite_visible_no_fix", {})
            issue = f"GPS_KN_002: Satellite visible but no fix (SAT={sat}, FIX=0)"
            if pattern:
                causes = pattern.get("root_causes", [])
                issue += f" - {', '.join(causes)}"
            self.add_anomaly(issue)
            collect(issue)

        # Pattern GPS_KN_004: Low satellites
        elif sat < 4 and sat > 0:
            pattern = anomaly_rules.get("low_satellite_count", {})
            issue = f"GPS_KN_004: Low satellite count (SAT={sat})"
            if pattern:
                causes = pattern.get("root_causes", [])
                issue += f" - {', '.join(causes)}"
            self.add_anomaly(issue)
            collect(issue)

    def handle(self, event):
        """Process GPS event with YAML-based knowledge and parameter validation"""
        line = event["raw"]

        # Parse GPS parameters using YAML schema
        params = self._parse_gps_line(line)

        if not params:
            return  # No GPS parameters found

        # Update state
        self.gps_state["messages_received"] += 1
        if "fix_quality" in params:
            self.gps_state["last_fix_quality"] = params["fix_quality"]
        if "satellite_count" in params:
            self.gps_state["last_satellite_count"] = params["satellite_count"]
        if "latitude" in params:
            self.gps_state["last_lat"] = params["latitude"]
        if "longitude" in params:
            self.gps_state["last_long"] = params["longitude"]

        # Run validation checks
        self._check_critical_parameters(params)
        self._check_coordinate_validity(params)
        self._check_satellite_health(params)
        self._match_anomaly_patterns(params)


gps_agent = GPSAgent()
