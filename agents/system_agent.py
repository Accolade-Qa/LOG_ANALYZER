import re
from pathlib import Path
import yaml  # type: ignore

from agents.base_agent import BaseAgent


class SystemAgent(BaseAgent):
    """
    Automotive System, RTOS & Power Management Agent.
    Monitors MCU CPU temperature, RTOS Heap allocation, system uptime (reboots),
    vehicle ignition signal, and power-saving sleep cycles.
    """

    def __init__(self):
        super().__init__()
        self.knowledge_dir = Path(__file__).parent.parent / "knowledge" / "system"
        self.system_state = {
            "messages_received": 0,
            "last_uptime": 0,
            "last_cpu_temp": 45.0,
            "last_heap_ratio": 0.44,
            "last_ignition": 0,
            "in_sleep": False,
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
            return config.get("system", config)
        except Exception as e:
            print(f"Warning: Could not load system parameters.yaml ({e})")
            return {}

    def _parse_system_line(self, line):
        params = {}

        # 1. DIAG HEAP: [PLA] DIAG    HEAP (5551624/12582912)
        heap_match = re.search(r"HEAP\s*\((\d+)\s*/\s*(\d+)\)", line, re.IGNORECASE)
        if heap_match:
            used = int(heap_match.group(1))
            total = int(heap_match.group(2))
            params["heap_used"] = used
            params["heap_total"] = total
            params["heap_ratio"] = used / total if total > 0 else 0.0

        # 2. SYSTEM UPTIME & CPU:
        # [PLA] SYSTEM  RTC 24/06/2024, 12:26:02, UTC EPOCH 1719231962, UPTIME SEC 132, CPU 47.18 DEG CEL, CLK 528000000
        uptime_match = re.search(r"UPTIME\s+SEC\s+(\d+)", line, re.IGNORECASE)
        if uptime_match:
            params["uptime_sec"] = int(uptime_match.group(1))

        cpu_match = re.search(r"CPU\s+([\d.]+)\s*DEG\s+CEL", line, re.IGNORECASE)
        if cpu_match:
            params["cpu_temp"] = float(cpu_match.group(1))

        # 3. DIGITAL IGNITION: [PLA] DIGITAL IGN 0, DI 00000000, DO 00, EMR 0, WC 0
        ign_match = re.search(r"IGN\s*(\d+)", line, re.IGNORECASE)
        if ign_match:
            params["ignition"] = int(ign_match.group(1))

        # 4. SLEEP: [PLA] SLEEP   176...
        sleep_match = re.search(r"SLEEP\s+(\d+)", line, re.IGNORECASE)
        if sleep_match:
            params["sleep_remaining"] = int(sleep_match.group(1))
            params["in_sleep"] = True

        return params

    def handle(self, event):
        line = event.get("raw", "")
        params = self._parse_system_line(line)
        if not params:
            return

        self.system_state["messages_received"] += 1

        # Track RTOS heap exhaustion
        if "heap_ratio" in params:
            ratio = params["heap_ratio"]
            self.system_state["last_heap_ratio"] = ratio
            if ratio > 0.90:
                self.open_session(
                    session_key="SYS_KN_001",
                    issue=f"SYS_KN_001: RTOS Heap Memory Critical ({ratio*100:.1f}% used: {params['heap_used']}/{params['heap_total']})",
                    source="SYSTEM",
                    category="system",
                    severity="critical",
                    event=event,
                )
            elif ratio <= 0.80:
                self.close_session(
                    "SYS_KN_001",
                    recovery_event=event,
                    recovery_message=f"Heap memory recovered: {ratio*100:.1f}% used",
                )

        # Track CPU temperature
        if "cpu_temp" in params:
            temp = params["cpu_temp"]
            self.system_state["last_cpu_temp"] = temp
            if temp > 85.0:
                self.open_session(
                    session_key="SYS_KN_002",
                    issue=f"SYS_KN_002: MCU Overheating (CPU={temp} deg C)",
                    source="SYSTEM",
                    category="system",
                    severity="high",
                    event=event,
                )
            elif temp <= 75.0:
                self.close_session(
                    "SYS_KN_002",
                    recovery_event=event,
                    recovery_message=f"CPU temperature cooled: {temp} deg C",
                )

        # Track MCU unexpected reboots (watchdog crash)
        if "uptime_sec" in params:
            uptime = params["uptime_sec"]
            prev_uptime = self.system_state["last_uptime"]
            if uptime < prev_uptime and prev_uptime > 60:
                # Reboot detected!
                self.open_session(
                    session_key="SYS_KN_003",
                    issue=f"SYS_KN_003: Unexpected MCU Watchdog Reboot Detected (Uptime dropped from {prev_uptime}s to {uptime}s)",
                    source="SYSTEM",
                    category="system",
                    severity="critical",
                    event=event,
                )
            self.system_state["last_uptime"] = uptime

        # Track vehicle sleep cycles
        if params.get("in_sleep") or (params.get("ignition") == 0 and params.get("sleep_remaining")):
            self.system_state["in_sleep"] = True
            self.open_session(
                session_key="SYS_KN_004",
                issue="SYS_KN_004: Vehicle Ignition OFF - Low-Power Standby Sleep Active",
                source="SYSTEM",
                category="system",
                severity="low",
                event=event,
            )
        elif params.get("ignition") == 1:
            self.system_state["in_sleep"] = False
            self.close_session(
                "SYS_KN_004",
                recovery_event=event,
                recovery_message="Vehicle Ignition ON - TCU woken up to active operational mode",
            )


system_agent = SystemAgent()
