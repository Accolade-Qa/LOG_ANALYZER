from agents.gps_agent import gps_agent

# GPS-only integration phase
registry = {
    "GPS": gps_agent,
}


def dispatch(event):
    """Dispatch events to appropriate agent (GPS-only phase)"""
    agent = registry.get(event["type"])
    if agent:
        agent.handle(event)
