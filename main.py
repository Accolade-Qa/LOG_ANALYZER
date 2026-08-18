import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

load_dotenv()

import argparse
from agents.battery_agent import battery_agent
from agents.can_agent import can_agent
from agents.gps_agent import gps_agent
from agents.mqtt_agent import mqtt_agent
from agents.net_agent import net_agent
from llm.summary_agent import generate_ai_summary
from parser.gps_log_reader import process_log
from parser.live_stream_reader import stream_growing_file, stream_uart_port
from reports.anomaly_collector import clear_anomalies, save_anomalies
from reports.report_generator import (
    generate_final_report,
    generate_html_dashboard,
    generate_report_cards,
)

from config_loader import config

ALL_AGENTS = [gps_agent, battery_agent, can_agent, net_agent, mqtt_agent]


def main():
    parser = argparse.ArgumentParser(
        description="Automated Telemetry Log Analyzer with Stateful Session & Live Ingestion"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["file", "tail", "uart"],
        default="file",
        help="Ingestion mode: file (static log file), tail (growing log file), or uart (live COM port)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to specific log file to analyze",
    )
    parser.add_argument(
        "--port",
        type=str,
        default=config["uart"]["default_port"],
        help=f"UART Serial Port (default: {config['uart']['default_port']})",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=config["uart"]["default_baudrate"],
        help=f"UART Serial Baud Rate (default: {config['uart']['default_baudrate']})",
    )
    args = parser.parse_args()

    # Reset anomaly collector state for clean run
    clear_anomalies()

    if args.mode == "uart":
        print(f"Starting Live Hardware UART Analysis on port {args.port} @ {args.baud} baud...")
        stream_uart_port(port=args.port, baudrate=args.baud, timeout=config["uart"]["timeout"])

    elif args.mode == "tail":
        if not args.log_file:
            raise ValueError("--log-file is required when using --mode tail")
        target_path = Path(args.log_file)
        if not target_path.is_absolute():
            target_path = BASE_DIR / args.log_file
        print(f"Starting Live Tailing on growing file: {target_path}")
        stream_growing_file(
            str(target_path),
            poll_interval=config["live_tail"]["poll_interval"],
            stop_on_idle_sec=config["live_tail"]["stop_on_idle_sec"],
        )

    else:
        # Standard static file mode
        LOG_DIR = BASE_DIR / config["paths"]["log_dir"]
        target_files = []

        if args.log_file:
            target_path = Path(args.log_file)
            if not target_path.is_absolute():
                target_path = BASE_DIR / args.log_file
            if target_path.exists():
                target_files = [target_path]
            else:
                raise FileNotFoundError(f"Specified log file not found: {target_path}")
        else:
            # Default from config or REL18_TO_REL24.log if available
            rel_file = BASE_DIR / config["paths"]["default_log_file"]
            if rel_file.exists():
                target_files = [rel_file]
            elif LOG_DIR.exists():
                target_files = sorted([f for f in LOG_DIR.glob("*.log") if f.is_file()])

        if not target_files:
            raise FileNotFoundError(f"No log files found in {LOG_DIR}")

        print(f"Starting telemetry analysis on {len(target_files)} log file(s)...")
        for log_path in target_files:
            print(f"Processing log file: {log_path.name} ({log_path.stat().st_size / (1024*1024):.2f} MB)...")
            process_log(str(log_path))

    # Finalize any unrecovered open sessions at end of run
    for agent in ALL_AGENTS:
        agent.finalize_open_sessions()

    # Persist anomalies to raw_anomalies.json
    save_anomalies()

    # Generate all reports
    report_cards_path = generate_report_cards()
    final_report_path = generate_final_report()
    dashboard_html_path = generate_html_dashboard()

    # Generate AI summary
    generate_ai_summary()
    ai_summary_path = BASE_DIR / config["paths"]["ai_summary_md"]

    print("\nTelemetry analysis completed successfully!")
    print("Generated Artifacts:")
    print(f" - Raw Anomalies JSON: {BASE_DIR / config['paths']['raw_anomalies_json']}")
    print(f" - Report Cards:       {report_cards_path}")
    print(f" - Final Report:        {final_report_path}")
    print(f" - AI Summary:         {ai_summary_path}")
    print(f" - HTML Dashboard:     {dashboard_html_path}")



if __name__ == "__main__":
    main()
