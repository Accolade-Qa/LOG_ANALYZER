"""
Async Stream Bridge for Live Telemetry Ingestion (File Tail, UART, Static File).
Connects incoming frames to the classification pipeline, reactive blackboard, and WebSocket broadcast hub.
"""

import asyncio
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from parser.classifier import classify
from engine.dispatcher import dispatch
from engine.reactive_bus import blackboard
from web.ws_hub import ws_hub

try:
    import serial
except ImportError:
    serial = None


class StreamBridge:
    """Bridges background thread ingestion to the async FastAPI WebSocket stream."""

    def __init__(self):
        self.is_running: bool = False
        self.is_paused: bool = False
        self.current_mode: str = "idle"  # "file", "tail", "uart", "idle"
        self.current_target: str = ""
        self.total_lines: int = 0
        self.lines_per_sec: int = 0
        self._lines_since_last_stat: int = 0
        self._last_stat_time: float = time.time()
        
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Batch buffer for smooth 60 FPS delivery
        self._frame_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = threading.Lock()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def get_status(self) -> Dict[str, Any]:
        """Return live ingestion status snapshot."""
        now = time.time()
        elapsed = now - self._last_stat_time
        if elapsed >= 1.0:
            self.lines_per_sec = int(self._lines_since_last_stat / elapsed)
            self._lines_since_last_stat = 0
            self._last_stat_time = now

        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "mode": self.current_mode,
            "target": self.current_target,
            "total_lines": self.total_lines,
            "lines_per_sec": self.lines_per_sec,
        }

    def start_file_stream(self, log_path: str, playback_speed: float = 0.001):
        """Stream a static log file line-by-line simulating live stream or fast feed."""
        self.stop()
        self._stop_event.clear()
        self.is_running = True
        self.is_paused = False
        self.current_mode = "file"
        self.current_target = Path(log_path).name
        self.total_lines = 0

        self._thread = threading.Thread(
            target=self._run_file_stream,
            args=(log_path, playback_speed),
            daemon=True
        )
        self._thread.start()

    def start_tail_stream(self, log_path: str, poll_interval: float = 0.05):
        """Continuously tail an actively growing log file ('tail -f')."""
        self.stop()
        self._stop_event.clear()
        self.is_running = True
        self.is_paused = False
        self.current_mode = "tail"
        self.current_target = Path(log_path).name
        self.total_lines = 0

        self._thread = threading.Thread(
            target=self._run_tail_stream,
            args=(log_path, poll_interval),
            daemon=True
        )
        self._thread.start()

    def start_uart_stream(self, port: str = "COM3", baudrate: int = 115200, timeout: float = 1.0):
        """Stream live telemetry frames from physical hardware UART COM port."""
        if serial is None:
            raise RuntimeError("pyserial is required for UART hardware streaming.")

        self.stop()
        self._stop_event.clear()
        self.is_running = True
        self.is_paused = False
        self.current_mode = "uart"
        self.current_target = f"{port} @ {baudrate}"
        self.total_lines = 0

        self._thread = threading.Thread(
            target=self._run_uart_stream,
            args=(port, baudrate, timeout),
            daemon=True
        )
        self._thread.start()

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        """Stop any active background ingestion thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.is_running = False
        self.is_paused = False
        self.current_mode = "idle"

    # --------------------------------------------------------------------------
    # Ingestion Worker Implementations
    # --------------------------------------------------------------------------
    def _run_file_stream(self, log_path: str, speed: float):
        try:
            with open(log_path, "r", errors="ignore") as f:
                for line_idx, raw_line in enumerate(f, start=1):
                    if self._stop_event.is_set():
                        break
                    while self.is_paused and not self._stop_event.is_set():
                        time.sleep(0.1)

                    self._process_single_line(raw_line, line_idx)
                    if speed > 0:
                        time.sleep(speed)
        finally:
            self._flush_buffer_now()
            self.is_running = False

    def _run_tail_stream(self, log_path: str, poll_interval: float):
        try:
            line_idx = 0
            with open(log_path, "r", errors="ignore") as f:
                # Seek to end or read from beginning if requested
                while not self._stop_event.is_set():
                    while self.is_paused and not self._stop_event.is_set():
                        time.sleep(0.1)

                    line = f.readline()
                    if line:
                        line_idx += 1
                        self._process_single_line(line, line_idx)
                    else:
                        self._flush_buffer_now()
                        time.sleep(poll_interval)
        finally:
            self._flush_buffer_now()
            self.is_running = False

    def _run_uart_stream(self, port: str, baudrate: int, timeout: float):
        try:
            with serial.Serial(port=port, baudrate=baudrate, timeout=timeout) as ser:
                line_idx = 0
                while ser.is_open and not self._stop_event.is_set():
                    while self.is_paused and not self._stop_event.is_set():
                        time.sleep(0.1)

                    raw_bytes = ser.readline()
                    if raw_bytes:
                        line = raw_bytes.decode("utf-8", errors="ignore").strip()
                        if line:
                            line_idx += 1
                            self._process_single_line(line, line_idx)
        except Exception as e:
            print(f"[StreamBridge UART Error: {e}]")
        finally:
            self._flush_buffer_now()
            self.is_running = False

    def _process_single_line(self, line: str, line_idx: int):
        clean_line = line.strip()
        if not clean_line:
            return

        self.total_lines += 1
        self._lines_since_last_stat += 1

        # 1. Parse and dispatch through reactive domain agents
        event = classify(clean_line, line_number=line_idx)
        if event:
            dispatch(event)

        # 2. Extract tag for UI syntax coloring
        tag = event.get("type", "UNKNOWN") if event else "RAW"

        frame = {
            "num": line_idx,
            "tag": tag,
            "raw": clean_line,
        }

        with self._buffer_lock:
            self._frame_buffer.append(frame)
            if len(self._frame_buffer) >= 50:
                self._flush_buffer_locked()

    def _flush_buffer_now(self):
        with self._buffer_lock:
            if self._frame_buffer:
                self._flush_buffer_locked()

    def _flush_buffer_locked(self):
        if not self._frame_buffer or not self._loop:
            return

        batch_frames = list(self._frame_buffer)
        self._frame_buffer.clear()
        snap = blackboard.get_snapshot()

        payload = {
            "type": "TELEMETRY_BATCH",
            "data": {
                "lines": batch_frames,
                "blackboard": snap,
                "status": self.get_status(),
            }
        }

        # Schedule thread-safe broadcast in the async loop
        asyncio.run_coroutine_threadsafe(ws_hub.broadcast_json(payload), self._loop)


stream_bridge = StreamBridge()
