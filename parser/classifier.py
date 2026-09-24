import re

# Match lines containing GPS telemetry: e.g., '[PLA] GPS RX', '$GPS,', or 'GPS RX'
GPS_PATTERN = re.compile(
    r"(?:\[PLA\]\s*GPS\s+RX|GPS\s+RX|\$GPS[, ])", re.IGNORECASE
)


def classify(line, line_number=None):
    """
    Inspect a log line and return a GPS event dictionary if it contains GPS telemetry data.
    """
    if GPS_PATTERN.search(line):
        return {
            "type": "GPS",
            "raw": line,
            "line_number": line_number,
        }
    return None



