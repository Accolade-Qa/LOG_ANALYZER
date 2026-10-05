/**
 * Live WebSocket Client for Telemetry Streaming with Auto-Reconnect
 */

export class TelemetryWebSocketClient {
  constructor(options = {}) {
    this.url = options.url || this._getDefaultWsUrl();
    this.onBatch = options.onBatch || (() => {});
    this.onInitial = options.onInitial || (() => {});
    this.onStatus = options.onStatus || (() => {});
    this.onConnect = options.onConnect || (() => {});
    this.onDisconnect = options.onDisconnect || (() => {});

    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 30;
    this.reconnectDelay = 1500;
    this.isConnected = false;
    this._pingTimer = null;
  }

  _getDefaultWsUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/live-stream`;
  }

  connect() {
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.onConnect();
        this._startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          this._handleMessage(payload);
        } catch (err) {
          console.error("WS Parse Error:", err, event.data);
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this._stopHeartbeat();
        this.onDisconnect();
        this._scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.warn("WS Connection Error:", err);
      };
    } catch (e) {
      this._scheduleReconnect();
    }
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this._pingTimer = setInterval(() => {
      if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.sendAction("ping");
      }
    }, 15000);
  }

  _stopHeartbeat() {
    if (this._pingTimer) {
      clearInterval(this._pingTimer);
      this._pingTimer = null;
    }
  }

  _scheduleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(this.reconnectDelay * Math.pow(1.2, this.reconnectAttempts), 10000);
      setTimeout(() => this.connect(), delay);
    }
  }

  _handleMessage(payload) {
    if (!payload || !payload.type) return;

    switch (payload.type) {
      case "TELEMETRY_BATCH":
        if (payload.data) {
          this.onBatch(payload.data.lines || [], payload.data.blackboard || {}, payload.data.status || {});
        }
        break;
      case "INITIAL_STATE":
        if (payload.data) {
          this.onInitial(payload.data.blackboard || {}, payload.data.status || {});
        }
        break;
      case "STATUS":
        if (payload.data) {
          this.onStatus(payload.data);
        }
        break;
      case "PONG":
        // Heartbeat response
        break;
      default:
        break;
    }
  }

  sendAction(action, extra = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action, ...extra }));
    }
  }

  sendPause() {
    this.sendAction("pause");
  }

  sendResume() {
    this.sendAction("resume");
  }

  sendStop() {
    this.sendAction("stop");
  }
}
