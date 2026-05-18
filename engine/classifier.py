def classify(line):
    if 'GPS' in line:
        return {'type': 'GPS', 'raw': line}
    if 'MQTT' in line:
        return {'type': 'MQTT', 'raw': line}
    if 'VEHICLE SP' in line:
        return {'type': 'CAN', 'raw': line}
    return None
