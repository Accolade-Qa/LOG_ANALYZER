def generate_ai_summary():
    summary = '''# AI Summary

- MQTT instability observed
- GPS invalid coordinates found
- CAN speed anomaly detected
'''

    with open('reports/ai_summary.md', 'w') as f:
        f.write(summary)
