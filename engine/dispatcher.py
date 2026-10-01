from agents.gps_agent import gps_agent
from agents.battery_agent import battery_agent
from agents.can_agent import can_agent
from agents.net_agent import net_agent
from agents.mqtt_agent import mqtt_agent
from agents.ais_agent import ais_agent
from agents.system_agent import system_agent
from agents.fota_agent import fota_agent
from engine.reactive_bus import blackboard, reactive_bus

registry = {
    "FOTA": fota_agent,
    "GPS": gps_agent,
    "BATTERY": battery_agent,
    "CAN": can_agent,
    "NET": net_agent,
    "MQTT": mqtt_agent,
    "AIS": ais_agent,
    "SYSTEM": system_agent,
}


def reset_all_agents():
    """Reset blackboard, event bus, and all agent internal sessions for a clean run."""
    blackboard.reset()
    reactive_bus.reset()
    for agent in registry.values():
        if hasattr(agent, "reset_state"):
            agent.reset_state()


def dispatch(event):
    """Dispatch telemetry events to their specialized subsystem agent."""
    if not event:
        return
    agent = registry.get(event.get("type"))
    if agent:
        agent.handle(event)
