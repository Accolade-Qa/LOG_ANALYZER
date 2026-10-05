/**
 * Main Application Orchestrator for Automotive Telemetry Workbench
 */

import { TelemetryWebSocketClient } from './ws_client.js';
import { LogViewer } from './components/log_viewer.js';
import { TelemetryHUD } from './components/telemetry_hud.js';
import { CopilotChat } from './components/copilot_chat.js';
import { AnomalyTable } from './components/anomaly_table.js';
import { StateFotaTab } from './components/state_fota_tab.js';

class WorkbenchApp {
  constructor() {
    this.currentMode = "file";
    this.isStreaming = false;
    this.isPaused = false;
    this.activeLogName = "";

    this._initElements();
    this._initSubsystems();
    this._bindEvents();
    this._loadInitialData();
  }

  _initElements() {
    // Top Bar Elements
    this.modeSelector = document.getElementById("stream-mode-select");
    this.sourceSelector = document.getElementById("stream-source-select");
    this.btnStart = document.getElementById("btn-stream-start");
    this.btnPause = document.getElementById("btn-stream-pause");
    this.btnStop = document.getElementById("btn-stream-stop");

    this.streamBadge = document.getElementById("badge-stream-state");
    this.streamDot = document.getElementById("badge-stream-dot");
    this.metricSpeed = document.getElementById("metric-speed");
    this.metricLines = document.getElementById("metric-lines");
    this.wsStatusBadge = document.getElementById("badge-ws-status");

    // Right Panel Tabs
    this.tabButtons = document.querySelectorAll(".right-tab-btn");
    this.tabContents = document.querySelectorAll(".right-tab-pane");

    // CIP1 Audit Modal
    this.cip1Modal = document.getElementById("modal-cip1-audit");
    this.cip1ModalContent = document.getElementById("modal-cip1-content");
    this.btnCloseCip1Modal = document.getElementById("btn-close-cip1-modal");
  }

  _initSubsystems() {
    // 1. Log Viewer
    this.logViewer = new LogViewer("center-log-viewer-container");

    // 2. Telemetry HUD
    this.hud = new TelemetryHUD("left-telemetry-hud-container", {
      onAuditCip1: () => this.handleAuditCip1(),
      onValidateFota: () => {
        this.switchRightTab("fota");
        this.fotaTab.runAudit();
      }
    });

    // 3. AI Copilot
    this.copilot = new CopilotChat("copilot-tab-container", {
      onJumpLine: (lineNum) => this.logViewer.jumpToLine(lineNum)
    });

    // 4. Anomaly Table
    this.anomalyTable = new AnomalyTable("anomaly-tab-container", {
      onJumpLine: (lineNum) => this.logViewer.jumpToLine(lineNum)
    });

    // 5. State FOTA Tab
    this.fotaTab = new StateFotaTab("fota-tab-container", {
      onJumpLine: (lineNum) => this.logViewer.jumpToLine(lineNum)
    });

    // 6. WebSocket Client
    this.wsClient = new TelemetryWebSocketClient({
      onBatch: (lines, bb, status) => this.handleBatch(lines, bb, status),
      onInitial: (bb, status) => {
        this.hud.updateSnapshot(bb);
        this.updateStreamStatus(status);
      },
      onConnect: () => {
        this.wsStatusBadge.innerText = "ONLINE";
        this.wsStatusBadge.className = "text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      },
      onDisconnect: () => {
        this.wsStatusBadge.innerText = "CONNECTING...";
        this.wsStatusBadge.className = "text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30";
      }
    });

    this.wsClient.connect();
  }

  _bindEvents() {
    // Stream controls
    this.modeSelector.addEventListener("change", () => this.handleModeChange());
    this.btnStart.addEventListener("click", () => this.startStream());
    this.btnPause.addEventListener("click", () => this.togglePauseStream());
    this.btnStop.addEventListener("click", () => this.stopStream());

    // Right Tabs switching
    this.tabButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const tab = btn.getAttribute("data-tab");
        this.switchRightTab(tab);
      });
    });

    // CIP1 Modal close
    if (this.btnCloseCip1Modal) {
      this.btnCloseCip1Modal.addEventListener("click", () => {
        this.cip1Modal.classList.add("hidden");
      });
    }
  }

  async _loadInitialData() {
    await this.loadSourcesForMode("file");
    this.anomalyTable.fetchAnomalies();
  }

  async handleModeChange() {
    this.currentMode = this.modeSelector.value;
    await this.loadSourcesForMode(this.currentMode);
  }

  async loadSourcesForMode(mode) {
    this.sourceSelector.innerHTML = "";

    if (mode === "file" || mode === "tail") {
      try {
        const res = await fetch("/api/logs/list");
        const files = await res.json();
        if (files && files.length > 0) {
          files.forEach(f => {
            const opt = document.createElement("option");
            opt.value = f.name;
            opt.innerText = `${f.name} (${f.size_mb} MB)`;
            this.sourceSelector.appendChild(opt);
          });
        } else {
          const opt = document.createElement("option");
          opt.value = "";
          opt.innerText = "No log files found in logs/";
          this.sourceSelector.appendChild(opt);
        }
      } catch (e) {
        console.error("Error loading logs:", e);
      }
    } else if (mode === "uart") {
      try {
        const res = await fetch("/api/serial/ports");
        const ports = await res.json();
        if (ports && ports.length > 0) {
          ports.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p.port;
            opt.innerText = `${p.port} (${p.description || 'Serial'})`;
            this.sourceSelector.appendChild(opt);
          });
        } else {
          const opt = document.createElement("option");
          opt.value = "COM3";
          opt.innerText = "COM3 (Default Hardware Port)";
          this.sourceSelector.appendChild(opt);
        }
      } catch (e) {
        console.error("Error loading COM ports:", e);
      }
    }
  }

  async startStream() {
    const source = this.sourceSelector.value;
    if (!source) {
      alert("Please select a valid log file or serial port first.");
      return;
    }

    this.btnStart.disabled = true;
    try {
      const res = await fetch("/api/stream/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: this.currentMode,
          source: source,
          speed: 0.001,
          baudrate: 115200
        })
      });

      if (res.ok) {
        this.isStreaming = true;
        this.isPaused = false;
        this.btnStart.classList.add("hidden");
        this.btnPause.classList.remove("hidden");
        this.btnPause.innerText = "⏸ Pause";
        this.btnStop.classList.remove("hidden");
        this.updateBadge("LIVE", "emerald");
      }
    } catch (e) {
      alert("Failed to start stream: " + e.message);
    } finally {
      this.btnStart.disabled = false;
    }
  }

  async togglePauseStream() {
    if (!this.isStreaming) return;

    if (this.isPaused) {
      // Resume
      await fetch("/api/stream/resume", { method: "POST" });
      this.isPaused = false;
      this.btnPause.innerText = "⏸ Pause";
      this.updateBadge("LIVE", "emerald");
    } else {
      // Pause
      await fetch("/api/stream/pause", { method: "POST" });
      this.isPaused = true;
      this.btnPause.innerText = "▶ Resume";
      this.updateBadge("PAUSED", "amber");
    }
  }

  async stopStream() {
    await fetch("/api/stream/stop", { method: "POST" });
    this.isStreaming = false;
    this.isPaused = false;
    this.btnStart.classList.remove("hidden");
    this.btnPause.classList.add("hidden");
    this.btnStop.classList.add("hidden");
    this.updateBadge("IDLE", "slate");
  }

  updateBadge(label, color) {
    this.streamBadge.innerText = label;
    if (color === "emerald") {
      this.streamDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-ping";
      this.streamBadge.className = "text-[11px] font-bold px-2.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
    } else if (color === "amber") {
      this.streamDot.className = "w-2 h-2 rounded-full bg-amber-400";
      this.streamBadge.className = "text-[11px] font-bold px-2.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30";
    } else {
      this.streamDot.className = "w-2 h-2 rounded-full bg-slate-500";
      this.streamBadge.className = "text-[11px] font-bold px-2.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700";
    }
  }

  handleBatch(lines, blackboard, status) {
    if (lines && lines.length > 0) {
      this.logViewer.appendBatch(lines);
    }
    if (blackboard) {
      this.hud.updateSnapshot(blackboard);
    }
    if (status) {
      this.updateStreamStatus(status);
    }
  }

  updateStreamStatus(status) {
    if (!status) return;
    if (status.lines_per_sec !== undefined) {
      this.metricSpeed.innerText = `${status.lines_per_sec.toLocaleString()} lines/s`;
    }
    if (status.total_lines !== undefined) {
      this.metricLines.innerText = `${status.total_lines.toLocaleString()} lines`;
    }

    if (status.is_running && !status.is_paused) {
      this.updateBadge("LIVE", "emerald");
      this.btnStart.classList.add("hidden");
      this.btnPause.classList.remove("hidden");
      this.btnStop.classList.remove("hidden");
    } else if (status.is_paused) {
      this.updateBadge("PAUSED", "amber");
    } else {
      this.updateBadge("IDLE", "slate");
      this.btnStart.classList.remove("hidden");
      this.btnPause.classList.add("hidden");
      this.btnStop.classList.add("hidden");
    }
  }

  switchRightTab(tabKey) {
    this.tabButtons.forEach(btn => {
      const active = btn.getAttribute("data-tab") === tabKey;
      if (active) {
        btn.classList.add("border-b-2", "border-cyan-400", "text-cyan-300");
        btn.classList.remove("text-slate-400");
      } else {
        btn.classList.remove("border-b-2", "border-cyan-400", "text-cyan-300");
        btn.classList.add("text-slate-400");
      }
    });

    this.tabContents.forEach(pane => {
      if (pane.id === `tab-${tabKey}`) {
        pane.classList.remove("hidden");
      } else {
        pane.classList.add("hidden");
      }
    });
  }

  async handleAuditCip1() {
    this.cip1Modal.classList.remove("hidden");
    this.cip1ModalContent.innerHTML = `
      <div class="p-4 text-cyan-400 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
        Evaluating dynamic blackboard state and firmware configuration for CIP1...
      </div>
    `;

    try {
      const res = await fetch("/api/telemetry/audit-cip1?param=cip1");
      const data = await res.json();
      if (data && data.audit_markdown) {
        this.cip1ModalContent.innerHTML = this.copilot._renderMarkdown(data.audit_markdown);
      } else {
        this.cip1ModalContent.innerHTML = `<div class="text-rose-400">Failed to audit CIP1 state.</div>`;
      }
    } catch (e) {
      this.cip1ModalContent.innerHTML = `<div class="text-rose-400">Audit Error: ${e.message}</div>`;
    }
  }
}

// Instantiate on DOM load
window.addEventListener("DOMContentLoaded", () => {
  window.workbenchApp = new WorkbenchApp();
});
