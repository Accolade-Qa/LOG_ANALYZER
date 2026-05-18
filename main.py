from engine.log_reader import process_log
from aggregator.report_merger import merge_reports
from ai.summary_agent import generate_ai_summary

LOG_FILE = "logs/REL18_TO_REL24.log"

process_log(LOG_FILE)
merge_reports()
generate_ai_summary()
print("Telemetry analysis completed")
