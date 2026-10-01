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

    def set_cellular(self, csq: Optional[int] = None, creg: Optional[int] = None, tcp_connected: Optional[bool] = None, line_number: Optional[int] = None):
        if csq is not None:
            self.csq = csq
        if creg is not None:
            self.creg = creg
        if tcp_connected is not None:
            self.tcp_connected = tcp_connected
            if not tcp_connected and line_number is not None:
                self.last_tcp_disconnect_line = line_number

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
            "gps_fix_quality": self.gps_fix_quality,
            "gps_satellites": self.gps_satellites,
            "fota_downloading": self.fota_downloading,
            "fota_progress_pct": f"{self.fota_progress_pct:.2f}%",
            "active_dtcs": list(self.active_dtcs),
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
