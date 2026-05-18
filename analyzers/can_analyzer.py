from analyzers.base_analyzer import BaseAnalyzer
from aggregator.anomaly_collector import collect

class CANAnalyzer(BaseAnalyzer):
    def handle(self, event):
        if '457' in event['raw']:
            collect('Abnormal vehicle speed spike')

can_analyzer = CANAnalyzer()
