def classify(line):
    if "GPS" in line:
        return {"type": "GPS", "raw": line}

    if "MQTT" in line:
        return {"type": "MQTT", "raw": line}

    if "NET" in line:
        return {"type": "NET", "raw": line}

    if "BATT" in line:
        return {"type": "BATTERY", "raw": line}

    if "CAN" in line or "VEHICLE SP" in line:
        return {"type": "CAN", "raw": line}

    return None
