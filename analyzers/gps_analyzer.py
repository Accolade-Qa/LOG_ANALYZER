from analyzers.base_analyzer import BaseAnalyzer
from aggregator.anomaly_collector import collect

class GPSAnalyzer(BaseAnalyzer):
    def handle(self, event):
        if '0.000000' in event['raw']:
            collect('GPS invalid coordinates')

gps_analyzer = GPSAnalyzer()
