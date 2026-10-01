from agents.base_agent import BaseAgent
from agents.gps_agent import GPSAgent, gps_agent
from agents.battery_agent import BatteryAgent, battery_agent
from agents.can_agent import CANAgent, can_agent
from agents.net_agent import NetAgent, net_agent
from agents.mqtt_agent import MQTTAgent, mqtt_agent
from agents.ais_agent import AISAgent, ais_agent
from agents.system_agent import SystemAgent, system_agent
from agents.fota_agent import FOTAAgent, fota_agent

ALL_AGENTS = [
    fota_agent,
    gps_agent,
    battery_agent,
    can_agent,
    net_agent,
    mqtt_agent,
    ais_agent,
    system_agent,
]

__all__ = [
    "BaseAgent",
    "GPSAgent",
    "gps_agent",
    "BatteryAgent",
    "battery_agent",
    "CANAgent",
    "can_agent",
    "NetAgent",
    "net_agent",
    "MQTTAgent",
    "mqtt_agent",
    "AISAgent",
    "ais_agent",
    "SystemAgent",
    "system_agent",
    "FOTAAgent",
    "fota_agent",
    "ALL_AGENTS",
]
