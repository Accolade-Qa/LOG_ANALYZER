from analyzers.gps_analyzer import gps_analyzer
from analyzers.mqtt_analyzer import mqtt_analyzer
from analyzers.can_analyzer import can_analyzer

registry = {
    'GPS': gps_analyzer,
    'MQTT': mqtt_analyzer,
    'CAN': can_analyzer
}

def dispatch(event):
    analyzer = registry.get(event['type'])
    if analyzer:
        analyzer.handle(event)
