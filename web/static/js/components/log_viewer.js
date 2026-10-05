/**
 * High-Performance Log Viewer Component
 * Supports virtual buffering, search/regex filtering, tag filtering, and instant line jumping.
 */

export class LogViewer {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.maxLines = options.maxLines || 10000;
    this.autoScroll = true;
    this.searchTerm = "";
    this.selectedTag = "ALL";
    this.allLines = [];
    this.filteredLines = [];
    this.highlightedLineNum = null;

    this._initDom();
    this._bindEvents();
  }

  _initDom() {
    this.container.innerHTML = `
      <div class="flex flex-col h-full bg-[#0b1120] border border-slate-800 rounded-lg overflow-hidden shadow-2xl">
        <!-- Control / Filter Bar -->
        <div class="flex flex-wrap items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-800 gap-2">
          <div class="flex items-center gap-2 flex-1 min-w-[280px]">
            <div class="relative flex-1">
              <input
                id="log-search-input"
                type="text"
                placeholder="Search raw logs or regex (/pattern/)..."
                class="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <span id="log-match-count" class="absolute right-2 top-1 text-[10px] text-slate-400"></span>
            </div>
            <!-- Tag Filter Dropdown -->
            <select id="log-tag-filter" class="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-500">
              <option value="ALL">All Tags</option>
              <option value="ERROR">Errors / Faults</option>
              <option value="WARN">Warnings</option>
              <option value="FOTA">FOTA Updates</option>
              <option value="AT">AT Commands</option>
              <option value="CIP">Sockets / Network</option>
              <option value="GNSS">GNSS / GPS</option>
              <option value="BATTERY">Battery / Power</option>
            </select>
          </div>

          <!-- Utility Actions -->
          <div class="flex items-center gap-2">
            <div class="flex items-center gap-1 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5">
              <span class="text-[11px] text-slate-400">Jump:</span>
              <input
                id="log-jump-input"
                type="number"
                placeholder="#"
                class="w-14 bg-transparent text-xs text-cyan-400 font-mono focus:outline-none"
              />
              <button id="btn-jump-line" class="text-xs text-slate-400 hover:text-white px-1">Go</button>
            </div>

            <button
              id="btn-toggle-autoscroll"
              class="flex items-center gap-1 px-2.5 py-1 text-xs rounded font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30"
              title="Toggle automatic scrolling to latest log line"
            >
              <span>Auto-Scroll: ON</span>
            </button>

            <button
              id="btn-clear-logs"
              class="px-2 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
              title="Clear viewer window"
            >
              Clear
            </button>
          </div>
        </div>

        <!-- Log Scrollable Body -->
        <div id="log-viewport" class="flex-1 overflow-y-auto font-mono-code text-[11.5px] leading-relaxed p-1 select-text">
          <div id="log-rows-container"></div>
        </div>

        <!-- Viewer Footer Status -->
        <div class="flex items-center justify-between px-3 py-1 bg-slate-900/90 border-t border-slate-800 text-[11px] text-slate-400">
          <div class="flex items-center gap-3">
            <span id="log-count-total">Lines: 0</span>
            <span id="log-count-filtered">Showing: 0</span>
          </div>
          <div class="flex items-center gap-2">
            <span id="log-stream-status" class="text-slate-500">IDLE</span>
          </div>
        </div>
      </div>
    `;

    this.searchInput = document.getElementById("log-search-input");
    this.tagFilter = document.getElementById("log-tag-filter");
    this.jumpInput = document.getElementById("log-jump-input");
    this.btnJump = document.getElementById("btn-jump-line");
    this.btnAutoScroll = document.getElementById("btn-toggle-autoscroll");
    this.btnClear = document.getElementById("btn-clear-logs");
    this.viewport = document.getElementById("log-viewport");
    this.rowsContainer = document.getElementById("log-rows-container");
    this.countTotal = document.getElementById("log-count-total");
    this.countFiltered = document.getElementById("log-count-filtered");
    this.streamStatus = document.getElementById("log-stream-status");
  }

  _bindEvents() {
    this.searchInput.addEventListener("input", () => {
      this.searchTerm = this.searchInput.value.trim();
      this.reapplyFilter();
    });

    this.tagFilter.addEventListener("change", () => {
      this.selectedTag = this.tagFilter.value;
      this.reapplyFilter();
    });

    this.btnJump.addEventListener("click", () => this._handleJump());
    this.jumpInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") this._handleJump();
    });

    this.btnAutoScroll.addEventListener("click", () => {
      this.autoScroll = !this.autoScroll;
      this._updateAutoScrollButton();
    });

    this.btnClear.addEventListener("click", () => this.clear());

    // Detect user manual scroll up
    this.viewport.addEventListener("scroll", () => {
      const isAtBottom = this.viewport.scrollHeight - this.viewport.scrollTop - this.viewport.clientHeight < 50;
      if (!isAtBottom && this.autoScroll) {
        // optionally keep user state or let button control
      }
    });
  }

  _updateAutoScrollButton() {
    if (this.autoScroll) {
      this.btnAutoScroll.className = "flex items-center gap-1 px-2.5 py-1 text-xs rounded font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30";
      this.btnAutoScroll.innerText = "Auto-Scroll: ON";
      this.scrollToBottom();
    } else {
      this.btnAutoScroll.className = "flex items-center gap-1 px-2.5 py-1 text-xs rounded font-medium bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700";
      this.btnAutoScroll.innerText = "Auto-Scroll: PAUSED";
    }
  }

  appendBatch(lines) {
    if (!lines || lines.length === 0) return;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      this.allLines.push(line);
      if (this.allLines.length > this.maxLines) {
        this.allLines.shift();
      }

      if (this._matchesFilter(line)) {
        this.filteredLines.push(line);
        if (this.filteredLines.length > this.maxLines) {
          this.filteredLines.shift();
        }
        this._renderSingleLine(line);
      }
    }

    this._updateCounts();

    if (this.autoScroll) {
      this.scrollToBottom();
    }
  }

  _matchesFilter(line) {
    if (!line) return false;
    
    // Tag match
    if (this.selectedTag !== "ALL") {
      const tag = (line.tag || "").toUpperCase();
      if (!tag.includes(this.selectedTag)) {
        return false;
      }
    }

    // Search query match
    if (this.searchTerm) {
      const raw = line.raw || "";
      if (this.searchTerm.startsWith("/") && this.searchTerm.endsWith("/") && this.searchTerm.length > 2) {
        try {
          const regex = new RegExp(this.searchTerm.slice(1, -1), "i");
          return regex.test(raw);
        } catch (e) {
          return raw.toLowerCase().includes(this.searchTerm.toLowerCase());
        }
      }
      return raw.toLowerCase().includes(this.searchTerm.toLowerCase());
    }

    return true;
  }

  _renderSingleLine(line) {
    const row = document.createElement("div");
    row.id = `log-line-${line.num}`;
    row.className = `log-line flex items-start gap-2 hover:bg-slate-800/40 font-mono-code ${
      this.highlightedLineNum === line.num ? "highlighted" : ""
    }`;

    // Tag badge class
    let tagClass = "tag-RAW";
    const tag = (line.tag || "RAW").toUpperCase();
    if (tag.includes("ERR") || tag.includes("FAULT")) tagClass = "tag-ERROR";
    else if (tag.includes("WARN")) tagClass = "tag-WARN";
    else if (tag.includes("FOTA")) tagClass = "tag-FOTA";
    else if (tag.includes("AT")) tagClass = "tag-AT";
    else if (tag.includes("CIP") || tag.includes("SOCK")) tagClass = "tag-CIP";
    else if (tag.includes("GNSS") || tag.includes("GPS")) tagClass = "tag-GNSS";
    else if (tag.includes("BAT") || tag.includes("PWR")) tagClass = "tag-BATTERY";

    // Format raw line with highlight if searching
    let rawHtml = this._escapeHtml(line.raw);
    if (this.searchTerm && !this.searchTerm.startsWith("/")) {
      const escapedTerm = this.searchTerm.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
      const re = new RegExp(`(${escapedTerm})`, "gi");
      rawHtml = rawHtml.replace(re, '<mark class="bg-amber-400 text-slate-950 px-0.5 rounded-sm">$1</mark>');
    }

    row.innerHTML = `
      <span class="text-slate-600 select-none text-[10px] w-12 text-right pt-0.5">${line.num}</span>
      <span class="tag-badge ${tagClass} select-none">${line.tag || "RAW"}</span>
      <span class="text-slate-300 break-all flex-1 whitespace-pre-wrap">${rawHtml}</span>
    `;

    this.rowsContainer.appendChild(row);

    // Keep DOM capped to avoid browser bloat
    if (this.rowsContainer.childElementCount > 3000) {
      this.rowsContainer.removeChild(this.rowsContainer.firstElementChild);
    }
  }

  reapplyFilter() {
    this.rowsContainer.innerHTML = "";
    this.filteredLines = [];

    for (let i = 0; i < this.allLines.length; i++) {
      const line = this.allLines[i];
      if (this._matchesFilter(line)) {
        this.filteredLines.push(line);
        this._renderSingleLine(line);
      }
    }

    this._updateCounts();
    if (this.autoScroll) {
      this.scrollToBottom();
    }
  }

  _updateCounts() {
    this.countTotal.innerText = `Total: ${this.allLines.length.toLocaleString()}`;
    this.countFiltered.innerText = `Showing: ${this.filteredLines.length.toLocaleString()}`;
  }

  scrollToBottom() {
    this.viewport.scrollTop = this.viewport.scrollHeight;
  }

  jumpToLine(lineNum) {
    this.highlightedLineNum = lineNum;
    
    // Ensure line is present or reset filters if it's hidden
    let elem = document.getElementById(`log-line-${lineNum}`);
    if (!elem) {
      // Clear filters so the line is visible
      this.searchInput.value = "";
      this.searchTerm = "";
      this.tagFilter.value = "ALL";
      this.selectedTag = "ALL";
      this.reapplyFilter();
      elem = document.getElementById(`log-line-${lineNum}`);
    }

    if (elem) {
      // Disable autoscroll temporarily so user can inspect
      this.autoScroll = false;
      this._updateAutoScrollButton();

      // Clear previous highlighted
      const existing = this.rowsContainer.querySelectorAll(".highlighted");
      existing.forEach(e => e.classList.remove("highlighted"));

      elem.classList.add("highlighted");
      elem.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  _handleJump() {
    const val = parseInt(this.jumpInput.value, 10);
    if (!isNaN(val) && val > 0) {
      this.jumpToLine(val);
    }
  }

  clear() {
    this.allLines = [];
    this.filteredLines = [];
    this.rowsContainer.innerHTML = "";
    this.highlightedLineNum = null;
    this._updateCounts();
  }

  _escapeHtml(text) {
    if (!text) return "";
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}
