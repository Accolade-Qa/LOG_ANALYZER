"""
Main FastAPI Server & WebSocket Live Telemetry Engine.
Integrates the reactive multi-agent blackboard, log ingestion stream, and static dashboard UI.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config_loader import config
from engine.reactive_bus import blackboard
from llm.agentic_engine import set_active_log_path
from web.ws_hub import ws_hub
from web.stream_bridge import stream_bridge

# Route imports
from web.routes.telemetry import router as telemetry_router
from web.routes.logs import router as logs_router
from web.routes.copilot import router as copilot_router
from web.routes.fota import router as fota_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: register event loop with stream bridge and init active log."""
    loop = asyncio.get_running_loop()
    stream_bridge.set_event_loop(loop)

    # Set default log file if configured
    default_log = config.get("paths", {}).get("default_log_file")
    if default_log:
        p = Path(__file__).parent.parent / default_log
        if p.exists():
            set_active_log_path(str(p.resolve()))

    yield

    # Clean shutdown of streaming thread
    stream_bridge.stop()


app = FastAPI(
    title="Automotive Telemetry Workbench",
    description="Interactive Live Telemetry, Diagnostic HUD & Copilot for AIS-140 TCUs",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for local integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST Routers
app.include_router(telemetry_router)
app.include_router(logs_router)
app.include_router(copilot_router)
app.include_router(fota_router)


# ------------------------------------------------------------------------------
# WebSocket Real-Time Telemetry Stream
# ------------------------------------------------------------------------------
@app.websocket("/ws/live-stream")
async def websocket_live_stream(websocket: WebSocket):
    """
    Bi-directional real-time telemetry stream.
    Pushes batched log lines, blackboard deltas, and stream metrics at up to 60 FPS.
    """
    await ws_hub.connect(websocket)
    try:
        # Push initial state handshake
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "data": {
                "blackboard": blackboard.get_snapshot(),
                "status": stream_bridge.get_status(),
                "client_count": ws_hub.client_count
            }
        })

        # Keep connection open and handle client-sent actions
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "ping":
                await websocket.send_json({"type": "PONG"})
            elif action == "pause":
                stream_bridge.pause()
            elif action == "resume":
                stream_bridge.resume()
            elif action == "stop":
                stream_bridge.stop()

    except WebSocketDisconnect:
        await ws_hub.disconnect(websocket)
    except Exception:
        await ws_hub.disconnect(websocket)


# ------------------------------------------------------------------------------
# Static Files & Frontend Mount
# ------------------------------------------------------------------------------
static_dir = Path(__file__).parent / "static"
if not static_dir.exists():
    static_dir.mkdir(parents=True, exist_ok=True)

app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Entry point to launch the uvicorn web server."""
    import uvicorn
    uvicorn.run("web.api_server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server()
