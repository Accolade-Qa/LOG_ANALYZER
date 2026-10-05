/**
 * AIS-140 State FOTA Workflow & Compliance Tab Component
 * Visualizes the 6-step handshake protocol from FOTA-Workflow.pdf and executes migration audits.
 */

export class StateFotaTab {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.onJumpLine = options.onJumpLine || (() => {});
    this.reportMarkdown = "";

    this._initDom();
    this._bindEvents();
  }

  _initDom() {
    this.container.innerHTML = `
      <div class="flex flex-col h-full bg-[#0b1120] border border-slate-800 rounded-lg overflow-hidden shadow-2xl">
        <!-- Header -->
        <div class="flex items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-800">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-purple-400"></span>
            <span class="text-xs font-bold text-slate-200 uppercase tracking-wider">AIS-140 State FOTA Engine</span>
          </div>
          <button
            id="btn-run-fota-audit"
            class="px-2.5 py-1 text-xs font-semibold rounded bg-purple-600 hover:bg-purple-500 text-white transition-all shadow-md flex items-center gap-1"
          >
            <span>⚡ Audit State Migration</span>
          </button>
        </div>

        <!-- Scrollable Content -->
        <div class="flex-1 overflow-y-auto p-3 space-y-3">
          
          <!-- State Selection Card -->
          <div class="bg-slate-900 border border-slate-800 rounded-lg p-3">
            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Indian State Government Profile</span>
            <div class="mt-2 grid grid-cols-2 gap-2 text-xs">
              <div class="bg-slate-950 p-2 rounded border border-slate-800">
                <span class="text-slate-500 text-[10px]">Active Jurisdiction</span>
                <div class="font-bold text-purple-300 mt-0.5">MH — Maharashtra (MVD)</div>
                <div class="text-[10px] text-slate-400 font-mono mt-0.5">Endpoint: 164.100.148.89:8088</div>
              </div>
              <div class="bg-slate-950 p-2 rounded border border-slate-800">
                <span class="text-slate-500 text-[10px]">Firmware Target</span>
                <div class="font-bold text-emerald-400 mt-0.5">REL_05 (AIS-140 Compliant)</div>
                <div class="text-[10px] text-slate-400 font-mono mt-0.5">Previous: REL_18</div>
              </div>
            </div>
          </div>

          <!-- 6-Step AIS-140 Handshake Flow -->
          <div class="bg-slate-900 border border-slate-800 rounded-lg p-3">
            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider">FOTA-Workflow.pdf Handshake Checklist</span>
            
            <div class="mt-2.5 space-y-2 text-xs font-mono-code">
              <!-- Step 1 -->
              <div class="flex items-start gap-2.5 p-2 rounded bg-slate-950 border border-slate-800/80">
                <span class="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center text-[10px] font-bold">✓</span>
                <div class="flex-1">
                  <div class="flex justify-between items-center">
                    <span class="font-bold text-slate-200">1. Vehicle Identity & Login</span>
                    <span class="text-[10px] text-emerald-400 font-sans">ACKNOWLEDGED</span>
                  </div>
                  <div class="text-[10.5px] text-slate-400 font-mono mt-0.5">*LOGIN# verified with IMEI & SWEMP signature</div>
                </div>
              </div>

              <!-- Step 2 -->
              <div class="flex items-start gap-2.5 p-2 rounded bg-slate-950 border border-slate-800/80">
                <span class="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center text-[10px] font-bold">✓</span>
                <div class="flex-1">
                  <div class="flex justify-between items-center">
                    <span class="font-bold text-slate-200">2. FOTA Trigger Command</span>
                    <span class="text-[10px] text-emerald-400 font-sans">DISPATCHED</span>
                  </div>
                  <div class="text-[10.5px] text-slate-400 font-mono mt-0.5">*FOTA# URL, FileSize, Checksum received</div>
                </div>
              </div>

              <!-- Step 3 -->
              <div class="flex items-start gap-2.5 p-2 rounded bg-slate-950 border border-slate-800/80">
                <span class="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center text-[10px] font-bold">✓</span>
                <div class="flex-1">
                  <div class="flex justify-between items-center">
                    <span class="font-bold text-slate-200">3. TCU Handshake ACK</span>
                    <span class="text-[10px] text-emerald-400 font-sans">CONFIRMED</span>
                  </div>
                  <div class="text-[10.5px] text-slate-400 font-mono mt-0.5">TCU switches to FOTA download mode on CIP3</div>
                </div>
              </div>

              <!-- Step 4 -->
              <div class="flex items-start gap-2.5 p-2 rounded bg-slate-950 border border-slate-800/80">
                <span class="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center text-[10px] font-bold">✓</span>
                <div class="flex-1">
                  <div class="flex justify-between items-center">
                    <span class="font-bold text-slate-200">4. Block-by-Block Download</span>
                    <span class="text-[10px] text-emerald-400 font-sans">100% COMPLETE</span>
                  </div>
                  <div class="text-[10.5px] text-slate-400 font-mono mt-0.5">Packet integrity checks pass; zero retransmissions</div>
                </div>
              </div>

              <!-- Step 5 -->
              <div class="flex items-start gap-2.5 p-2 rounded bg-slate-950 border border-slate-800/80">
                <span class="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center text-[10px] font-bold">✓</span>
                <div class="flex-1">
                  <div class="flex justify-between items-center">
                    <span class="font-bold text-slate-200">5. Flash Write & MCU Reboot</span>
                    <span class="text-[10px] text-emerald-400 font-sans">VERIFIED</span>
                  </div>
                  <div class="text-[10.5px] text-slate-400 font-mono mt-0.5">Firmware committed to flash memory; warm reboot complete</div>
                </div>
              </div>

              <!-- Step 6 -->
              <div class="flex items-start gap-2.5 p-2 rounded bg-purple-950/40 border border-purple-500/40">
                <span class="w-5 h-5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/40 flex items-center justify-center text-[10px] font-bold">⚡</span>
                <div class="flex-1">
                  <div class="flex justify-between items-center">
                    <span class="font-bold text-purple-200">6. Post-Flash State Endpoint Reconfig</span>
                    <span class="text-[10px] text-purple-300 font-sans font-bold">DYNAMIC MIGRATION</span>
                  </div>
                  <div class="text-[10.5px] text-purple-300/80 font-mono mt-0.5">*SET#CIP1#164.100.148.89:8088 applied for MH MVD</div>
                </div>
              </div>
            </div>
          </div>

          <!-- Audit Output Card -->
          <div id="fota-audit-output" class="bg-slate-900 border border-slate-800 rounded-lg p-3 hidden">
            <div class="flex items-center justify-between pb-2 border-b border-slate-800 mb-2">
              <span class="text-xs font-bold text-cyan-300">Live Migration Compliance Report</span>
              <button id="btn-close-fota-audit" class="text-slate-400 hover:text-white text-xs">✕</button>
            </div>
            <div id="fota-audit-markdown" class="text-xs text-slate-300 copilot-body space-y-2"></div>
          </div>

        </div>
      </div>
    `;

    this.btnRunAudit = document.getElementById("btn-run-fota-audit");
    this.auditOutput = document.getElementById("fota-audit-output");
    this.auditMarkdown = document.getElementById("fota-audit-markdown");
    this.btnCloseAudit = document.getElementById("btn-close-fota-audit");
  }

  _bindEvents() {
    this.btnRunAudit.addEventListener("click", () => this.runAudit());
    this.btnCloseAudit.addEventListener("click", () => {
      this.auditOutput.classList.add("hidden");
    });
  }

  async runAudit() {
    this.btnRunAudit.disabled = true;
    this.btnRunAudit.innerText = "Analyzing...";
    this.auditOutput.classList.remove("hidden");
    this.auditMarkdown.innerHTML = `<div class="p-3 text-cyan-400 flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span> Auditing FOTA campaign against FOTA-Workflow.pdf...</div>`;

    try {
      const res = await fetch("/api/fota/validate-state");
      const data = await res.json();
      if (res.ok && data.report_markdown) {
        this.auditMarkdown.innerHTML = this._renderMarkdown(data.report_markdown);
      } else {
        this.auditMarkdown.innerHTML = `<div class="text-rose-400">Failed to run audit: ${data.detail || 'Unknown error'}</div>`;
      }
    } catch (e) {
      this.auditMarkdown.innerHTML = `<div class="text-rose-400">Error: ${e.message}</div>`;
    } finally {
      this.btnRunAudit.disabled = false;
      this.btnRunAudit.innerText = "⚡ Audit State Migration";
    }
  }

  _renderMarkdown(md) {
    if (!md) return "";
    let html = md.replace(/\b[Ll]ine\s+(\d+)\b/g, '<span class="text-cyan-400 font-mono font-bold">Line $1</span>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-white">$1</strong>');
    html = html.replace(/`([^`]+)`/g, '<code class="bg-slate-950 px-1 py-0.5 rounded text-cyan-300 font-mono text-[11px]">$1</code>');
    html = html.replace(/^###\s*(.*)$/gm, '<div class="text-xs font-bold text-cyan-300 mt-2 mb-1">$1</div>');
    html = html.replace(/^##\s*(.*)$/gm, '<div class="text-sm font-bold text-cyan-400 mt-3 mb-1 border-b border-slate-800 pb-1">$1</div>');
    html = html.replace(/^\s*-\s+(.*)$/gm, '<div class="flex items-start gap-1.5 my-0.5"><span class="text-purple-400">•</span><span>$1</span></div>');
    html = html.replace(/\n\n/g, '<div class="h-2"></div>');
    return html;
  }
}
