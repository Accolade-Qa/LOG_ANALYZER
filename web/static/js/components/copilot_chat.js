/**
 * Automotive Copilot Chat Component
 * Provides interactive Level 4 AI assistant with quick-action chips and clickable line citations.
 */

export class CopilotChat {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.onJumpLine = options.onJumpLine || (() => {});
    this.history = [];
    this.isLoading = false;

    this._initDom();
    this._bindEvents();
    this._addWelcomeMessage();
  }

  _initDom() {
    this.container.innerHTML = `
      <div class="flex flex-col h-full bg-[#0b1120] border border-slate-800 rounded-lg overflow-hidden shadow-2xl">
        <!-- Header -->
        <div class="flex items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-800">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse"></span>
            <span class="text-xs font-bold text-slate-200 uppercase tracking-wider">AI Automotive Copilot</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">Level 4 ReAct</span>
          </div>
          <button id="btn-clear-chat" class="text-[11px] text-slate-400 hover:text-white">Clear</button>
        </div>

        <!-- Quick Action Chips -->
        <div class="p-2 bg-slate-950/80 border-b border-slate-800 flex flex-wrap gap-1.5">
          <button class="copilot-chip text-[11px] px-2 py-0.5 rounded-full bg-slate-800/80 hover:bg-slate-700 text-cyan-300 border border-slate-700 transition-all text-left">
            ⚡ Why did FOTA fail?
          </button>
          <button class="copilot-chip text-[11px] px-2 py-0.5 rounded-full bg-slate-800/80 hover:bg-slate-700 text-purple-300 border border-slate-700 transition-all text-left">
            🔍 Audit CIP1 Dynamic State
          </button>
          <button class="copilot-chip text-[11px] px-2 py-0.5 rounded-full bg-slate-800/80 hover:bg-slate-700 text-emerald-300 border border-slate-700 transition-all text-left">
            🇮🇳 Validate State Migration
          </button>
          <button class="copilot-chip text-[11px] px-2 py-0.5 rounded-full bg-slate-800/80 hover:bg-slate-700 text-amber-300 border border-slate-700 transition-all text-left">
            🚨 Summarize Critical Anomalies
          </button>
        </div>

        <!-- Messages Area -->
        <div id="copilot-messages" class="flex-1 overflow-y-auto p-3 space-y-3 font-sans text-xs"></div>

        <!-- Input Area -->
        <div class="p-2 bg-slate-900 border-t border-slate-800">
          <form id="copilot-form" class="flex items-center gap-2">
            <input
              id="copilot-input"
              type="text"
              placeholder="Ask Copilot about AT commands, FOTA blocks, or DTCs..."
              class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              autocomplete="off"
            />
            <button
              id="copilot-send"
              type="submit"
              class="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-semibold transition-all flex items-center gap-1 shadow-md disabled:opacity-50"
            >
              <span>Send</span>
            </button>
          </form>
        </div>
      </div>
    `;

    this.messagesContainer = document.getElementById("copilot-messages");
    this.input = document.getElementById("copilot-input");
    this.sendBtn = document.getElementById("copilot-send");
    this.form = document.getElementById("copilot-form");
    this.btnClear = document.getElementById("btn-clear-chat");
  }

  _bindEvents() {
    this.form.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = this.input.value.trim();
      if (text) {
        this.submitQuery(text);
      }
    });

    this.btnClear.addEventListener("click", () => {
      this.messagesContainer.innerHTML = "";
      this._addWelcomeMessage();
    });

    // Quick action chips
    const chips = this.container.querySelectorAll(".copilot-chip");
    chips.forEach(chip => {
      chip.addEventListener("click", () => {
        let q = chip.innerText.replace(/^[^\w\s]+/, "").trim();
        this.submitQuery(q);
      });
    });

    // Delegate line jump clicks inside copilot messages
    this.messagesContainer.addEventListener("click", (e) => {
      const lineLink = e.target.closest("[data-jump-line]");
      if (lineLink) {
        e.preventDefault();
        const lineNum = parseInt(lineLink.getAttribute("data-jump-line"), 10);
        if (!isNaN(lineNum)) {
          this.onJumpLine(lineNum);
        }
      }
    });
  }

  _addWelcomeMessage() {
    this.appendMessage(
      "copilot",
      "Hello! I am your **Autonomous Automotive Copilot**. I have live access to the vehicle log stream, DTC knowledge base, and Indian State FOTA migration profiles. How can I assist your diagnostic triage today?"
    );
  }

  async submitQuery(question) {
    if (this.isLoading) return;
    this.isLoading = true;
    this.input.value = "";
    this.sendBtn.disabled = true;

    // 1. Add user bubble
    this.appendMessage("user", question);

    // 2. Add loading indicator
    const loadingId = this._addLoadingIndicator();

    try {
      const res = await fetch("/api/copilot/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: question }),
      });

      const data = await res.json();
      this._removeLoadingIndicator(loadingId);

      if (res.ok && data.response) {
        this.appendMessage("copilot", data.response);
      } else {
        this.appendMessage("copilot", `⚠️ **Diagnostic Error:** ${data.detail || "Unable to reach copilot engine."}`);
      }
    } catch (err) {
      this._removeLoadingIndicator(loadingId);
      this.appendMessage("copilot", `⚠️ **Network Error:** ${err.message}`);
    } finally {
      this.isLoading = false;
      this.sendBtn.disabled = false;
    }
  }

  appendMessage(sender, text) {
    const bubble = document.createElement("div");
    bubble.className = `flex ${sender === "user" ? "justify-end" : "justify-start"} animate-fadeIn`;

    const isUser = sender === "user";
    const formattedText = this._renderMarkdown(text);

    bubble.innerHTML = `
      <div class="max-w-[88%] rounded-xl p-3 shadow-md ${
        isUser
          ? "bg-cyan-600 text-white rounded-br-none"
          : "bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none copilot-body"
      }">
        <div class="flex items-center gap-1.5 mb-1 text-[10px] font-semibold text-slate-400">
          <span>${isUser ? "You" : "🤖 Automotive Copilot"}</span>
        </div>
        <div class="leading-relaxed">${formattedText}</div>
      </div>
    `;

    this.messagesContainer.appendChild(bubble);
    this.scrollToBottom();
  }

  _addLoadingIndicator() {
    const id = "loading-" + Date.now();
    const bubble = document.createElement("div");
    bubble.id = id;
    bubble.className = "flex justify-start";
    bubble.innerHTML = `
      <div class="bg-slate-900 border border-slate-800 rounded-xl rounded-bl-none p-3 text-slate-400 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
        <span class="text-xs">Analyzing log evidence & verifying DTCs...</span>
      </div>
    `;
    this.messagesContainer.appendChild(bubble);
    this.scrollToBottom();
    return id;
  }

  _removeLoadingIndicator(id) {
    const elem = document.getElementById(id);
    if (elem) elem.remove();
  }

  scrollToBottom() {
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }

  _renderMarkdown(md) {
    if (!md) return "";

    // 1. Convert Line references: "Line 245" or "line 245" to clickable links
    let html = md.replace(/\b[Ll]ine\s+(\d+)\b/g, '<a href="#" data-jump-line="$1" class="text-cyan-400 underline font-mono font-bold hover:text-cyan-300">Line $1</a>');

    // 2. Bold: **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-white">$1</strong>');

    // 3. Inline code: `code`
    html = html.replace(/`([^`]+)`/g, '<code class="bg-slate-950 px-1 py-0.5 rounded text-cyan-300 font-mono text-[11px]">$1</code>');

    // 4. Headers: ### text -> bold block
    html = html.replace(/^###\s*(.*)$/gm, '<div class="text-xs font-bold text-cyan-300 mt-2 mb-1">$1</div>');
    html = html.replace(/^##\s*(.*)$/gm, '<div class="text-sm font-bold text-cyan-400 mt-3 mb-1 border-b border-slate-800 pb-1">$1</div>');

    // 5. Bullet items: - item
    html = html.replace(/^\s*-\s+(.*)$/gm, '<div class="flex items-start gap-1.5 my-0.5"><span class="text-cyan-400">•</span><span>$1</span></div>');

    // 6. Line breaks
    html = html.replace(/\n\n/g, '<div class="h-2"></div>');

    return html;
  }
}
