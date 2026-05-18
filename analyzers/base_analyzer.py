class BaseAnalyzer:
    def __init__(self):
        self.anomalies = []

    def add_anomaly(self, issue):
        self.anomalies.append(issue)
