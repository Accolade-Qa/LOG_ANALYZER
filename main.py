import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

load_dotenv()

from parser.gps_log_reader import process_log

from llm.summary_agent import generate_ai_summary

# print(os.getenv("OPENAI_API_KEY"))
# print(os.getenv("GEMINI_API_KEY"))

LOG_DIR = "logs"
LOG_FILE = None
if os.path.isdir(LOG_DIR):
    log_files = [
        f
        for f in sorted(os.listdir(LOG_DIR))
        if os.path.isfile(os.path.join(LOG_DIR, f))
    ]
    if log_files:
        LOG_FILE = os.path.join(LOG_DIR, log_files[0])
    else:
        raise FileNotFoundError(f"No log files found in directory: {LOG_DIR}")
else:
    raise FileNotFoundError(f"Log directory not found: {LOG_DIR}")

from reports.report_generator import generate_report_cards

# Existing imports remain
# from reports.report_merger import merge_reports  # removed

# After processing logs
process_log(LOG_FILE)
generate_report_cards()
# Cleanup auto-generated report files
report_files = ["reports/summary_report.md", "reports/final_report.md"]
for rf in report_files:
    try:
        os.remove(rf)
    except FileNotFoundError:
        pass
print("Telemetry analysis completed")
