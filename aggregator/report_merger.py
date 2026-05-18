import json

def merge_reports():
    try:
        with open('reports/raw_anomalies.json') as f:
            anomalies = json.load(f)
    except:
        anomalies = []

    with open('reports/final_report.md', 'w') as f:
        f.write('# Telemetry Report\n\n')
        for item in anomalies:
            f.write(f'- {item}\n')
