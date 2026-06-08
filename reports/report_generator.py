import json
from collections import Counter, defaultdict
from pathlib import Path

# Mapping of known anomaly titles to suggested fixes.
SUGGESTED_FIXES = {
    "GPS_KN_001": "Investigate satellite reception and antenna placement to restore GPS lock.",
    "GPS_KN_002": "Verify GPS fix acquisition logic and ensure enough visible satellites are present.",
    "GPS_KN_004": "Check satellite visibility and antenna orientation to improve satellite count.",
    "GPS invalid coordinates": "Check GPS sensor configuration and ensure proper coordinate formatting.",
    "Critical parameter missing": "Confirm the source log contains all required parameters and validate parsing rules.",
    "BATT_KN_001": "Inspect battery health and charging circuits; low voltage may indicate failing cells.",
    "BATT_KN_002": "Cool the battery pack and verify thermal management systems.",
    "CAN_KN_001": "Investigate UDS session stability and ensure timeouts are handled properly.",
    "CAN_KN_002": "Review fault codes and diagnose the underlying CAN module issue.",
    "MQTT_KN_001": "Check broker connectivity and MQTT keepalive settings.",
    "MQTT_KN_002": "Reduce MQTT latency by improving network QoS or message handling.",
    "NET_KN_001": "Improve radio signal strength or move the device to a better reception area.",
    "NET_KN_002": "Verify GSM registration credentials and network coverage.",
    "NET_KN_003": "Inspect packet data connectivity and mobile network registration.",
    "NET_KN_004": "Confirm operator information is available and correctly reported.",
    "NET_KN_005": "Check network connectivity and active socket usage for telemetry traffic.",
}

DEFAULT_SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def _load_anomalies(raw_path):
    with open(raw_path, "r", encoding="utf-8") as f:
        anomalies = json.load(f)

    if not anomalies:
        return []

    if isinstance(anomalies[0], str):
        normalized = []
        for issue in anomalies:
            normalized.append(
                {
                    "id": None,
                    "title": issue,
                    "description": issue,
                    "severity": "medium",
                    "category": None,
                    "source": None,
                    "detected_at": None,
                    "metadata": {"raw_line": None, "event_type": None},
                }
            )
        return normalized

    return anomalies


def _group_counts(anomalies, key):
    counter = Counter()
    for anomaly in anomalies:
        counter[anomaly.get(key) or "unknown"] += 1
    return counter


def _best_examples(anomalies):
    examples = defaultdict(list)
    for anomaly in anomalies:
        anomaly_id = anomaly.get("id") or anomaly.get("title")
        raw_line = anomaly.get("metadata", {}).get("raw_line")
        if raw_line and raw_line not in examples[anomaly_id]:
            examples[anomaly_id].append(raw_line.strip())
            if len(examples[anomaly_id]) >= 3:
                continue
    return examples


def generate_report_cards():
    base_dir = Path(__file__).parent
    raw_path = base_dir / "raw_anomalies.json"
    report_path = base_dir / "report_cards.md"

    if not raw_path.is_file():
        raise FileNotFoundError(f"Raw anomalies file not found: {raw_path}")

    anomalies = _load_anomalies(raw_path)
    total = len(anomalies)
    type_counter = _group_counts(anomalies, "id")
    severity_counter = _group_counts(anomalies, "severity")
    source_counter = _group_counts(anomalies, "source")
    examples = _best_examples(anomalies)

    sorted_types = sorted(
        type_counter.items(),
        key=lambda kv: (-kv[1], kv[0] or ""),
    )

    lines = ["# Anomaly Report Cards", f"**Total anomalies detected:** {total}", ""]
    lines.append("## Severity summary")
    for severity, count in sorted(
        severity_counter.items(), key=lambda kv: DEFAULT_SEVERITY_ORDER.get(kv[0], 99)
    ):
        lines.append(f"- **{severity.title()}**: {count}")
    lines.append("")

    lines.append("## Source summary")
    for source, count in sorted(
        source_counter.items(), key=lambda kv: (-kv[1], kv[0] or "")
    ):
        lines.append(f"- **{source or 'unknown'}**: {count}")
    lines.append("")

    for anomaly_id, count in sorted_types:
        matching = [
            a for a in anomalies if (a.get("id") or a.get("title")) == anomaly_id
        ]
        if not matching:
            continue
        anomaly = matching[0]
        title = anomaly.get("title") or anomaly_id or "Unknown anomaly"
        description = anomaly.get("description") or title
        severity = anomaly.get("severity", "medium")
        source = anomaly.get("source") or "unknown"
        fix = (
            SUGGESTED_FIXES.get(anomaly_id)
            or SUGGESTED_FIXES.get(title)
            or "Review the log entry and apply appropriate remediation."
        )

        lines.extend(
            [
                "---",
                f"## {title}",
                f"**Occurrences:** {count}",
                f"**Severity:** {severity.title()}",
                f"**Source:** {source}",
                f"**Description:** {description}",
                f"**Recommended Fix:** {fix}",
                "",
            ]
        )

        sample_lines = examples.get(anomaly_id, [])
        if sample_lines:
            lines.append("**Sample log entries:**")
            for sample in sample_lines:
                lines.append("```text")
                lines.append(sample)
                lines.append("```")
            lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return report_path


def generate_final_report():
    base_dir = Path(__file__).parent
    raw_path = base_dir / "raw_anomalies.json"
    report_path = base_dir / "final_report.md"

    if not raw_path.is_file():
        raise FileNotFoundError(f"Raw anomalies file not found: {raw_path}")

    anomalies = _load_anomalies(raw_path)
    if not anomalies:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(
                "# Telemetry Analysis Final Report\n\nNo anomalies were detected.\n"
            )
        return report_path

    total = len(anomalies)
    unique_types = len({(a.get("id") or a.get("title")) for a in anomalies})
    severity_counter = _group_counts(anomalies, "severity")
    source_counter = _group_counts(anomalies, "source")
    top_types = Counter((a.get("id") or a.get("title")) for a in anomalies)
    examples = _best_examples(anomalies)

    lines = [
        "# Telemetry Analysis Final Report",
        "",
        "## Executive Summary",
        f"- Total anomalies detected: **{total}**",
        f"- Unique anomaly types: **{unique_types}**",
        "",
    ]
    lines.append("## Severity distribution")
    for severity, count in sorted(
        severity_counter.items(), key=lambda kv: DEFAULT_SEVERITY_ORDER.get(kv[0], 99)
    ):
        lines.append(f"- **{severity.title()}**: {count}")
    lines.append("")

    lines.append("## Source distribution")
    for source, count in sorted(
        source_counter.items(), key=lambda kv: (-kv[1], kv[0] or "")
    ):
        lines.append(f"- **{source or 'unknown'}**: {count}")
    lines.append("")

    lines.append("## Top anomaly types")
    for anomaly_id, count in top_types.most_common(10):
        lines.append(f"- **{anomaly_id or 'unknown'}**: {count}")
    lines.append("")

    lines.append("## Detailed findings")
    for anomaly_id, count in top_types.most_common(10):
        matching = [
            a for a in anomalies if (a.get("id") or a.get("title")) == anomaly_id
        ]
        anomaly = matching[0]
        title = anomaly.get("title") or anomaly_id or "Unknown anomaly"
        description = anomaly.get("description") or title
        severity = anomaly.get("severity", "medium")
        source = anomaly.get("source") or "unknown"
        fix = (
            SUGGESTED_FIXES.get(anomaly_id)
            or SUGGESTED_FIXES.get(title)
            or "Review the log entry and apply appropriate remediation."
        )

        lines.extend(
            [
                "---",
                f"### {title}",
                f"- **Occurrences:** {count}",
                f"- **Severity:** {severity.title()}",
                f"- **Source:** {source}",
                f"- **Description:** {description}",
                f"- **Recommended Fix:** {fix}",
                "",
            ]
        )

        sample_lines = examples.get(anomaly_id, [])
        if sample_lines:
            lines.append("**Sample logs:**")
            for sample in sample_lines:
                lines.append("```text")
                lines.append(sample)
                lines.append("```")
            lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return report_path


if __name__ == "__main__":
    generate_report_cards()
    generate_final_report()
