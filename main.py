import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

load_dotenv()

from parser.gps_log_reader import process_log
from reports.report_generator import generate_report_cards, generate_final_report

# Runtime configuration
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

# Process the selected log and generate richer reports.
process_log(LOG_FILE)
report_cards_path = generate_report_cards()
final_report_path = generate_final_report()
print(
    f"Telemetry analysis completed. Reports written:\n- {report_cards_path}\n- {final_report_path}"
)
