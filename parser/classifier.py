import re

# High-Performance Pre-compiled Subsystem Regular Expressions
GPS_PATTERN = re.compile(
    r"(?:\[PLA\]\s*GPS\s+RX|GPS\s+RX|\$GPS[, ])", re.IGNORECASE
)

BATTERY_PATTERN = re.compile(
    r"(?:\[PLA\]\s*ANALOG|INT\s+BATT|EXT\s+BATT|\$ANALOG[, ])", re.IGNORECASE
)

CAN_PATTERN = re.compile(
    r"(?:\[CAN\]|UDS\s+Session|UDS\s+Timeout|DTC\s*[:=]|DTC_CODE|\$CAN2[, ])", re.IGNORECASE
)

NET_PATTERN = re.compile(
    r"(?:\[PLA\]\s*NET|\[NET\]|\$GSM[, ]|CSQ\s*\d+|CREG\s*[:=]|CGREG\s*[:=])", re.IGNORECASE
)

AIS_PATTERN = re.compile(
    r"(?:\[AIS\]|AIS140|PktTyp\s*=|TxSeq\s*=)", re.IGNORECASE
)

SYSTEM_PATTERN = re.compile(
    r"(?:\[PLA\]\s*(?:SYSTEM|DIAG|SLEEP|DIGITAL)|RTC\s+\d+|HEAP\s*\(\d+|UPTIME\s+SEC)", re.IGNORECASE
)


def classify(line, line_number=None):
    """
    Inspect a raw automotive telemetry log line and return an event dictionary
    categorized by subsystem domain (GPS, BATTERY, CAN, NET, AIS, SYSTEM).
    """
    if not line:
        return None

    # Check GPS
    if GPS_PATTERN.search(line):
        return {
            "type": "GPS",
            "raw": line,
            "line_number": line_number,
        }

    # Check CAN / Diagnostics
    if CAN_PATTERN.search(line):
        return {
            "type": "CAN",
            "raw": line,
            "line_number": line_number,
        }

    # Check Power & Battery
    if BATTERY_PATTERN.search(line):
        return {
            "type": "BATTERY",
            "raw": line,
            "line_number": line_number,
        }

    # Check Cellular Network & MQTT
    if NET_PATTERN.search(line):
        return {
            "type": "NET",
            "raw": line,
            "line_number": line_number,
        }

    # Check AIS-140 Intelligent Transportation Standard
    if AIS_PATTERN.search(line):
        return {
            "type": "AIS",
            "raw": line,
            "line_number": line_number,
        }

    # Check System RTOS, Power Sleep & Watchdog
    if SYSTEM_PATTERN.search(line):
        return {
            "type": "SYSTEM",
            "raw": line,
            "line_number": line_number,
        }

    return None
