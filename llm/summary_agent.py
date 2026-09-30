"""
Automotive AI Summary & Root Cause Synthesis Agent.
Integrates the AutomotiveDiagnosticAgent to generate comprehensive
root cause analyses and QA troubleshooting guides.
"""

import json
from pathlib import Path

from config_loader import config
from llm.agentic_engine import AutomotiveDiagnosticAgent


def generate_ai_summary(log_path=None):
    """
    Generate an AI-powered root cause synthesis and tester troubleshooting plan
    for detected multi-domain automotive anomalies using Agentic AI reasoning.
    """
    base_dir = Path(__file__).parent.parent
    raw_path = base_dir / config["paths"]["raw_anomalies_json"]
    ai_summary_path = base_dir / config["paths"]["ai_summary_md"]

    if not raw_path.exists():
        return ""

    try:
        with open(raw_path, "r", encoding="utf-8") as f:
            anomalies = json.load(f)
    except Exception:
        anomalies = []

    agent = AutomotiveDiagnosticAgent(log_path=log_path)
    summary_text = agent.run_agentic_triage(anomalies)

    ai_summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ai_summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    return summary_text
