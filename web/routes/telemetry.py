"""
Telemetry, Blackboard, and Anomaly REST Endpoints
"""

import json
from pathlib import Path
from fastapi import APIRouter
from config_loader import config
from engine.reactive_bus import blackboard
from llm.agentic_engine import audit_telemetry_configuration
from web.stream_bridge import stream_bridge

router = APIRouter(prefix="/api", tags=["Telemetry"])


@router.get("/blackboard/snapshot")
def get_blackboard_snapshot():
    """Return the real-time vehicle blackboard snapshot."""
    return blackboard.get_snapshot()


@router.get("/telemetry/status")
def get_stream_status():
    """Return ingestion stream metrics and status."""
    return stream_bridge.get_status()


@router.get("/telemetry/audit-cip1")
def audit_cip1_endpoint(param: str = "cip1"):
    """Audit CIP1 parameter status (explicit vs dynamically inferred)."""
    result_text = audit_telemetry_configuration(param)
    return {"parameter": param, "audit_markdown": result_text}


@router.get("/anomalies")
def get_anomalies():
    """Retrieve detected anomalies from artifacts/raw_anomalies.json."""
    raw_path = Path(__file__).parent.parent.parent / config["paths"]["raw_anomalies_json"]
    if not raw_path.exists():
        return []
    try:
        with open(raw_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        return {"error": str(e)}
