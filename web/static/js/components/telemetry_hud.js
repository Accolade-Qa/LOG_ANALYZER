/**
 * Real-Time Telemetry HUD Component
 * Displays 4G CSQ meter, Sockets bitmask with dynamic CIP1 badge, battery dials, GNSS radar, and FOTA status.
 */

export class TelemetryHUD {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.onAuditCip1 = options.onAuditCip1 || (() => {});
    this.onValidateFota = options.onValidateFota || (() => {});

    this._initDom();
    this._bindEvents();
  }

  _initDom() {
    this.container.innerHTML = `
      <div class="flex flex-col gap-3 h-full overflow-y-auto pr-1">

        <!-- 1. Modem & Cellular Signal -->
        <div class="bg-slate-900 border border-slate-800 rounded-lg p-3 shadow-md">
          <div class="flex items-center justify-between pb-2 border-b border-slate-800">
            <span class="text-xs font-bold tracking-wider text-slate-300 uppercase flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-cyan-400 inline-block"></span>
              Cellular 4G Modem
            </span>
            <span id="hud-creg-badge" class="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              REGISTERED
            </span>
          </div>

          <div class="mt-3 flex items-center justify-between">
            <div class="flex flex-col">
              <span class="text-[11px] text-slate-400">Signal Quality (CSQ)</span>
              <div class="flex items-baseline gap-1 mt-0.5">
                <span id="hud-csq-val" class="text-xl font-mono font-bold text-cyan-400">--</span>
                <span class="text-[11px] text-slate-500">/ 31</span>
              </div>
            </div>
            <div class="text-right">
              <span class="text-[10px] text-slate-500">Est. Signal</span>
              <div id="hud-csq-dbm" class="text-xs font-mono font-semibold text-slate-300">-- dBm</div>
            </div>
          </div>

          <!-- CSQ Progress Bar -->
          <div class="w-full bg-slate-950 h-2 rounded-full overflow-hidden mt-2 border border-slate-800">
            <div id="hud-csq-bar" class="h-full bg-cyan-500 transition-all duration-300" style="width: 0%"></div>
          </div>

          <div class="mt-2 flex justify-between text-[10px] text-slate-400">
            <span>Operator: <span id="hud-operator" class="text-slate-200">Auto</span></span>
            <span>RAT: <span id="hud-rat" class="text-slate-200">LTE-M</span></span>
          </div>
        </div>

        <!-- 2. Sockets Matrix & Dynamic CIP1 Status -->
        <div class="bg-slate-900 border border-slate-800 rounded-lg p-3 shadow-md">
          <div class="flex items-center justify-between pb-2 border-b border-slate-800">
            <span class="text-xs font-bold tracking-wider text-slate-300 uppercase flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-blue-400 inline-block"></span>
              Sockets Matrix (CIP)
            </span>
            <button
              id="hud-btn-audit-cip1"
              class="text-[10px] font-semibold px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40 hover:bg-purple-500/30 transition-all flex items-center gap-1"
              title="Audit CIP1 Dynamic Inference vs Static Config"
            >
              <span>Audit CIP1</span>
            </button>
          </div>

          <div class="grid grid-cols-2 gap-2 mt-2.5">
            <!-- CIP0: Primary -->
            <div class="bg-slate-950 p-2 rounded border border-slate-800/80">
              <div class="flex justify-between items-center text-[10px]">
                <span class="font-bold text-slate-300">CIP0: Primary</span>
                <span id="hud-cip0-state" class="text-emerald-400 font-mono">ACTIVE</span>
              </div>
              <div id="hud-cip0-endpoint" class="text-[10px] font-mono text-slate-400 truncate mt-1">103.241.144.10:9001</div>
            </div>

            <!-- CIP1: Secondary / State Govt -->
            <div id="hud-cip1-card" class="bg-slate-950 p-2 rounded border border-purple-500/40">
              <div class="flex justify-between items-center text-[10px]">
                <span class="font-bold text-purple-300">CIP1: Gov Server</span>
                <span id="hud-cip1-badge" class="px-1 py-0.2 rounded text-[9px] bg-purple-500/30 text-purple-200 border border-purple-400/30 font-semibold">
                  INFERRED
                </span>
              </div>
              <div id="hud-cip1-endpoint" class="text-[10px] font-mono text-slate-400 truncate mt-1">164.100.148.89:8088</div>
            </div>

            <!-- CIP2: Aux -->
            <div class="bg-slate-950 p-2 rounded border border-slate-800/80">
              <div class="flex justify-between items-center text-[10px]">
                <span class="font-bold text-slate-300">CIP2: Emergency</span>
                <span id="hud-cip2-state" class="text-slate-500 font-mono">STANDBY</span>
              </div>
              <div id="hud-cip2-endpoint" class="text-[10px] font-mono text-slate-500 truncate mt-1">--</div>
            </div>

            <!-- CIP3: FOTA Socket -->
            <div class="bg-slate-950 p-2 rounded border border-slate-800/80">
              <div class="flex justify-between items-center text-[10px]">
                <span class="font-bold text-slate-300">CIP3: FOTA DL</span>
                <span id="hud-cip3-state" class="text-amber-400 font-mono">IDLE</span>
              </div>
              <div id="hud-cip3-endpoint" class="text-[10px] font-mono text-slate-400 truncate mt-1">115.241.194.26:5000</div>
            </div>
          </div>
        </div>

        <!-- 3. Power, Voltage & Ignition -->
        <div class="bg-slate-900 border border-slate-800 rounded-lg p-3 shadow-md">
          <div class="flex items-center justify-between pb-2 border-b border-slate-800">
            <span class="text-xs font-bold tracking-wider text-slate-300 uppercase flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-amber-400 inline-block"></span>
              Power & Voltages
            </span>
            <span id="hud-ign-badge" class="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              IGN: ON
            </span>
          </div>

          <div class="grid grid-cols-2 gap-3 mt-3">
            <div class="flex flex-col bg-slate-950 p-2 rounded border border-slate-800/80">
              <span class="text-[10px] text-slate-400">Main Vehicle Battery</span>
              <div class="flex items-baseline gap-1 mt-0.5">
                <span id="hud-main-v-val" class="text-lg font-mono font-bold text-amber-400">24.1</span>
                <span class="text-xs text-slate-500">V</span>
              </div>
              <span id="hud-main-v-status" class="text-[10px] text-emerald-400 mt-0.5">Normal (24V System)</span>
            </div>

            <div class="flex flex-col bg-slate-950 p-2 rounded border border-slate-800/80">
              <span class="text-[10px] text-slate-400">Internal Li-ion</span>
              <div class="flex items-baseline gap-1 mt-0.5">
                <span id="hud-int-v-val" class="text-lg font-mono font-bold text-emerald-400">3.82</span>
                <span class="text-xs text-slate-500">V</span>
              </div>
              <span id="hud-int-v-status" class="text-[10px] text-emerald-400 mt-0.5">Charged (94%)</span>
            </div>
          </div>
        </div>

        <!-- 4. GNSS Constellation & Fix -->
        <div class="bg-slate-900 border border-slate-800 rounded-lg p-3 shadow-md">
          <div class="flex items-center justify-between pb-2 border-b border-slate-800">
            <span class="text-xs font-bold tracking-wider text-slate-300 uppercase flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-emerald-400 inline-block"></span>
              GNSS Radar
            </span>
            <span id="hud-gnss-fix" class="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              3D FIX
            </span>
          </div>

          <div class="mt-2.5 flex items-center justify-between">
            <div class="text-[11px] text-slate-300">
              Satellites: <span id="hud-gnss-sats" class="font-mono font-bold text-emerald-400">18 / 24</span>
            </div>
            <div class="text-[11px] text-slate-400">
              HDOP: <span id="hud-gnss-hdop" class="font-mono text-slate-200">0.82</span>
            </div>
          </div>

          <div class="mt-2 bg-slate-950 p-2 rounded border border-slate-800/80 text-[10.5px] font-mono text-slate-300 flex justify-between items-center">
            <span>Lat: <span id="hud-gnss-lat" class="text-emerald-400">18.5204° N</span></span>
            <span>Lon: <span id="hud-gnss-lon" class="text-emerald-400">73.8567° E</span></span>
          </div>
        </div>

        <!-- 5. AIS-140 Indian State FOTA Migration -->
        <div class="bg-slate-900 border border-slate-800 rounded-lg p-3 shadow-md">
          <div class="flex items-center justify-between pb-2 border-b border-slate-800">
            <span class="text-xs font-bold tracking-wider text-purple-300 uppercase flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-purple-400 inline-block"></span>
              AIS-140 State FOTA
            </span>
            <button
              id="hud-btn-validate-fota"
              class="text-[10px] font-semibold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 transition-all flex items-center gap-1"
            >
              <span>Validate</span>
            </button>
          </div>

          <div class="mt-2.5 flex justify-between items-center text-[11px]">
            <span class="text-slate-400">Target State Server:</span>
            <span id="hud-fota-state-target" class="font-bold text-purple-300">MH (Maharashtra - MVD)</span>
          </div>

          <div class="mt-1 flex justify-between items-center text-[11px]">
            <span class="text-slate-400">Migration Stage:</span>
            <span id="hud-fota-stage" class="font-mono text-amber-300">Reconfiguration Complete</span>
          </div>

          <div class="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden mt-2 border border-slate-800">
            <div id="hud-fota-progress-bar" class="h-full bg-purple-500" style="width: 100%"></div>
          </div>
        </div>

      </div>
    `;

    // Elements
    this.csqVal = document.getElementById("hud-csq-val");
    this.csqDbm = document.getElementById("hud-csq-dbm");
    this.csqBar = document.getElementById("hud-csq-bar");
    this.cregBadge = document.getElementById("hud-creg-badge");
    
    this.cip0State = document.getElementById("hud-cip0-state");
    this.cip0Endpoint = document.getElementById("hud-cip0-endpoint");
    this.cip1Badge = document.getElementById("hud-cip1-badge");
    this.cip1Endpoint = document.getElementById("hud-cip1-endpoint");
    this.cip2State = document.getElementById("hud-cip2-state");
    this.cip3State = document.getElementById("hud-cip3-state");
    this.cip3Endpoint = document.getElementById("hud-cip3-endpoint");

    this.mainVVal = document.getElementById("hud-main-v-val");
    this.mainVStatus = document.getElementById("hud-main-v-status");
    this.intVVal = document.getElementById("hud-int-v-val");
    this.intVStatus = document.getElementById("hud-int-v-status");
    this.ignBadge = document.getElementById("hud-ign-badge");

    this.gnssFix = document.getElementById("hud-gnss-fix");
    this.gnssSats = document.getElementById("hud-gnss-sats");
    this.gnssHdop = document.getElementById("hud-gnss-hdop");
    this.gnssLat = document.getElementById("hud-gnss-lat");
    this.gnssLon = document.getElementById("hud-gnss-lon");

    this.fotaStateTarget = document.getElementById("hud-fota-state-target");
    this.fotaStage = document.getElementById("hud-fota-stage");
    this.fotaProgressBar = document.getElementById("hud-fota-progress-bar");

    this.btnAuditCip1 = document.getElementById("hud-btn-audit-cip1");
    this.btnValidateFota = document.getElementById("hud-btn-validate-fota");
  }

  _bindEvents() {
    this.btnAuditCip1.addEventListener("click", () => this.onAuditCip1());
    this.btnValidateFota.addEventListener("click", () => this.onValidateFota());
  }

  updateSnapshot(bb) {
    if (!bb) return;

    // 1. Modem & CSQ
    const csq = (bb.modem && typeof bb.modem.csq === "number") ? bb.modem.csq : bb.cellular_csq;
    if (typeof csq === "number") {
      this.csqVal.innerText = csq;
      const dbm = csq === 99 ? "Unknown" : `${(2 * csq) - 113} dBm`;
      this.csqDbm.innerText = dbm;
      const pct = Math.min(100, Math.round((csq / 31) * 100));
      this.csqBar.style.width = `${pct}%`;
      if (pct < 30) this.csqBar.className = "h-full bg-rose-500 transition-all duration-300";
      else if (pct < 60) this.csqBar.className = "h-full bg-amber-500 transition-all duration-300";
      else this.csqBar.className = "h-full bg-cyan-500 transition-all duration-300";
    }

    const creg = (bb.modem && bb.modem.creg_status !== undefined) ? bb.modem.creg_status : bb.cellular_creg;
    if (creg !== undefined && creg !== null) {
      const isReg = [1, 5].includes(creg);
      this.cregBadge.innerText = isReg ? "REGISTERED" : "SEARCHING";
      this.cregBadge.className = isReg
        ? "text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
        : "text-[10px] font-semibold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30";
    }

    // 2. Sockets & Dynamic CIP1 Status
    const primaryServer = (bb.server && bb.server.ip) ? `${bb.server.ip}:${bb.server.port}` : bb.primary_server;
    if (primaryServer && primaryServer !== "Unknown") {
      this.cip0Endpoint.innerText = primaryServer;
    }
    const secondaryServer = (bb.server && bb.server.cip1) ? bb.server.cip1 : bb.secondary_server;
    if (secondaryServer && secondaryServer !== "Unknown") {
      this.cip1Endpoint.innerText = secondaryServer;
    }

    const inferred = bb.inferred_parameters || (bb.modem && bb.modem.inferred_cip1);
    if (inferred && (inferred.tcp_cip1 || inferred === true)) {
      this.cip1Badge.innerText = "INFERRED ACTIVE";
      this.cip1Badge.className = "px-1 py-0.2 rounded text-[9px] bg-purple-500/30 text-purple-200 border border-purple-400/40 font-semibold pulse-purple";
    }

    // 3. Battery & Power
    const extV = (bb.battery && bb.battery.main_voltage) || bb.ext_battery_v;
    if (extV) {
      const numV = parseFloat(extV);
      if (!isNaN(numV)) {
        this.mainVVal.innerText = numV.toFixed(1);
        this.mainVStatus.innerText = numV > 16 ? "Normal (24V Truck/Bus)" : "Normal (12V LCV/Car)";
      }
    }
    const intV = (bb.battery && bb.battery.internal_voltage) || bb.int_battery_v;
    if (intV) {
      const numV = parseFloat(intV);
      if (!isNaN(numV)) {
        this.intVVal.innerText = numV.toFixed(2);
      }
    }

    const ign = (bb.battery && bb.battery.ignition !== undefined) ? bb.battery.ignition : bb.ignition;
    if (ign !== undefined && ign !== null) {
      const isOn = ign === 1 || ign === "ON (1)" || ign === true;
      this.ignBadge.innerText = isOn ? "IGN: ON" : "IGN: OFF";
      this.ignBadge.className = isOn
        ? "text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
        : "text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700";
    }

    // 4. GNSS
    const sats = (bb.gnss && bb.gnss.satellites_in_view !== undefined) ? `${bb.gnss.satellites_used || 0}/${bb.gnss.satellites_in_view}` : bb.gps_satellites;
    if (sats !== undefined && sats !== null) {
      this.gnssSats.innerText = String(sats);
    }
    const fixQ = (bb.gnss && bb.gnss.fix_type) || bb.gps_fix_quality;
    if (fixQ !== undefined && fixQ !== null) {
      this.gnssFix.innerText = (fixQ === 1 || fixQ === 2 || String(fixQ).includes("FIX") || String(fixQ).includes("3D")) ? "3D FIX" : "NO FIX";
    }

    // 5. FOTA
    const fotaPct = (bb.fota && bb.fota.progress_percent !== undefined) ? bb.fota.progress_percent : bb.fota_progress_pct;
    if (fotaPct !== undefined && fotaPct !== null) {
      const numPct = parseFloat(fotaPct);
      if (!isNaN(numPct)) {
        this.fotaProgressBar.style.width = `${numPct}%`;
      }
    }
  }
}
