import json
import os
import ssl
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from config_loader import config

try:
    from google import genai
except ImportError:
    genai = None


def _render_anomaly_text(anomaly):
    if isinstance(anomaly, dict):
        return anomaly.get("description") or anomaly.get("title") or str(anomaly)
    return str(anomaly)


def generate_ai_summary():
    base_dir = Path(__file__).parent.parent
    raw_path = base_dir / config["paths"]["raw_anomalies_json"]
    ai_summary_path = base_dir / config["paths"]["ai_summary_md"]

    if not raw_path.exists():
        return

    with open(raw_path, "r", encoding="utf-8") as f:
        anomalies = json.load(f)

    if not anomalies:
        summary_text = "# Telemetry AI Summary & Root Cause Analysis\n\nNo anomalies were detected during log analysis."
    else:
        unique = Counter()
        by_source = Counter()
        for anomaly in anomalies:
            text = _render_anomaly_text(anomaly)
            source = anomaly.get("source") or "General"
            unique[text] += 1
            by_source[source] += 1

        top_anomalies = unique.most_common(25)
        anomalies_summary = "\n".join(
            [f"- **{text}**: {count} occurrence(s)" for text, count in top_anomalies]
        )
        source_summary = "\n".join(
            [f"- **{src}**: {cnt} event(s)" for src, cnt in by_source.most_common()]
        )

        fallback_report = f"""# Telemetry AI Summary & Root Cause Analysis

                    ## Executive Synthesis
                    During telemetry log analysis, **{len(anomalies)}** anomaly event(s) across **{len(unique)}** distinct pattern(s) were identified.

                    ### Subsystem Impact Breakdown
                    {source_summary}

                    ### Key Anomaly Observations (Top 25 Most Frequent)
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

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        ai_summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ai_summary_path, "w", encoding="utf-8") as f:
            f.write(fallback_report)
        return

    model_name = config["ai"].get("model", "gemini-3.6-flash")
    prompt = f"Analyze the following telemetry anomaly summary and produce a structured root cause analysis and action plan:\n\n{fallback_report}"
    summary_text = None

    # Method 1: Official google-genai Python SDK
    if genai is not None:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            if response and response.text:
                summary_text = response.text
        except Exception as e:
            print(
                f"google-genai SDK call failed ({e}). Falling back to REST HTTPS client..."
            )

    # Method 2: Fallback REST Client with SSL context & retry loop
    if summary_text is None:
        url = config["ai"]["api_url"]
        if "?" not in url:
            url += f"?key={api_key}"
        else:
            url += f"&key={api_key}"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LOG_ANALYZER/1.0",
            "Connection": "close",
        }
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        ssl_context = ssl.create_default_context()
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(
                    req, context=ssl_context, timeout=60
                ) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    summary_text = res_data["candidates"][0]["content"]["parts"][0][
                        "text"
                    ]
                    break
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(1.0 * attempt)
                else:
                    print(
                        f"Failed to query Gemini API after {max_retries} attempt(s) ({e}). Writing local structured synthesis."
                    )
                    summary_text = fallback_report

    ai_summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ai_summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)
