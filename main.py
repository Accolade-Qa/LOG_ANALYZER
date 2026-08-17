import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

load_dotenv()

import argparse
from llm.summary_agent import generate_ai_summary
from parser.gps_log_reader import process_log
from reports.anomaly_collector import clear_anomalies, save_anomalies
from reports.report_generator import generate_final_report, generate_report_cards

def main():
    parser = argparse.ArgumentParser(description="Automated Telemetry Log Analyzer")
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to specific log file to analyze",
    )
    args = parser.parse_args()

    LOG_DIR = BASE_DIR / "logs"
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
        # Default to REL18_TO_REL24.log if available, otherwise analyze all log files
        rel_file = LOG_DIR / "REL18_TO_REL24.log"
        if rel_file.exists():
            target_files = [rel_file]
        elif LOG_DIR.exists():
            target_files = sorted([f for f in LOG_DIR.glob("*.log") if f.is_file()])

    if not target_files:
        raise FileNotFoundError(f"No log files found in {LOG_DIR}")

    # Reset anomaly collector state for clean run
    clear_anomalies()

    print(f"Starting telemetry analysis on {len(target_files)} log file(s)...")
    for log_path in target_files:
        print(f"Processing log file: {log_path.name} ({log_path.stat().st_size / (1024*1024):.2f} MB)...")
        process_log(str(log_path))

    # Persist anomalies to raw_anomalies.json
    save_anomalies()

    # Generate all reports
    report_cards_path = generate_report_cards()

    final_report_path = generate_final_report()
    
    # Generate AI summary
    generate_ai_summary()
    ai_summary_path = BASE_DIR / "artifacts" / "ai_summary.md"

    print("\nTelemetry analysis completed successfully!")
    print("Generated Artifacts:")
    print(f" - Raw Anomalies JSON: {BASE_DIR / 'artifacts' / 'raw_anomalies.json'}")
    print(f" - Report Cards:       {report_cards_path}")
    print(f" - Final Report:        {final_report_path}")
    print(f" - AI Summary:         {ai_summary_path}")



if __name__ == "__main__":
    main()

