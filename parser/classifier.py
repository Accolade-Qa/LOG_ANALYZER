import re

TIMESTAMP_PATTERN = r"\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\]"
LEVEL_COMPONENT_PATTERN = r"\s+\w+:\s+"
PLA_PREFIX = rf"{TIMESTAMP_PATTERN}{LEVEL_COMPONENT_PATTERN}\[PLA\]\s+"
NET_PREFIX = rf"{TIMESTAMP_PATTERN}{LEVEL_COMPONENT_PATTERN}\[NET\]\s+"
CAN_PREFIX = rf"{TIMESTAMP_PATTERN}{LEVEL_COMPONENT_PATTERN}\[CAN\]\s+"

PATTERN_DEFINITIONS = [
    (
        "GPS",
        re.compile(rf"{PLA_PREFIX}GPS\s+RX", re.IGNORECASE),
    ),
    (
        "MQTT",
        re.compile(rf"{PLA_PREFIX}NET\b.*\bMQTT\b", re.IGNORECASE),
    ),
    (
        "CAN",
        re.compile(
            rf"(?:{CAN_PREFIX}|{PLA_PREFIX}(?:CAN\b|UDS\s+Session\s+Timeout|DTC\b|FaultVal|IGN_status|##INCR))",
            re.IGNORECASE,
        ),
    ),
    (
        "BATTERY",
        re.compile(
            rf"{PLA_PREFIX}ANALOG\b.*\b(?:INT\s+BATT|EXT\s+BATT|TMPR|AN)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "NET",
        re.compile(rf"(?:{PLA_PREFIX}NET\b|{NET_PREFIX})", re.IGNORECASE),
    ),
]


def classify(line):
    for event_type, pattern in PATTERN_DEFINITIONS:
        if pattern.search(line):
            return {"type": event_type, "raw": line}
    return None
