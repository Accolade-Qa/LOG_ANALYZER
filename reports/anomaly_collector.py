import json
import re
from datetime import datetime
from pathlib import Path

anomalies = []

# Get the absolute path to the anomalies file
ANOMALIES_FILE = Path(__file__).parent / "raw_anomalies.json"
ANOMALY_ID_PATTERN = re.compile(r"^(?P<id>[A-Z]+_KN_\d+):\s*(?P<description>.+)$")


def _normalize_issue(issue):
    if isinstance(issue, dict):
        anomaly = issue.copy()
    else:
        issue_text = str(issue).strip()
        match = ANOMALY_ID_PATTERN.match(issue_text)
        anomaly_id = None
        title = issue_text
        description = issue_text

        if match:
            anomaly_id = match.group("id")
            description = match.group("description").strip()
            title = anomaly_id

        anomaly = {
            "id": anomaly_id,
            "title": title,
            "description": description,
            "severity": "medium",
            "category": None,
            "source": None,
            "detected_at": datetime.utcnow().isoformat() + "Z",
            "metadata": {"raw_line": None, "event_type": None},
        }

    anomaly.setdefault("severity", "medium")
    anomaly.setdefault("category", None)
    anomaly.setdefault("source", None)
    anomaly.setdefault("detected_at", datetime.utcnow().isoformat() + "Z")
    anomaly.setdefault("metadata", {"raw_line": None, "event_type": None})
    return anomaly


def _build_anomaly(
    issue, source=None, category=None, severity=None, event=None, metadata=None
):
    anomaly = _normalize_issue(issue)

    if source:
        anomaly["source"] = source
    if category:
        anomaly["category"] = category
    if severity:
        anomaly["severity"] = severity
    if metadata:
        anomaly["metadata"] = {**anomaly.get("metadata", {}), **metadata}

    if event:
        anomaly["metadata"]["raw_line"] = event.get("raw")
        anomaly["metadata"]["event_type"] = event.get("type")

    if anomaly["category"] is None and anomaly["source"]:
        anomaly["category"] = str(anomaly["source"]).lower()

    if anomaly["id"] is None and anomaly["title"]:
        anomaly["id"] = anomaly["title"].replace(" ", "_")[:64]

    return anomaly


def collect(
    issue, source=None, category=None, severity=None, event=None, metadata=None
):
    anomaly = _build_anomaly(
        issue,
        source=source,
        category=category,
        severity=severity,
        event=event,
        metadata=metadata,
    )

    anomalies.append(anomaly)
    ANOMALIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ANOMALIES_FILE, "w", encoding="utf-8") as f:
        json.dump(anomalies, f, indent=2)
