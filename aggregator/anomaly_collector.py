import json

anomalies = []

def collect(issue):
    anomalies.append(issue)
    with open('reports/raw_anomalies.json', 'w') as f:
        json.dump(anomalies, f, indent=2)
