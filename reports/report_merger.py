import json
from pathlib import Path


def merge_reports():
    base_dir = Path(__file__).parent
    anomalies_path = base_dir / "raw_anomalies.json"
    report_path = base_dir / "final_report.md"

    with open(anomalies_path) as f:
        anomalies = json.load(f)

    with open(report_path, "w") as f:
        f.write("# Telemetry Report\n\n")

        for item in anomalies:
            f.write(f"- {item}\n")
