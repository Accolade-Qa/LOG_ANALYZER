import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

load_dotenv()

from agents import ALL_AGENTS
from config_loader import config
from engine.dispatcher import reset_all_agents
from engine.unsupervised_scanner import scan_unmodeled_anomalies
from llm.agentic_engine import AutomotiveDiagnosticAgent
from parser.gps_log_reader import process_log
from parser.live_stream_reader import stream_growing_file, stream_uart_port
from reports.anomaly_collector import clear_anomalies, save_anomalies
from reports.report_generator import generate_html_dashboard


def run_interactive_copilot(log_path=None):
    """Launch interactive Level 4 Autonomous Automotive Diagnostic Copilot CLI session."""
    raw_path = BASE_DIR / config["paths"]["raw_anomalies_json"]
    anomalies = []
    if raw_path.exists():
        try:
            with open(raw_path, "r", encoding="utf-8") as f:
                anomalies = json.load(f)
        except Exception:
            anomalies = []

    agent = AutomotiveDiagnosticAgent(log_path=log_path)
    print("\n" + "=" * 75)
    print("🤖 Level 4 Autonomous Automotive Telemetry Copilot (Interactive Mode)")
    print("Direct ReAct log search & multi-tool evidence grounding active.")
    print("Ask questions about anomalies, CAN timeouts, FOTA requests, or line events.")
    print("Type 'exit' or 'quit' to end session.")
    print("=" * 75 + "\n")

    while True:
        try:
            user_input = input("Copilot> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Ending Copilot session. Goodbye!")
                break
            
            print("\nAnalyzing telemetry context and executing dynamic log inspection tools...")
            answer = agent.answer_copilot_query(user_input, anomalies)
            print(f"\n{answer}\n")
            print("-" * 75)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting Copilot.")
            break


def main():
    parser = argparse.ArgumentParser(
        description="Level 4 Autonomous Agentic AI Automotive Telemetry & Log Analyzer"
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
    parser.add_argument(
        "--copilot",
        action="store_true",
        help="Launch interactive AI Diagnostic Copilot chat session after analysis",
    )
    args = parser.parse_args()

    # Reset anomaly collector and all reactive agents state for clean run
    clear_anomalies()
    reset_all_agents()

    analyzed_log_file = None

    if args.mode == "uart":
        print(f"Starting Live Hardware UART Analysis on port {args.port} @ {args.baud} baud...")
        if args.copilot:
            import threading
            uart_thread = threading.Thread(
                target=stream_uart_port,
                args=(args.port, args.baud, config["uart"]["timeout"]),
                daemon=True,
            )
            uart_thread.start()
            print(f"🚀 Live UART stream active on {args.port}! Launching live Copilot...")
            run_interactive_copilot()
            return
        else:
            stream_uart_port(port=args.port, baudrate=args.baud, timeout=config["uart"]["timeout"])

    elif args.mode == "tail":
        if not args.log_file:
            raise ValueError("--log-file is required when using --mode tail")
        target_path = Path(args.log_file)
        if not target_path.is_absolute():
            target_path = BASE_DIR / args.log_file
        print(f"Starting Live Tailing on growing file: {target_path}")
        analyzed_log_file = str(target_path)
        if args.copilot:
            import threading
            tail_thread = threading.Thread(
                target=stream_growing_file,
                args=(str(target_path),),
                kwargs={
                    "poll_interval": config["live_tail"]["poll_interval"],
                    "stop_on_idle_sec": None,
                },
                daemon=True,
            )
            tail_thread.start()
            print(f"🚀 Live log tailing active on {target_path.name}! Launching live Copilot...")
            run_interactive_copilot(log_path=analyzed_log_file)
            return
        else:
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
            rel_file = BASE_DIR / config["paths"]["default_log_file"]
            if rel_file.exists():
                target_files = [rel_file]
            elif LOG_DIR.exists():
                target_files = sorted([f for f in LOG_DIR.glob("*.log") if f.is_file()])

        if not target_files:
            raise FileNotFoundError(f"No log files found in {LOG_DIR}")

        print(f"Starting automotive telemetry analysis on {len(target_files)} log file(s)...")
        for log_path in target_files:
            analyzed_log_file = str(log_path)
            print(f"Processing log file: {log_path.name} ({log_path.stat().st_size / (1024*1024):.2f} MB)...")
            process_log(str(log_path))

    # Finalize any unrecovered open sessions at end of run across all active domain agents
    for agent in ALL_AGENTS:
        agent.finalize_open_sessions()

    # Persist anomalies JSON with cross-domain temporal correlations
    save_anomalies()

    # Execute Level 4 Unsupervised Semantic Discovery on zero-shot telemetry lines
    print("Executing Level 4 Unsupervised Semantic Log Adaptation...")
    raw_path = BASE_DIR / config["paths"]["raw_anomalies_json"]
    known_lines = []
    if raw_path.exists():
        try:
            with open(raw_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for s in saved:
                    sl = s.get("metadata", {}).get("start_line")
                    el = s.get("metadata", {}).get("end_line")
                    if sl:
                        known_lines.append(sl)
                    if el:
                        known_lines.append(el)
        except Exception:
            pass

    discovered_anomalies = []
    if analyzed_log_file:
        discovered_anomalies = scan_unmodeled_anomalies(analyzed_log_file, known_anomaly_lines=known_lines)
        print(f" - Discovered {len(discovered_anomalies)} novel unmodeled anomaly clusters on zero-shot log lines.")

    # Generate multi-domain HTML dashboard with Level 4 Agentic AI synthesis
    dashboard_html_path = generate_html_dashboard(
        log_path=analyzed_log_file,
        discovered_anomalies=discovered_anomalies,
    )

    discovered_yaml = BASE_DIR / "artifacts" / "discovered_rules.yaml"

    print("\nLevel 4 Autonomous Telemetry Analysis Completed Successfully!")
    print("Generated Artifacts:")
    print(f" - Correlated Telemetry Data: {BASE_DIR / config['paths']['raw_anomalies_json']}")
    print(f" - Level 4 AI Diagnostic Synthesis: {BASE_DIR / config['paths']['ai_summary_md']}")
    if discovered_yaml.exists():
        print(f" - Self-Adapted Rule Proposals: {discovered_yaml}")
    print(f" - HTML Diagnostic Dashboard: {dashboard_html_path}")

    # Launch interactive copilot if requested
    if args.copilot:
        run_interactive_copilot(log_path=analyzed_log_file)


if __name__ == "__main__":
    main()
