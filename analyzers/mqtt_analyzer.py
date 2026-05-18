from analyzers.base_analyzer import BaseAnalyzer
from aggregator.anomaly_collector import collect

class MQTTAnalyzer(BaseAnalyzer):
    def handle(self, event):
        if 'disconnect' in event['raw'].lower():
            collect('MQTT disconnected')

mqtt_analyzer = MQTTAnalyzer()
