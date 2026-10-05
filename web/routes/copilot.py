"""
Interactive Automotive Copilot REST Endpoints.
Connects browser chat UI to Level 4 Autonomous Copilot with dynamic AFC function tools.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config_loader import config
from engine.reactive_bus import blackboard
from llm.agentic_engine import AutomotiveDiagnosticAgent, CURRENT_LOG_PATH

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])


class CopilotQueryRequest(BaseModel):
    query: str
    context: Optional[str] = None


@router.post("/query")
def ask_copilot(req: CopilotQueryRequest):
    """
    Submit a technical question to the Automotive Diagnostic Copilot.
    The agent uses AFC (Automatic Function Calling) to inspect raw log lines,
    verify DTC occurrences, and audit state FOTA or CIP1 configurations.
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 1. Fetch current anomalies for context
    raw_path = Path(__file__).parent.parent.parent / config.get("paths", {}).get("raw_anomalies_json", "artifacts/raw_anomalies.json")
    anomalies: List[Dict[str, Any]] = []
    if raw_path.exists():
        try:
            with open(raw_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    anomalies = loaded
        except Exception:
            pass

    # 2. Instantiate agent with current active log
    agent = AutomotiveDiagnosticAgent(log_path=CURRENT_LOG_PATH)

    # 3. Execute query
    try:
        response_markdown = agent.answer_copilot_query(
            user_question=req.query.strip(),
            anomalies=anomalies
        )
        return {
            "query": req.query,
            "response": response_markdown,
            "active_log": CURRENT_LOG_PATH,
            "anomaly_count": len(anomalies)
        }
    except Exception as e:
        return {
            "query": req.query,
            "response": f"⚠️ **Copilot Diagnostic Warning:** {str(e)}",
            "active_log": CURRENT_LOG_PATH,
            "anomaly_count": len(anomalies)
        }
