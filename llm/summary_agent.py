"""
Automotive AI Summary & Root Cause Synthesis Agent.
Integrates the AutomotiveDiagnosticAgent to generate comprehensive
root cause analyses and QA troubleshooting guides.
"""

import json
from pathlib import Path

from config_loader import config
from llm.agentic_engine import AutomotiveDiagnosticAgent


def generate_ai_summary(log_path=None, discovered_anomalies=None):
    """
    Generate a Level 4 autonomous AI root cause synthesis and QA troubleshooting plan
    investigating both explicit anomaly sessions and unsupervised discovered anomalies.
    """
    base_dir = Path(__file__).parent.parent
    raw_path = base_dir / config["paths"]["raw_anomalies_json"]
    ai_summary_path = base_dir / config["paths"]["ai_summary_md"]

    anomalies = []
    if raw_path.exists():
        try:
            with open(raw_path, "r", encoding="utf-8") as f:
                anomalies = json.load(f)
        except Exception:
            anomalies = []

    agent = AutomotiveDiagnosticAgent(log_path=log_path)
    summary_text = agent.run_agentic_triage(anomalies, discovered_anomalies=discovered_anomalies)

    ai_summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ai_summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    return summary_text
