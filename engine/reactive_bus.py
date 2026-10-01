"""
Automotive Reactive Multi-Agent Event Bus & Shared Vehicle Blackboard.
Enables real-time inter-agent messaging, cross-domain state synchronization,
and dynamic causal dependency resolution across all ECU subsystem agents.
"""

from typing import Any, Callable, Dict, List, Optional


class VehicleBlackboard:
    """
    Shared Real-Time Vehicle Context Blackboard.
    Provides a synchronized operational ground truth of the vehicle state
    accessible to all domain agents during stream analysis.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.ignition: Optional[int] = None
        self.in_sleep: bool = False
        self.sleep_remaining: int = 0
        self.sleep_start_line: Optional[int] = None
        self.last_ign_line: Optional[int] = None

        self.ext_battery_v: Optional[float] = None
        self.int_battery_v: Optional[float] = None
        self.is_battery_brownout: bool = False
        self.is_battery_low: bool = False

        self.csq: Optional[int] = None
        self.creg: Optional[int] = None
        self.tcp_connected: bool = True
        self.tcp_skt_raw: str = "000"
        self.tcp_ais_primary: int = 0
        self.tcp_chtp: int = 0
        self.tcp_cip1: int = 0
        self.last_tcp_disconnect_line: Optional[int] = None

        self.gps_fix_quality: int = 0
        self.gps_satellites: int = 0
        self.gps_locked: bool = False

        self.fota_active: bool = False
        self.fota_downloading: bool = False
        self.fota_progress_pct: float = 0.0
        self.fota_offset: int = 0
        self.last_fota_line: Optional[int] = None

        self.can_bus_state: int = 0
        self.uds_active: bool = False
        self.active_dtcs: List[str] = []

        self.device_imei: Optional[str] = None
        self.device_iccid: Optional[str] = None
        self.device_vin: Optional[str] = None
        self.firmware_version: Optional[str] = None
        self.primary_server: Optional[str] = None
        self.secondary_server: Optional[str] = None
        self.last_login_line: Optional[int] = None

        self.inferred_parameters: Dict[str, Dict[str, Any]] = {}
        self.configuration_advisories: List[Dict[str, Any]] = []

    def set_inferred_parameter(self, param_name: str, inferred_value: Any, confidence: float, rationale: str, line_number: Optional[int] = None):
        """
        Record a dynamically synthesized / inferred parameter value when the field
        is missing from the raw telemetry stream or misconfigured for the active firmware release.
        """
        self.inferred_parameters[param_name] = {
            "value": inferred_value,
            "confidence": confidence,
            "rationale": rationale,
            "line_number": line_number,
        }
        if param_name == "tcp_cip1":
            self.tcp_cip1 = int(inferred_value)
        elif param_name == "tcp_chtp":
            self.tcp_chtp = int(inferred_value)
        elif param_name == "tcp_ais_primary":
            self.tcp_ais_primary = int(inferred_value)

    def get_effective_parameter(self, param_name: str) -> Dict[str, Any]:
        """
        Retrieve effective parameter status, indicating whether it was directly
        parsed or dynamically inferred on the fly.
        """
        if param_name in self.inferred_parameters:
            info = self.inferred_parameters[param_name]
            return {
                "parameter": param_name,
                "value": info["value"],
                "status": "DYNAMICALLY_INFERRED",
                "confidence": info["confidence"],
                "rationale": info["rationale"],
                "line_number": info.get("line_number"),
            }
        
        raw_val = None
        if param_name == "tcp_cip1": raw_val = self.tcp_cip1
        elif param_name == "tcp_chtp": raw_val = self.tcp_chtp
        elif param_name == "tcp_ais_primary": raw_val = self.tcp_ais_primary
        
        return {
            "parameter": param_name,
            "value": raw_val,
            "status": "EXPLICIT_RAW" if raw_val is not None else "UNSET",
            "confidence": 1.0 if raw_val is not None else 0.0,
            "rationale": "Directly parsed from telemetry frame" if raw_val is not None else "Field not present in telemetry stream",
        }

    def set_ignition(self, ign_state: int, line_number: Optional[int] = None):
        self.ignition = ign_state
        self.last_ign_line = line_number

    def set_sleep(self, in_sleep: bool, sleep_remaining: int = 0, line_number: Optional[int] = None):
        self.in_sleep = in_sleep
        self.sleep_remaining = sleep_remaining
        if in_sleep and line_number is not None:
            self.sleep_start_line = line_number

    def set_battery(self, ext_v: Optional[float] = None, int_v: Optional[float] = None, line_number: Optional[int] = None):
        if ext_v is not None:
            self.ext_battery_v = ext_v
            self.is_battery_brownout = ext_v < 9.0
            self.is_battery_low = ext_v < 11.5
        if int_v is not None:
            self.int_battery_v = int_v

    def set_cellular(self, csq: Optional[int] = None, creg: Optional[int] = None, tcp_connected: Optional[bool] = None, tcp_skt_raw: Optional[str] = None, line_number: Optional[int] = None):
        if csq is not None:
            self.csq = csq
        if creg is not None:
            self.creg = creg
        if tcp_connected is not None:
            self.tcp_connected = tcp_connected
            if not tcp_connected and line_number is not None:
                self.last_tcp_disconnect_line = line_number
        if tcp_skt_raw is not None:
            self.tcp_skt_raw = tcp_skt_raw
            if len(tcp_skt_raw) >= 3:
                try:
                    self.tcp_ais_primary = int(tcp_skt_raw[0])
                    self.tcp_chtp = int(tcp_skt_raw[1])
                    self.tcp_cip1 = int(tcp_skt_raw[2])
                except ValueError:
                    pass

    def set_gps(self, fix_quality: int, satellites: int, line_number: Optional[int] = None):
        self.gps_fix_quality = fix_quality
        self.gps_satellites = satellites
        self.gps_locked = fix_quality > 0 and satellites >= 4

    def set_fota(self, active: bool = True, downloading: bool = False, pct: float = 0.0, offset: int = 0, line_number: Optional[int] = None):
        self.fota_active = active
        self.fota_downloading = downloading
        self.fota_progress_pct = pct
        self.fota_offset = offset
        if line_number is not None:
            self.last_fota_line = line_number

    def add_dtc(self, dtc_code: str):
        if dtc_code and dtc_code not in self.active_dtcs:
            self.active_dtcs.append(dtc_code)

    def set_device_identity(self, imei: Optional[str] = None, iccid: Optional[str] = None, vin: Optional[str] = None, firmware: Optional[str] = None, primary_server: Optional[str] = None, secondary_server: Optional[str] = None, line_number: Optional[int] = None):
        if imei: self.device_imei = imei
        if iccid: self.device_iccid = iccid
        if vin: self.device_vin = vin
        if firmware: self.firmware_version = firmware
        if primary_server: self.primary_server = primary_server
        if secondary_server: self.secondary_server = secondary_server
        if line_number: self.last_login_line = line_number

    def is_vehicle_sleeping(self) -> bool:
        """Vehicle is in power-saving sleep or ignition is confirmed off."""
        return self.in_sleep or (self.ignition == 0)

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "ignition": "ON (1)" if self.ignition == 1 else ("OFF (0)" if self.ignition == 0 else "UNKNOWN"),
            "in_sleep": self.in_sleep,
            "sleep_remaining_sec": self.sleep_remaining,
            "ext_battery_v": f"{self.ext_battery_v:.2f}V" if self.ext_battery_v is not None else "Unknown",
            "int_battery_v": f"{self.int_battery_v:.2f}V" if self.int_battery_v is not None else "Unknown",
            "is_brownout": self.is_battery_brownout,
            "cellular_csq": self.csq,
            "cellular_creg": self.creg,
            "tcp_connected": self.tcp_connected,
            "tcp_sockets": f"{self.tcp_skt_raw} (AIS/Primary={self.tcp_ais_primary}, CHTP={self.tcp_chtp}, CIP1={self.tcp_cip1})",
            "gps_fix_quality": self.gps_fix_quality,
            "gps_satellites": self.gps_satellites,
            "fota_downloading": self.fota_downloading,
            "fota_progress_pct": f"{self.fota_progress_pct:.2f}%",
            "active_dtcs": list(self.active_dtcs),
            "device_imei": self.device_imei or "Unknown",
            "device_vin": self.device_vin or "Unknown",
            "firmware_version": self.firmware_version or "Unknown",
            "primary_server": self.primary_server or "Unknown",
            "secondary_server": self.secondary_server or "Unknown",
            "inferred_parameters": dict(self.inferred_parameters),
        }


class InterAgentEventBus:
    """
    Reactive Event Bus for Multi-Agent Real-Time Message Passing.
    Enables agents to publish domain events (e.g. SYSTEM_SLEEP, BATTERY_BROWNOUT,
    TCP_DROPPED) and subscribe to events from other agents.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any], str], None]]] = {}
        self.collaboration_records: List[Dict[str, Any]] = []
        self.published_events: List[Dict[str, Any]] = []

    def subscribe(self, event_name: str, callback: Callable[[Dict[str, Any], str], None]):
        """Register a callback for an inter-agent reactive event."""
        self._subscribers.setdefault(event_name, []).append(callback)

    def publish(self, event_name: str, payload: Dict[str, Any], sender: str):
        """Publish a reactive event to all registered subscriber agents."""
        record = {
            "event_name": event_name,
            "payload": payload,
            "sender": sender,
            "line_number": payload.get("line_number"),
        }
        self.published_events.append(record)

        callbacks = self._subscribers.get(event_name, [])
        for cb in callbacks:
            try:
                cb(payload, sender)
            except Exception:
                pass

    def record_collaboration(
        self,
        consumer_agent: str,
        upstream_agent: str,
        relationship: str,
        evidence: str,
        line_number: Optional[int] = None,
    ):
        """Record an explicit inter-agent dependency or collaborative resolution."""
        collab = {
            "consumer_agent": consumer_agent,
            "upstream_agent": upstream_agent,
            "relationship": relationship,
            "evidence": evidence,
            "line_number": line_number,
        }
        self.collaboration_records.append(collab)

    def get_collaborations(self) -> List[Dict[str, Any]]:
        return list(self.collaboration_records)

    def get_published_events(self) -> List[Dict[str, Any]]:
        return list(self.published_events)


# Global singleton instances for system-wide agent coordination
blackboard = VehicleBlackboard()
reactive_bus = InterAgentEventBus()
