from agents.battery_agent import battery_agent
from agents.can_agent import can_agent
from agents.gps_agent import gps_agent
from agents.mqtt_agent import mqtt_agent
from agents.net_agent import net_agent

# Register available agent instances by event type.
# Add new agent imports plus registry entries as more agents are added.
registry = {
    "GPS": gps_agent,
    "MQTT": mqtt_agent,
    "CAN": can_agent,
    "BATTERY": battery_agent,
    "NET": net_agent,
}


def dispatch(event):
    """Dispatch events to appropriate agent."""
    agent = registry.get(event["type"])
    if agent:
        agent.handle(event)
