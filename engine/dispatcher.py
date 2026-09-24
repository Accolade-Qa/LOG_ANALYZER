from agents.gps_agent import gps_agent

registry = {
    "GPS": gps_agent,
}


def dispatch(event):
    """Dispatch GPS telemetry events to the GPS agent."""
    agent = registry.get(event["type"])
    if agent:
        agent.handle(event)

