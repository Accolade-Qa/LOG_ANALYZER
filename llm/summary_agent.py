import json
import os
import urllib.request


def _render_anomaly_text(anomaly):
    if isinstance(anomaly, dict):
        return anomaly.get("description") or anomaly.get("title") or str(anomaly)
    return str(anomaly)


def generate_ai_summary():
    with open("reports/raw_anomalies.json", "r", encoding="utf-8") as f:
        anomalies = json.load(f)

    if not anomalies:
        summary = "# Telemetry Analysis Summary\n\nNo anomalies were detected."
    else:
        unique = {}
        for anomaly in anomalies:
            text = _render_anomaly_text(anomaly)
            unique[text] = unique.get(text, 0) + 1

        anomalies_summary = "\n".join(
            [f"- {text} (occurred {count} times)" for text, count in unique.items()]
        )

        summary = f"""
Analyze telemetry anomalies:

{anomalies_summary}

Tasks:
1. Summarize issues
2. Predict root causes
3. Suggest fixes
"""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        with open("reports/ai_summary.md", "w", encoding="utf-8") as f:
            f.write(summary)
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": summary}]}]}

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
        print(f"Failed to query Gemini API: {e}")
        summary_text = summary

    with open("reports/ai_summary.md", "w", encoding="utf-8") as f:
        f.write(summary_text)
