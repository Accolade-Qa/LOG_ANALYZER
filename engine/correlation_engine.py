"""
Automotive Cross-Domain Temporal Correlation Engine.
Identifies causal dependencies and cascade fault patterns across subsystems
(e.g., distinguishing primary root causes like vehicle sleep/power cut from secondary symptoms like CAN/GPS dropouts).
"""

from collections import defaultdict


def correlate_anomalies(anomalies, time_window_seconds=15.0):
    """
    Analyze anomalies chronologically across subsystems and attach
    causal correlation metadata.
    """
    if not anomalies:
        return []

    # Sort anomalies by start_line or timestamp
    def get_sort_key(a):
        meta = a.get("metadata", {})
        return meta.get("start_line") or 0

    sorted_anomalies = sorted(anomalies, key=get_sort_key)

    # Track sleep and power events
    sleep_events = []
    power_events = []
    rf_events = []
    crash_events = []

    for a in sorted_anomalies:
        aid = a.get("id", "")
        source = a.get("source", "")
        meta = a.get("metadata", {})

        if aid == "SYS_KN_004" or "SLEEP" in aid or "Ignition OFF" in a.get("description", ""):
            sleep_events.append(a)
        elif aid in ["BATT_KN_001", "BATT_KN_004"] or "Battery" in source:
            power_events.append(a)
        elif aid in ["NET_KN_001", "GPS_KN_001", "GPS_KN_004"]:
            rf_events.append(a)
        elif aid in ["SYS_KN_001", "SYS_KN_003"]:
            crash_events.append(a)

    # Correlate symptoms with primary root causes
    for a in sorted_anomalies:
        aid = a.get("id", "")
        meta = a.get("metadata", {})
        start_ln = meta.get("start_line", 0)
        end_ln = meta.get("end_line", start_ln)
        
        # Initialize correlation field
        a["correlation"] = {
            "is_cascade_symptom": False,
            "primary_trigger": None,
            "pattern_type": "INDEPENDENT_ANOMALY",
            "confidence": 1.0,
            "diagnostic_insight": "Isolated subsystem telemetry fault.",
        }

        # 0. High-Priority Live Reactive Agent Collaboration Dependency
        if meta.get("causal_dependency"):
            dep = meta.get("causal_dependency")
            collab = meta.get("collaborative_context", "Inter-agent reactive dependency verified.")
            a["correlation"] = {
                "is_cascade_symptom": True,
                "primary_trigger": dep,
                "pattern_type": "REACTIVE_AGENT_COLLABORATION",
                "confidence": 0.98,
                "diagnostic_insight": collab,
            }
            continue

        # 1. Check if CAN timeout or GPS loss is a symptom of Vehicle Sleep Mode
        if aid in ["CAN_KN_001", "GPS_KN_001", "NET_KN_004"]:
            matching_sleep = [
                s for s in sleep_events
                if abs(s.get("metadata", {}).get("start_line", 0) - start_ln) < 500
                or (s.get("metadata", {}).get("start_line", 0) <= start_ln <= s.get("metadata", {}).get("end_line", start_ln))
            ]
            if matching_sleep:
                sleep_ref = matching_sleep[0]
                a["correlation"] = {
                    "is_cascade_symptom": True,
                    "primary_trigger": sleep_ref.get("id", "SYS_KN_004"),
                    "pattern_type": "VEHICLE_SLEEP_CASCADE",
                    "confidence": 0.95,
                    "diagnostic_insight": (
                        f"Secondary symptom: This {a.get('source')} outage occurred during Vehicle Low-Power Sleep "
                        f"(triggered around Line {sleep_ref.get('metadata', {}).get('start_line')}). "
                        f"Hardware bus and RF peripherals were intentionally powered down to conserve vehicle battery."
                    ),
                }
                continue

        # 2. Check if fault was triggered by vehicle battery drop (EXT_BATT < 9V)
        if aid in ["CAN_KN_001", "NET_KN_002", "NET_KN_003", "SYS_KN_003"]:
            matching_power = [
                p for p in power_events
                if abs(p.get("metadata", {}).get("start_line", 0) - start_ln) < 200
            ]
            if matching_power:
                power_ref = matching_power[0]
                a["correlation"] = {
                    "is_cascade_symptom": True,
                    "primary_trigger": power_ref.get("id", "BATT_KN_001"),
                    "pattern_type": "POWER_RAIL_DROPOUT_CASCADE",
                    "confidence": 0.90,
                    "diagnostic_insight": (
                        f"Secondary symptom: Triggered by vehicle power rail collapse or main battery disconnect "
                        f"(at Line {power_ref.get('metadata', {}).get('start_line')}). Subsystem lost VCC supply."
                    ),
                }
                continue

        # 3. Check for environmental RF blind zone (simultaneous Cellular CSQ + GPS loss)
        if aid == "GPS_KN_001":
            matching_net = [
                r for r in rf_events
                if r.get("id") in ["NET_KN_001", "NET_KN_002"]
                and abs(r.get("metadata", {}).get("start_line", 0) - start_ln) < 150
            ]
            if matching_net:
                net_ref = matching_net[0]
                a["correlation"] = {
                    "is_cascade_symptom": False,
                    "primary_trigger": "ENVIRONMENTAL_SHIELDING",
                    "pattern_type": "RF_SHIELDED_ZONE",
                    "confidence": 0.88,
                    "diagnostic_insight": (
                        f"Correlated RF Dropout: Concurrent Cellular signal degradation (Line {net_ref.get('metadata', {}).get('start_line')}) "
                        f"and GPS satellite loss indicate external environmental shielding (tunnel, basement, or metal container), "
                        f"rather than hardware antenna cable damage."
                    ),
                }
                continue

        # 4. Check for Watchdog Crash following RTOS Heap Exhaustion
        if aid == "SYS_KN_003":
            matching_heap = [
                c for c in crash_events
                if c.get("id") == "SYS_KN_001"
                and c.get("metadata", {}).get("start_line", 0) <= start_ln
            ]
            if matching_heap:
                heap_ref = matching_heap[0]
                a["correlation"] = {
                    "is_cascade_symptom": True,
                    "primary_trigger": "SYS_KN_001",
                    "pattern_type": "HEAP_EXHAUSTION_CRASH",
                    "confidence": 0.96,
                    "diagnostic_insight": (
                        f"Watchdog Crash Root Cause: Memory heap was previously exhausted (Line {heap_ref.get('metadata', {}).get('start_line')}), "
                        f"forcing MCU watchdog reset."
                    ),
                }

    return sorted_anomalies
