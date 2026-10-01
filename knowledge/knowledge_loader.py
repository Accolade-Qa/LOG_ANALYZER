from pathlib import Path
import yaml  # type: ignore

KNOWLEDGE_DIR = Path(__file__).resolve().parent

DEFAULT_GENERIC_INSIGHT = {
    "why": "Telemetry parameter anomaly or string offset formatting mismatch detected.",
    "lookup": "Inspect NMEA / ATCU CSV parser logic in firmware and verify sensor line calibration.",
    "fix": "Review telemetry logs and inspect firmware configuration.",
}

# Dynamic In-Memory Knowledge Registry
KNOWLEDGE_REGISTRY = {}
SUGGESTED_FIXES_REGISTRY = {}


def _format_root_causes(root_causes):
    if not root_causes:
        return "Telemetry parameter threshold breached."
    if isinstance(root_causes, list):
        return "Potential causes: " + ", ".join(root_causes) + "."
    return str(root_causes)


def load_all_knowledge():
    """Dynamically scan knowledge/ directory and load all YAML parameter registries."""
    global KNOWLEDGE_REGISTRY, SUGGESTED_FIXES_REGISTRY
    KNOWLEDGE_REGISTRY.clear()
    SUGGESTED_FIXES_REGISTRY.clear()

    if not KNOWLEDGE_DIR.exists():
        return

    yaml_files = list(KNOWLEDGE_DIR.rglob("*.yaml")) + list(KNOWLEDGE_DIR.rglob("*.yml"))
    for yf in yaml_files:
        try:
            with open(yf, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            # Helper to process an anomaly_rules block
            def process_rules(rules_block):
                if not isinstance(rules_block, dict):
                    return
                for rule_key, rule_def in rules_block.items():
                    if not isinstance(rule_def, dict):
                        continue
                    rule_id = rule_def.get("id") or rule_key
                    why = rule_def.get("why_it_happened") or _format_root_causes(rule_def.get("root_causes"))
                    lookup = rule_def.get("what_to_look_up") or f"Inspect firmware logic and hardware signals for {rule_id}."
                    fix = rule_def.get("suggested_fix") or rule_def.get("condition") or f"Apply remediation for {rule_id}."

                    insight = {
                        "id": rule_id,
                        "why": why,
                        "lookup": lookup,
                        "fix": fix,
                        "severity": rule_def.get("severity", "MEDIUM"),
                    }
                    KNOWLEDGE_REGISTRY[rule_id] = insight
                    KNOWLEDGE_REGISTRY[rule_key] = insight
                    SUGGESTED_FIXES_REGISTRY[rule_id] = fix

            # Helper to process a parameters specification block
            def process_parameters(params_block):
                if not isinstance(params_block, dict):
                    return
                for param_key, param_def in params_block.items():
                    if not isinstance(param_def, dict):
                        continue
                    p_name = param_def.get("name", param_key)
                    symbol = param_def.get("symbol", param_key)
                    desc = param_def.get("description", "")
                    diag = param_def.get("diagram", "")
                    why = f"{p_name} ({symbol}): {desc}"
                    if diag:
                        why += f"\nArchitecture Bitmask:\n{diag.strip()}"
                    insight = {
                        "id": symbol,
                        "parameter": p_name,
                        "symbol": symbol,
                        "type": param_def.get("type"),
                        "why": why,
                        "lookup": param_def.get("format") or param_def.get("units") or "Automotive ECU telemetry parameter specification.",
                        "fix": f"Verify hardware transceiver line integrity and RTOS driver status for {symbol}.",
                        "details": param_def,
                    }
                    KNOWLEDGE_REGISTRY[symbol] = insight
                    KNOWLEDGE_REGISTRY[symbol.lower()] = insight
                    KNOWLEDGE_REGISTRY[param_key] = insight
                    KNOWLEDGE_REGISTRY[param_key.lower()] = insight
                    KNOWLEDGE_REGISTRY[p_name.lower()] = insight

            # Check top-level anomaly_rules and parameters
            if "anomaly_rules" in data:
                process_rules(data["anomaly_rules"])
            if "parameters" in data:
                process_parameters(data["parameters"])

            # Check domain-nested sections (e.g. net.parameters, net.anomaly_rules)
            for top_key, top_val in data.items():
                if isinstance(top_val, dict):
                    if "anomaly_rules" in top_val:
                        process_rules(top_val["anomaly_rules"])
                    if "parameters" in top_val:
                        process_parameters(top_val["parameters"])

        except Exception as e:
            print(f"Warning: Failed to load knowledge file {yf.name}: {e}")


# Initialize registry on import
load_all_knowledge()


def get_rule_insight(rule_id_or_title):
    """Retrieve rule insight dynamically from knowledge registry."""
    if not rule_id_or_title:
        return DEFAULT_GENERIC_INSIGHT

    str_key = str(rule_id_or_title).strip()
    if str_key in KNOWLEDGE_REGISTRY:
        return KNOWLEDGE_REGISTRY[str_key]

    # Partial key matching for dynamic titles (e.g. "GPS_KN_001: No satellite acquisition")
    for k, v in KNOWLEDGE_REGISTRY.items():
        if k and k.lower() in str_key.lower():
            return v

    return DEFAULT_GENERIC_INSIGHT


def get_suggested_fix(rule_id_or_title):
    insight = get_rule_insight(rule_id_or_title)
    return insight.get("fix") or DEFAULT_GENERIC_INSIGHT["fix"]
