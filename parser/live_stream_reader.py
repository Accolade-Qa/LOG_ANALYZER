import time
from parser.classifier import classify
from engine.dispatcher import dispatch

try:
    import serial
except ImportError:
    serial = None


def stream_growing_file(log_path, poll_interval=0.1, stop_on_idle_sec=None):
    """Tail a growing log file (tail -f behavior) in real-time."""
    print(f"Starting live tail on growing log file: {log_path}")
    line_num = 0
    idle_time = 0.0

    with open(log_path, "r", errors="ignore") as f:
        # Stream lines as they arrive
        while True:
            line = f.readline()
            if line:
                idle_time = 0.0
                line_num += 1
                event = classify(line, line_number=line_num)
                if event:
                    dispatch(event)
            else:
                time.sleep(poll_interval)
                idle_time += poll_interval
                if stop_on_idle_sec and idle_time >= stop_on_idle_sec:
                    print(f"No new lines for {stop_on_idle_sec} seconds. Stopping live tail.")
                    break


def stream_uart_port(port="COM3", baudrate=115200, timeout=1.0):
    """Stream live telemetry logs directly from physical hardware UART COM port."""
    if serial is None:
        raise ImportError(
            "pyserial package is required for UART streaming. Run: pip install pyserial"
        )

    print(f"Opening live UART hardware connection on {port} @ {baudrate} baud...")
    line_num = 0

    try:
        with serial.Serial(port=port, baudrate=baudrate, timeout=timeout) as ser:
            print(f"Successfully connected to UART {port}. Listening for live telemetry lines...")
            while ser.is_open:
                raw_bytes = ser.readline()
                if raw_bytes:
                    line = raw_bytes.decode("utf-8", errors="ignore").strip()
                    if line:
                        line_num += 1
                        event = classify(line, line_number=line_num)
                        if event:
                            print(f"[UART Realtime Event #{line_num}] Tagged: {event['type']}")
                            dispatch(event)
    except KeyboardInterrupt:
        print("\nUART stream stopped by user.")
    except Exception as e:
        print(f"UART Serial Port Error on {port}: {e}")
