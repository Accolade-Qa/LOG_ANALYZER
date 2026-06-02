from dotenv import load_dotenv

load_dotenv()

from parser.gps_log_reader import process_log

from llm.summary_agent import generate_ai_summary
import os

# print(os.getenv("OPENAI_API_KEY"))
print(os.getenv("GEMINI_API_KEY"))

LOG_FILE = "logs/FOTA_REL_18_861564061380138_To_REL_05.log"

from reports.report_generator import generate_report_cards

# Existing imports remain
# from reports.report_merger import merge_reports  # removed

# After processing logs
process_log(LOG_FILE)
generate_report_cards()
# Cleanup auto-generated report files
import os

report_files = ["reports/summary_report.md", "reports/final_report.md"]
for rf in report_files:
    try:
        os.remove(rf)
    except FileNotFoundError:
        pass
print("Telemetry analysis completed")
