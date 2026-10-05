"""
FOTA State Migration and AIS-140 Compliance REST Endpoints.
"""

from typing import Optional
from fastapi import APIRouter
from engine.reactive_bus import blackboard
from llm.agentic_engine import validate_state_fota_migration, CURRENT_LOG_PATH

router = APIRouter(prefix="/api/fota", tags=["FOTA"])


@router.get("/validate-state")
def audit_fota_state(log_path: Optional[str] = None):
    """
    Validate AIS-140 Indian State Government FOTA campaign migration.
    Checks firmware download, block integrity, reboot, and dynamic state server IP/Port reconfiguration.
    """
    target = log_path or CURRENT_LOG_PATH
    report = validate_state_fota_migration(target)
    snap = blackboard.get_subsystem_view("fota")
    
    return {
        "active_log": target,
        "fota_blackboard": snap,
        "report_markdown": report
    }


@router.get("/status")
def get_fota_status():
    """Get active FOTA subsystem state from blackboard."""
    fota_snap = blackboard.get_subsystem_view("fota")
    server_snap = blackboard.get_subsystem_view("server")
    return {
        "fota": fota_snap,
        "server": server_snap
    }
