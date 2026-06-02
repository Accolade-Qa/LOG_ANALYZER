class BaseAgent:
    """Base class for telemetry subsystem agents"""

    def __init__(self):
        self.anomalies = []

    def add_anomaly(self, issue):
        """Record an anomaly detected by this agent"""
        self.anomalies.append(issue)
