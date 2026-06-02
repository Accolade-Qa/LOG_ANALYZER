import json
import os
import urllib.request

def generate_ai_summary():
    with open("reports/raw_anomalies.json") as f:
        anomalies = json.load(f)

    # Deduplicate and count anomalies to save tokens and improve prompt clarity
    unique_anomalies = list(set(anomalies))
    counts = {item: anomalies.count(item) for item in unique_anomalies}
    anomalies_summary = "\n".join([f"- {item} (occurred {count} times)" for item, count in counts.items()])

    prompt = f"""
Analyze telemetry anomalies:

{anomalies_summary}

Tasks:
1. Summarize issues
2. Predict root causes
3. Suggest fixes
"""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    
    req = urllib.request.Request(
        url, 
        data=json.dumps(data).encode("utf-8"), 
        headers=headers, 
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            summary = res_data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Failed to query Gemini API: {e}")
        summary = f"# Telemetry Analysis Summary\n\nFailed to fetch AI summary. Errors detected:\n{anomalies_summary}"

    with open("reports/ai_summary.md", "w") as f:
        f.write(summary)

