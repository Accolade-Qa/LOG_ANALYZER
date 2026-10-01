"""
Automotive Unsupervised Semantic Anomaly Discovery Engine.
Autonomously adapts to unmodeled, novel vehicle logs by scanning for unhandled
exceptions, hardware bus errors, RTOS assertions, and driver fault codes
without requiring prior human-written YAML rules.
"""

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# Regex patterns for error level indicators and unhandled faults
ERROR_TOKEN_PATTERN = re.compile(
    r"(?:ERROR\s*:\s*|FATAL\s*:\s*|WARN\s*:\s*|\+CM[ES]\s+ERROR\s*:\s*|Assert\s+failed|HardFault|BusFault|UsageFault|overflow|corrupt|panic|exception)",
    re.IGNORECASE
)

TIMESTAMP_PATTERN = re.compile(r"\[(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]")


def _extract_template(line):
    """
    Normalize log line to extract canonical template by abstracting
    timestamps, numbers, hex addresses, and variable strings.
    """
    # Remove timestamp
    cleaned = re.sub(r"^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\]\s*", "", line)
    # Remove hex addresses e.g. 0x1234 or :011
    cleaned = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", cleaned)
    # Remove numbers
    cleaned = re.sub(r"\b\d+\b", "<NUM>", cleaned)
    # Clean whitespace
    return re.sub(r"\s+", " ", cleaned).strip()


def scan_unmodeled_anomalies(log_path, known_anomaly_lines=None, max_novel_clusters=15):
    """
    Scan raw log for unmodeled errors and cluster into novel anomaly dockets.
    """
    if not log_path or not Path(log_path).exists():
        return []

    known_lines = set(known_anomaly_lines or [])
    clusters = defaultdict(lambda: {
        "count": 0,
        "first_line": None,
        "last_line": None,
        "sample_lines": [],
        "severity": "medium",
        "raw_template": "",
    })

    try:
        with open(log_path, "r", errors="ignore") as f:
            for line_num, line in enumerate(f, start=1):
                # Skip if already part of an explicit rule-based anomaly
                if line_num in known_lines:
                    continue

                if ERROR_TOKEN_PATTERN.search(line):
                    template = _extract_template(line)
                    cluster = clusters[template]
                    cluster["count"] += 1
                    if cluster["first_line"] is None:
                        cluster["first_line"] = line_num
                    cluster["last_line"] = line_num
                    cluster["raw_template"] = template

                    if len(cluster["sample_lines"]) < 3:
                        cluster["sample_lines"].append(f"L{line_num}: {line.strip()}")

                    # Determine severity
                    line_upper = line.upper()
                    if any(tok in line_upper for tok in ["FATAL", "PANIC", "HARDFAULT", "CRASH"]):
                        cluster["severity"] = "critical"
                    elif any(tok in line_upper for tok in ["ERROR:", "+CME ERROR", "+CMS ERROR"]):
                        if cluster["severity"] != "critical":
                            cluster["severity"] = "high"
    except Exception as e:
        print(f"Warning: Unsupervised scan encountered error: {e}")
        return []

    discovered = []
    # Sort clusters by frequency and severity
    sorted_clusters = sorted(
        clusters.items(),
        key=lambda item: (1 if item[1]["severity"] == "critical" else (2 if item[1]["severity"] == "high" else 3), -item[1]["count"])
    )

    for i, (template, data) in enumerate(sorted_clusters[:max_novel_clusters], start=1):
        cluster_id = f"NOVEL_ERR_{i:03d}"
        
        # Determine subsystem prefix if present (e.g. [PLA], [NET], [CVP], [AIS])
        subsys_match = re.search(r"\[([A-Z0-9_]{3,6})\]", template)
        subsystem = subsys_match.group(1) if subsys_match else "UNCLASSIFIED"

        discovered.append({
            "id": cluster_id,
            "title": f"{cluster_id}: {template[:80]}",
            "description": f"Unsupervised Anomaly: {template} ({data['count']} occurrences)",
            "severity": data["severity"],
            "source": subsystem,
            "category": "novel_discovery",
            "detected_at": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "start_line": data["first_line"],
                "end_line": data["last_line"],
                "occurrence_count": data["count"],
                "status": "UNMODELED_DISCOVERY",
                "template": template,
                "sample_traces": data["sample_lines"],
            },
            "correlation": {
                "is_cascade_symptom": False,
                "primary_trigger": None,
                "pattern_type": "ZERO_SHOT_DISCOVERY",
                "confidence": 0.85,
                "diagnostic_insight": (
                    f"Discovered novel error pattern in subsystem [{subsystem}] with {data['count']} occurrences "
                    f"between Line {data['first_line']} and Line {data['last_line']}. Requires autonomous investigation."
                ),
            }
        })

    return discovered
