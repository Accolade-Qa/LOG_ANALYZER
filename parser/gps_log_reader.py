from parser.classifier import classify
from engine.dispatcher import dispatch


def process_log(log_path):
    """Process GPS log file and dispatch events to agents"""
    with open(log_path, "r", errors="ignore") as f:
        for line in f:
            event = classify(line)
            if event:
                dispatch(event)
