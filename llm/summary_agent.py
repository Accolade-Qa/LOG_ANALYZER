import json
import os
import urllib.request
from pathlib import Path



def _render_anomaly_text(anomaly):
    if isinstance(anomaly, dict):
        return anomaly.get("description") or anomaly.get("title") or str(anomaly)
    return str(anomaly)


def generate_ai_summary():
    raw_path = Path(__file__).parent.parent / "artifacts" / "raw_anomalies.json"
    ai_summary_path = Path(__file__).parent.parent / "artifacts" / "ai_summary.md"


    if not raw_path.exists():
        return

    with open(raw_path, "r", encoding="utf-8") as f:
        anomalies = json.load(f)

    if not anomalies:
        summary_text = "# Telemetry AI Summary & Root Cause Analysis\n\nNo anomalies were detected during log analysis."
    else:
        unique = {}
        by_source = {}
        for anomaly in anomalies:
            text = _render_anomaly_text(anomaly)
            source = anomaly.get("source") or "General"
            unique[text] = unique.get(text, 0) + 1
            by_source[source] = by_source.get(source, 0) + 1

        anomalies_summary = "\n".join(
            [f"- **{text}**: {count} occurrence(s)" for text, count in unique.items()]
        )
        source_summary = "\n".join(
            [f"- **{src}**: {cnt} event(s)" for src, cnt in by_source.items()]
        )

        fallback_report = f"""# Telemetry AI Summary & Root Cause Analysis

## Executive Synthesis
During telemetry log analysis, **{len(anomalies)}** anomaly event(s) across **{len(unique)}** distinct pattern(s) were identified.

### Subsystem Impact Breakdown
{source_summary}

### Key Anomaly Observations
{anomalies_summary}

## Predictive Root Cause Analysis
1. **Satellite Acquisition & Antenna Losses (GPS)**:
   - Frequent `GPS_KN_001` (SAT=0, FIX=0) or low satellite count indicates signal occlusion, poor antenna placement, or cold-boot satellite search timeouts during boot sequence.
2. **Network & Cellular Registration Delays (NET/GSM)**:
   - `NET_KN_001` (Poor CSQ) and `NET_KN_002`/`003` (Registration Failures) suggest weak cellular tower coverage or SIM module attachment latency.
3. **Power Subsystem Integrity (BATTERY)**:
   - Voltage drops or missing critical analog channels point to power line noise or low backup battery state during high-draw operations (like cellular TX bursts).

## Recommended Remediation Steps
- **Hardware/Antenna**: Re-orient GPS antenna with clear sky view and verify RF line attenuation.
- **Cellular Protocol Stack**: Increase network registration retry timers and check APN/SIM credentials.
- **Power Optimization**: Verify internal battery charging voltage and decouple analog sensor supply.
"""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        ai_summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ai_summary_path, "w", encoding="utf-8") as f:
            f.write(fallback_report)
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    prompt = f"Analyze the following telemetry anomaly summary and produce a structured root cause analysis and action plan:\n\n{fallback_report}"
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            summary_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Failed to query Gemini API ({e}). Writing local structured synthesis.")
        summary_text = fallback_report

    ai_summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ai_summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

