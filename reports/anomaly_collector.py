import json
import os
from pathlib import Path

anomalies = []

# Get the absolute path to the anomalies file
ANOMALIES_FILE = Path(__file__).parent / "raw_anomalies.json"


def collect(issue):
    anomalies.append(issue)

    with open(ANOMALIES_FILE, "w") as f:
        json.dump(anomalies, f, indent=2)
