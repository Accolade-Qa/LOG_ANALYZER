import json
import os
import ssl
import time
import urllib.error
import urllib.request
import warnings
from collections import Counter
from pathlib import Path

from config_loader import config

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


def _render_anomaly_text(anomaly):
    if isinstance(anomaly, dict):
        return anomaly.get("description") or anomaly.get("title") or str(anomaly)
    return str(anomaly)


def generate_ai_summary():
    """
    Generate an AI-powered root cause synthesis and tester troubleshooting plan
    for detected GPS anomalies using Gemini AI (or local expert synthesis).
    """
    base_dir = Path(__file__).parent.parent
    raw_path = base_dir / config["paths"]["raw_anomalies_json"]
    ai_summary_path = base_dir / config["paths"]["ai_summary_md"]

    if not raw_path.exists():
        return ""

    with open(raw_path, "r", encoding="utf-8") as f:
        anomalies = json.load(f)

    if not anomalies:
        summary_text = (
            "### GPS Subsystem Status: Healthy\n\nNo telemetry anomalies detected during log execution."
        )
    else:
        unique = Counter()
        for anomaly in anomalies:
            text = _render_anomaly_text(anomaly)
            unique[text] += 1

        top_anomalies = unique.most_common(25)
        anomalies_summary = "\n".join(
            [f"- **{text}**: {count} occurrence(s)" for text, count in top_anomalies]
        )

        fallback_report = f"""### AI Root Cause Analysis & QA Troubleshooting Guide

#### Executive Summary
During GPS log analysis, **{len(anomalies)}** anomaly event(s) across **{len(unique)}** distinct pattern(s) were identified.

#### Detected Anomaly Breakdown
{anomalies_summary}

#### Technical Root Cause Analysis
1. **Satellite Acquisition & RF Antenna Signal Loss (`GPS_KN_001`)**:
   - **Why It Happened**: The GPS receiver module is not receiving satellite RF signals (`SAT=0, FIX=0`). Common causes include coaxial cable disconnection, LNA power supply drop, indoor testing without clear sky view, or cold-boot satellite acquisition timeouts.
   - **QA Action**: Check antenna SMA connection, measure LNA supply voltage (~3.3V), and re-test with direct sky visibility.

2. **Visible Satellites Without Navigation Fix (`GPS_KN_002`)**:
   - **Why It Happened**: Satellites are visible (`SAT>=4`), but the GNSS engine failed to compute a 3D position lock (`FIX=0`). Indicates multipath reflections, stale ephemeris data, or firmware initialization latency.
   - **QA Action**: Check HDOP values, verify GNSS ephemeris update interval in firmware, and monitor cold-boot stabilization timers.

3. **Invalid Zero Coordinates (`GPS_KN_003`)**:
   - **Why It Happened**: Fix quality bit was set to 1, but Latitude/Longitude coordinates were unpopulated (`0.000000`). Indicates C-struct serialization error or UART parser offset mismatch.
   - **QA Action**: Inspect UART buffer offset in C-firmware NMEA parser and check binary telemetry packet field alignment.

4. **Low Satellite Count (`GPS_KN_004`)**:
   - **Why It Happened**: Satellite count dropped below the 4-satellite threshold required for reliable positioning.
   - **QA Action**: Verify physical sky visibility and check for adjacent cellular RF interference lines.
"""

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        ai_summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ai_summary_path, "w", encoding="utf-8") as f:
            f.write(fallback_report)
        return fallback_report

    model_name = config["ai"].get("model", "gemini-3.6-flash")
    prompt = (
        "You are an expert GPS Hardware & Telemetry QA Engineer. Analyze the following detected GPS anomaly trace "
        "and generate a concise, professional Root Cause Analysis and QA Tester Inspection Guide:\n\n"
        f"{fallback_report}"
    )
    summary_text = None

    # Method 1: Official google-genai Python SDK with suppressed AFC warnings
    if genai is not None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                client = genai.Client(api_key=api_key)
                gen_config = types.GenerateContentConfig(tools=[]) if types else None
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=gen_config,
                )
                if response and response.text:
                    summary_text = response.text
        except Exception:
            pass  # Fail gracefully to REST client

    # Method 2: REST Client fallback
    if summary_text is None:
        url = config["ai"]["api_url"]
        if "?" not in url:
            url += f"?key={api_key}"
        else:
            url += f"&key={api_key}"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LOG_ANALYZER/1.0",
            "Connection": "close",
        }
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        ssl_context = ssl.create_default_context()

        for attempt in range(1, 3):
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, context=ssl_context, timeout=15) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    summary_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                    break
            except Exception:
                if attempt < 2:
                    time.sleep(1.0)

    if not summary_text:
        summary_text = fallback_report

    ai_summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ai_summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    return summary_text
