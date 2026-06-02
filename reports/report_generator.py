import json
from pathlib import Path
from collections import Counter

# Mapping of known anomalies to suggested fixes (placeholder examples)
SUGGESTED_FIXES = {
    "GPS invalid coordinates": "Check GPS sensor configuration and ensure proper data format.",
    "Missing timestamp": "Ensure log entries include a valid timestamp field.",
    "Signal loss": "Investigate connectivity issues and retry mechanisms.",
    # Add more specific mappings as needed
}


def generate_report_cards():
    """Generate a markdown report with cards for each anomaly type.

    Each card includes:
    - Problem (anomaly description)
    - Occurrence count
    - Suggested fix (if known, otherwise generic guidance)
    """
    base_dir = Path(__file__).parent
    raw_path = base_dir / "raw_anomalies.json"
    report_path = base_dir / "report_cards.md"

    if not raw_path.is_file():
        raise FileNotFoundError(f"Raw anomalies file not found: {raw_path}")

    with open(raw_path, "r", encoding="utf-8") as f:
        anomalies = json.load(f)

    total = len(anomalies)
    counter = Counter(anomalies)
    sorted_items = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)

    lines = []
    lines.append("# Anomaly Report Cards")
    lines.append(f"**Total anomalies detected:** {total}\n")

    for anomaly, count in sorted_items:
        fix = SUGGESTED_FIXES.get(
            anomaly, "Review the log entry and apply appropriate remediation."
        )
        lines.append("---")
        lines.append(f"## {anomaly}")
        lines.append(f"**Occurrences:** {count}")
        lines.append(f"**Problem:** {anomaly}")
        lines.append(f"**Solution:** {fix}\n")

    # Write the report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    generate_report_cards()
