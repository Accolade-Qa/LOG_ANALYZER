from parser.classifier import classify
from engine.dispatcher import dispatch


def process_log(log_path):
    """Process GPS log file and dispatch events to agents with 1-based line tracking."""
    with open(log_path, "r", errors="ignore") as f:
        for line_num, line in enumerate(f, start=1):
            event = classify(line, line_number=line_num)
            if event:
                dispatch(event)
