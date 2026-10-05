/**
 * Anomaly Inspector Table Component
 * Real-time filterable table of detected vehicle telemetry faults and DTCs with jump-to-line support.
 */

export class AnomalyTable {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.onJumpLine = options.onJumpLine || (() => {});
    this.anomalies = [];
    this.selectedSeverity = "ALL";
    this.searchTerm = "";

    this._initDom();
    this._bindEvents();
    this.fetchAnomalies();
  }

  _initDom() {
    this.container.innerHTML = `
      <div class="flex flex-col h-full bg-[#0b1120] border border-slate-800 rounded-lg overflow-hidden shadow-2xl">
        <!-- Control Bar -->
        <div class="flex items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-800 gap-2">
          <div class="flex items-center gap-2 flex-1">
            <input
              id="anomaly-search-input"
              type="text"
              placeholder="Filter anomalies..."
              class="flex-1 bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
            />
            <select id="anomaly-severity-filter" class="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-500">
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical Only</option>
              <option value="WARNING">Warnings</option>
              <option value="INFO">Info</option>
            </select>
          </div>
          <button id="btn-refresh-anomalies" class="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-2" title="Refresh anomalies">
            ↻
          </button>
        </div>

        <!-- Table Header -->
        <div class="grid grid-cols-12 px-3 py-1.5 bg-slate-950 border-b border-slate-800 text-[10.5px] font-bold text-slate-400 uppercase tracking-wider">
          <span class="col-span-2">Severity</span>
          <span class="col-span-2 text-center">Line #</span>
          <span class="col-span-3">Subsystem</span>
          <span class="col-span-5">Message / Anomaly</span>
        </div>

        <!-- Scrollable Anomaly Rows -->
        <div id="anomaly-rows-container" class="flex-1 overflow-y-auto divide-y divide-slate-800/60 font-mono-code text-[11px]">
          <div class="p-4 text-center text-slate-500 font-sans text-xs">No anomalies detected yet or scanning in progress.</div>
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-between px-3 py-1 bg-slate-900 border-t border-slate-800 text-[11px] text-slate-400">
          <span id="anomaly-count-summary">Total: 0</span>
          <span class="text-[10px] text-slate-500">Click row to jump in log viewer</span>
        </div>
      </div>
    `;

    this.searchInput = document.getElementById("anomaly-search-input");
    this.severityFilter = document.getElementById("anomaly-severity-filter");
    this.btnRefresh = document.getElementById("btn-refresh-anomalies");
    this.rowsContainer = document.getElementById("anomaly-rows-container");
    this.countSummary = document.getElementById("anomaly-count-summary");
  }

  _bindEvents() {
    this.searchInput.addEventListener("input", () => {
      this.searchTerm = this.searchInput.value.trim().toLowerCase();
      this.render();
    });

    this.severityFilter.addEventListener("change", () => {
      this.selectedSeverity = this.severityFilter.value;
      this.render();
    });

    this.btnRefresh.addEventListener("click", () => this.fetchAnomalies());

    this.rowsContainer.addEventListener("click", (e) => {
      const row = e.target.closest("[data-line-num]");
      if (row) {
        const lineNum = parseInt(row.getAttribute("data-line-num"), 10);
        if (!isNaN(lineNum)) {
          this.onJumpLine(lineNum);
        }
      }
    });
  }

  async fetchAnomalies() {
    try {
      const res = await fetch("/api/anomalies");
      if (res.ok) {
        const data = await res.json();
        this.anomalies = Array.isArray(data) ? data : [];
        this.render();
      }
    } catch (err) {
      console.warn("Failed to fetch anomalies:", err);
    }
  }

  render() {
    const filtered = this.anomalies.filter(item => {
      // Severity check
      if (this.selectedSeverity !== "ALL") {
        const sev = (item.severity || "").toUpperCase();
        if (sev !== this.selectedSeverity) return false;
      }
      // Search term check
      if (this.searchTerm) {
        const str = `${item.subsystem || ''} ${item.rule_id || ''} ${item.message || ''} ${item.line_number || ''}`.toLowerCase();
        if (!str.includes(this.searchTerm)) return false;
      }
      return true;
    });

    this.countSummary.innerText = `Showing ${filtered.length} of ${this.anomalies.length} anomalies`;

    if (filtered.length === 0) {
      this.rowsContainer.innerHTML = `
        <div class="p-6 text-center text-slate-500 font-sans text-xs">
          No matching anomalies found.
        </div>
      `;
      return;
    }

    this.rowsContainer.innerHTML = filtered.map(item => {
      const sev = (item.severity || "INFO").toUpperCase();
      let badgeClass = "bg-blue-500/20 text-blue-300 border-blue-500/30";
      if (sev === "CRITICAL") badgeClass = "bg-rose-500/20 text-rose-300 border-rose-500/40";
      else if (sev === "WARNING") badgeClass = "bg-amber-500/20 text-amber-300 border-amber-500/40";

      return `
        <div data-line-num="${item.line_number || 0}" class="grid grid-cols-12 px-3 py-2 hover:bg-slate-800/50 cursor-pointer transition-colors items-center gap-1">
          <div class="col-span-2">
            <span class="text-[9px] font-bold px-1.5 py-0.5 rounded border ${badgeClass}">${sev}</span>
          </div>
          <div class="col-span-2 text-center">
            <span class="text-cyan-400 font-bold hover:underline">L${item.line_number || '--'}</span>
          </div>
          <div class="col-span-3 text-slate-300 font-medium truncate" title="${item.subsystem || ''}">
            ${item.subsystem || 'SYS'}
          </div>
          <div class="col-span-5 text-slate-400 truncate text-[10.5px]" title="${item.message || item.rule_id || ''}">
            ${item.message || item.rule_id || 'Telemetry fault detected'}
          </div>
        </div>
      `;
    }).join("");
  }
}
