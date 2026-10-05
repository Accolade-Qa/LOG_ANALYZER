"""
Log Management, Serial Port Detection, and Stream Control REST Endpoints.
"""

import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config_loader import config
from web.stream_bridge import stream_bridge
from llm.agentic_engine import set_active_log_path

try:
    import serial.tools.list_ports
except ImportError:
    serial = None

router = APIRouter(prefix="/api", tags=["Logs & Streaming"])


class StreamStartRequest(BaseModel):
    mode: str  # "file", "tail", "uart"
    source: str  # filename (in logs/) or full path, or COM port
    speed: Optional[float] = 0.001
    baudrate: Optional[int] = 115200


@router.get("/logs/list")
def list_logs():
    """List available log files in the configured logs directory."""
    logs_dir = Path(config.get("paths", {}).get("logs_dir", "logs"))
    if not logs_dir.is_absolute():
        logs_dir = Path(__file__).parent.parent.parent / logs_dir

    if not logs_dir.exists():
        return []

    files = []
    for f in logs_dir.glob("*.log"):
        stat = f.stat()
        files.append({
            "name": f.name,
            "path": str(f.resolve()),
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": stat.st_mtime
        })

    # Sort newest first
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files


@router.get("/serial/ports")
def list_serial_ports():
    """List available physical and virtual serial COM ports."""
    ports = []
    try:
        import serial.tools.list_ports
        for port, desc, hwid in serial.tools.list_ports.comports():
            ports.append({
                "port": port,
                "description": desc,
                "hwid": hwid
            })
    except Exception as e:
        pass
    return ports


@router.post("/stream/start")
def start_stream(req: StreamStartRequest):
    """Start streaming telemetry from file, tail, or UART."""
    mode = req.mode.lower()

    if mode in ("file", "tail"):
        target_path = Path(req.source)
        if not target_path.is_absolute():
            logs_dir = Path(__file__).parent.parent.parent / config.get("paths", {}).get("logs_dir", "logs")
            target_path = logs_dir / req.source

        if not target_path.exists():
            raise HTTPException(status_code=404, detail=f"Log file not found: {target_path}")

        # Set active path in agentic engine for LLM tools
        set_active_log_path(str(target_path))

        if mode == "file":
            stream_bridge.start_file_stream(str(target_path), playback_speed=req.speed or 0.001)
        else:
            stream_bridge.start_tail_stream(str(target_path))

        return {
            "status": "started",
            "mode": mode,
            "target": target_path.name,
            "full_path": str(target_path)
        }

    elif mode == "uart":
        try:
            stream_bridge.start_uart_stream(port=req.source, baudrate=req.baudrate or 115200)
            return {
                "status": "started",
                "mode": "uart",
                "target": req.source,
                "baudrate": req.baudrate or 115200
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported streaming mode: {req.mode}")


@router.post("/stream/pause")
def pause_stream():
    """Pause the current telemetry stream."""
    stream_bridge.pause()
    return {"status": "paused"}


@router.post("/stream/resume")
def resume_stream():
    """Resume a paused telemetry stream."""
    stream_bridge.resume()
    return {"status": "resumed"}


@router.post("/stream/stop")
def stop_stream():
    """Stop the active telemetry stream."""
    stream_bridge.stop()
    return {"status": "stopped"}


@router.get("/stream/status")
def get_status():
    """Get active telemetry stream ingestion status."""
    return stream_bridge.get_status()
