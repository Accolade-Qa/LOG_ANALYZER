import json
from collections import Counter
from pathlib import Path

from config_loader import config
from knowledge.knowledge_loader import get_rule_insight, get_suggested_fix
from llm.summary_agent import generate_ai_summary


def _load_anomalies(raw_path):
    """Load raw anomalies JSON file."""
    if not raw_path.is_file():
        return []

    try:
        with open(raw_path, "r", encoding="utf-8") as f:
            anomalies = json.load(f)
        return anomalies if isinstance(anomalies, list) else []
    except Exception as e:
        print(f"Error reading anomalies JSON ({e})")
        return []


def generate_html_dashboard(log_path=None):
    """
    Generate an automotive multi-domain telemetry diagnostic report for QA & Firmware engineers.
    Combines stateful transition metrics, cross-domain correlations, and Agentic AI root-cause synthesis.
    """
    base_dir = Path(__file__).parent.parent
    raw_path = base_dir / config["paths"]["raw_anomalies_json"]
    dashboard_path = base_dir / config["paths"]["report_dashboard_html"]

    anomalies = _load_anomalies(raw_path)
    total = len(anomalies)

    # 1. Generate / Retrieve Agentic AI Root Cause Analysis & QA Guidance
    ai_guidance_md = generate_ai_summary(log_path=log_path) or ""

    # Convert markdown headings/bullets to HTML for embedding
    ai_guidance_html = (
        ai_guidance_md.replace("### ", "<h3>")
        .replace("#### ", "<h4>")
        .replace("- **", "<li><strong>")
        .replace("**: ", "</strong>: ")
        .replace("\n\n", "<br>")
    )

    severity_counter = Counter()
    domain_counter = Counter()
    top_types = Counter()
    pattern_cards = []

    for anomaly in anomalies:
        anomaly_id = anomaly.get("id") or anomaly.get("title") or "TELEMETRY_ANOMALY"
        severity = str(anomaly.get("severity", "medium")).lower()
        source = str(anomaly.get("source", "UNKNOWN")).upper()
        severity_counter[severity] += 1
        domain_counter[source] += 1
        top_types[anomaly_id] += 1

    for anomaly_id, count in top_types.most_common():
        matching = [a for a in anomalies if (a.get("id") or a.get("title")) == anomaly_id]
        anomaly = matching[0]
        title = anomaly.get("title") or anomaly_id or "Telemetry Anomaly"
        description = anomaly.get("description") or title
        severity = str(anomaly.get("severity", "medium")).lower()
        source = str(anomaly.get("source") or "SYSTEM").upper()

        # Dynamic Knowledge Retrieval
        insight = get_rule_insight(anomaly_id or title)
        fix = insight.get("fix") or get_suggested_fix(anomaly_id or title)
        why = insight.get("why", "Threshold or condition breached.")
        lookup = insight.get("lookup", "Inspect vehicle bus signals and firmware telemetry parser.")

        meta = anomaly.get("metadata", {})
        status = str(meta.get("status", "RESOLVED")).upper()
        start_ln = meta.get("start_line", "N/A")
        end_ln = meta.get("end_line", "N/A")
        duration_sec = meta.get("duration_seconds")
        duration_str = f"{duration_sec:.2f} s" if duration_sec is not None else "N/A"
        
        start_raw = meta.get("start_raw_line") or meta.get("raw_line") or ""
        recovery_raw = meta.get("recovery_line") or meta.get("raw_line") or ""

        # Cross-Domain Correlation Metadata
        correlation = anomaly.get("correlation", {})
        is_cascade = correlation.get("is_cascade_symptom", False)
        cascade_insight = correlation.get("diagnostic_insight", "")
        primary_trigger = correlation.get("primary_trigger", "")

        pattern_cards.append({
            "id": anomaly_id,
            "title": title,
            "description": description,
            "count": count,
            "severity": severity,
            "source": source,
            "status": status,
            "start_line": start_ln,
            "end_line": end_ln,
            "duration": duration_str,
            "why": why,
            "lookup": lookup,
            "fix": fix,
            "is_cascade": is_cascade,
            "cascade_insight": cascade_insight,
            "primary_trigger": primary_trigger,
            "start_raw": start_raw.strip(),
            "recovery_raw": recovery_raw.strip(),
        })

    cards_json = json.dumps(pattern_cards)
    crit_cnt = severity_counter.get("critical", 0)
    high_cnt = severity_counter.get("high", 0)
    med_cnt = severity_counter.get("medium", 0)
    low_cnt = severity_counter.get("low", 0)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Automotive Telematics Diagnostic & Agentic AI Root Cause Report</title>
    <style>
        :root {{
            --bg: #0b0f19;
            --panel: #131b2e;
            --panel-border: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #38bdf8;
            --critical: #dc2626;
            --high: #ef4444;
            --medium: #f59e0b;
            --low: #10b981;
            --cascade: #818cf8;
            --code-bg: #050811;
            --guide-bg: rgba(56, 189, 248, 0.04);
            --guide-border: rgba(56, 189, 248, 0.2);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            padding: 32px 24px;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        .header {{
            margin-bottom: 24px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--panel-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header h1 {{
            font-size: 24px;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.5px;
        }}
        .header p {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}
        .system-badge {{
            background: rgba(56, 189, 248, 0.15);
            border: 1px solid var(--accent);
            color: var(--accent);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }}

        /* Summary KPIs */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 14px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 14px 18px;
        }}
        .kpi-card .val {{
            font-size: 26px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        .kpi-card .lbl {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            font-weight: 600;
            margin-top: 2px;
        }}
        .val.critical {{ color: var(--critical); }}
        .val.high {{ color: var(--high); }}
        .val.medium {{ color: var(--medium); }}
        .val.low {{ color: var(--low); }}

        /* AI Guidance Box */
        .ai-guidance-card {{
            background: var(--guide-bg);
            border: 1px solid var(--guide-border);
            border-radius: 8px;
            padding: 22px 26px;
            margin-bottom: 28px;
            font-size: 14px;
            line-height: 1.7;
        }}
        .ai-guidance-card h3 {{ font-size: 17px; color: var(--accent); margin-bottom: 12px; font-weight: 700; }}
        .ai-guidance-card h4 {{ font-size: 14px; color: var(--text-primary); margin: 14px 0 6px 0; font-weight: 600; }}
        .ai-guidance-card ul {{ padding-left: 20px; margin-bottom: 10px; }}
        .ai-guidance-card li {{ margin-bottom: 6px; }}

        /* Filter Controls */
        .controls {{
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .search-input {{
            flex: 1;
            min-width: 260px;
            padding: 10px 14px;
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 6px;
            color: var(--text-primary);
            font-size: 14px;
            outline: none;
        }}
        .search-input:focus {{ border-color: var(--accent); }}

        .btn-group {{ display: flex; gap: 6px; flex-wrap: wrap; }}
        .filter-btn {{
            padding: 6px 12px;
            background: var(--panel);
            border: 1px solid var(--panel-border);
            color: var(--text-secondary);
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .filter-btn:hover, .filter-btn.active {{
            background: var(--accent);
            color: #0b0f19;
            border-color: var(--accent);
        }}

        /* Anomaly Cards */
        .cards-list {{ display: grid; gap: 20px; }}
        .card {{
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 22px;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 14px;
            gap: 12px;
        }}
        .card-title {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        /* Badges */
        .badges-wrapper {{ display: flex; gap: 6px; align-items: center; }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .badge-source {{ background: rgba(56, 189, 248, 0.12); color: var(--accent); border: 1px solid rgba(56, 189, 248, 0.3); }}
        .badge-critical {{ background: rgba(220, 38, 38, 0.15); color: var(--critical); border: 1px solid rgba(220, 38, 38, 0.4); }}
        .badge-high {{ background: rgba(239, 68, 68, 0.15); color: var(--high); border: 1px solid rgba(239, 68, 68, 0.3); }}
        .badge-medium {{ background: rgba(245, 158, 11, 0.15); color: var(--medium); border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-low {{ background: rgba(16, 185, 129, 0.15); color: var(--low); border: 1px solid rgba(16, 185, 129, 0.3); }}
        
        .cascade-banner {{
            background: rgba(129, 140, 248, 0.1);
            border-left: 3px solid var(--cascade);
            padding: 10px 14px;
            border-radius: 4px;
            margin-bottom: 14px;
            font-size: 13px;
            color: #c7d2fe;
        }}
        .cascade-banner strong {{ color: var(--cascade); }}

        /* Meta Table */
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 10px;
            background: rgba(5, 8, 17, 0.5);
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 12px;
            margin-bottom: 14px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .meta-item .key {{ color: var(--text-secondary); display: block; font-size: 10px; text-transform: uppercase; }}
        .meta-item .val {{ font-weight: 600; color: var(--text-primary); }}

        /* Analysis Box */
        .analysis-section {{
            margin-bottom: 14px;
            font-size: 13px;
            background: rgba(2, 6, 23, 0.4);
            padding: 12px 16px;
            border-radius: 6px;
            border-left: 3px solid var(--accent);
        }}
        .analysis-item {{ margin-bottom: 6px; }}
        .analysis-item:last-child {{ margin-bottom: 0; }}
        .analysis-item strong {{ color: var(--accent); font-weight: 600; }}

        /* Code Trace Box */
        .code-box {{
            background: var(--code-bg);
            border: 1px solid var(--panel-border);
            border-radius: 6px;
            padding: 10px 14px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 11px;
            color: #cbd5e1;
            overflow-x: auto;
        }}
        .code-label {{ font-family: sans-serif; font-size: 10px; font-weight: 700; margin-bottom: 4px; display: inline-block; }}
        .tag-start {{ color: var(--high); }}
        .tag-end {{ color: var(--low); }}
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <div>
            <h1>Automotive Telematics Diagnostic Report</h1>
            <p>Agentic AI Multi-Domain Root Cause Synthesis & Stateful Fault Correlation</p>
        </div>
        <div class="system-badge">6 Automotive Subsystems Active</div>
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="val">{total}</div>
            <div class="lbl">Total Anomalies</div>
        </div>
        <div class="kpi-card">
            <div class="val">{len(top_types)}</div>
            <div class="lbl">Unique Patterns</div>
        </div>
        <div class="kpi-card">
            <div class="val critical">{crit_cnt}</div>
            <div class="lbl">Critical</div>
        </div>
        <div class="kpi-card">
            <div class="val high">{high_cnt}</div>
            <div class="lbl">High Severity</div>
        </div>
        <div class="kpi-card">
            <div class="val medium">{med_cnt}</div>
            <div class="lbl">Medium</div>
        </div>
        <div class="kpi-card">
            <div class="val low">{low_cnt}</div>
            <div class="lbl">Low / Standby</div>
        </div>
    </div>

    <!-- Agentic AI Tester Guidance Card -->
    <div class="ai-guidance-card">
        {ai_guidance_html}
    </div>

    <div class="controls">
        <input type="text" id="searchInput" class="search-input" placeholder="Search by rule ID, root cause, or raw log text...">
        <div class="btn-group" id="domainBtns">
            <button class="filter-btn active" data-domain="all">All Domains</button>
            <button class="filter-btn" data-domain="CAN">CAN / UDS</button>
            <button class="filter-btn" data-domain="BATTERY">Battery / Power</button>
            <button class="filter-btn" data-domain="GPS">GNSS / GPS</button>
            <button class="filter-btn" data-domain="NET">Cellular / MQTT</button>
            <button class="filter-btn" data-domain="AIS">AIS-140</button>
            <button class="filter-btn" data-domain="SYSTEM">System RTOS</button>
        </div>
    </div>

    <div class="cards-list" id="cardsContainer"></div>
</div>

<script>
    const data = {cards_json};
    const container = document.getElementById('cardsContainer');
    const searchInput = document.getElementById('searchInput');
    const domainBtns = document.getElementById('domainBtns');
    let currentDomain = 'all';

    function render() {{
        const q = searchInput.value.toLowerCase().trim();
        container.innerHTML = '';

        const filtered = data.filter(c => {{
            const matchDomain = currentDomain === 'all' || c.source === currentDomain;
            const matchQuery = !q || 
                               c.title.toLowerCase().includes(q) || 
                               c.why.toLowerCase().includes(q) || 
                               c.lookup.toLowerCase().includes(q) ||
                               c.fix.toLowerCase().includes(q) ||
                               c.start_raw.toLowerCase().includes(q) ||
                               c.recovery_raw.toLowerCase().includes(q);
            return matchDomain && matchQuery;
        }});

        if (filtered.length === 0) {{
            container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-secondary);">No telemetry anomalies match the selected filter.</div>';
            return;
        }}

        filtered.forEach(item => {{
            const card = document.createElement('div');
            card.className = 'card';

            let logTraceHtml = '';
            if (item.start_raw) {{
                logTraceHtml += `<div class="code-label tag-start">🔴 FAULT TRIGGER (Line ${{item.start_line}}):</div><div>${{item.start_raw}}</div>`;
            }}
            if (item.recovery_raw && item.recovery_raw !== item.start_raw) {{
                logTraceHtml += `<div class="code-label tag-end" style="margin-top:8px;">🟢 STATE RECOVERED (Line ${{item.end_line}}):</div><div>${{item.recovery_raw}}</div>`;
            }}

            let cascadeHtml = '';
            if (item.is_cascade && item.cascade_insight) {{
                cascadeHtml = `<div class="cascade-banner"><strong>🔗 Cross-Domain Correlation:</strong> ${{item.cascade_insight}}</div>`;
            }}

            card.innerHTML = `
                <div class="card-header">
                    <div class="card-title">${{item.title}}</div>
                    <div class="badges-wrapper">
                        <span class="badge badge-source">${{item.source}}</span>
                        <span class="badge badge-${{item.severity}}">${{item.severity}}</span>
                    </div>
                </div>
                ${{cascadeHtml}}
                <div class="meta-grid">
                    <div class="meta-item"><span class="key">Occurrences</span><span class="val">${{item.count}}</span></div>
                    <div class="meta-item"><span class="key">Status</span><span class="val">${{item.status}}</span></div>
                    <div class="meta-item"><span class="key">Line Transition</span><span class="val">Line ${{item.start_line}} &rarr; ${{item.end_line}}</span></div>
                    <div class="meta-item"><span class="key">Outage Duration</span><span class="val">${{item.duration}}</span></div>
                </div>
                <div class="analysis-section">
                    <div class="analysis-item"><strong>❓ Root Cause Analysis:</strong> ${{item.why}}</div>
                    <div class="analysis-item"><strong>🔍 What Testers Should Inspect:</strong> ${{item.lookup}}</div>
                    <div class="analysis-item"><strong>🛠️ Step-by-Step QA Action:</strong> ${{item.fix}}</div>
                </div>
                ${{logTraceHtml ? `<div class="code-box">${{logTraceHtml}}</div>` : ''}}
            `;
            container.appendChild(card);
        }});
    }}

    domainBtns.addEventListener('click', (e) => {{
        if (e.target.classList.contains('filter-btn')) {{
            document.querySelectorAll('#domainBtns .filter-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentDomain = e.target.getAttribute('data-domain');
            render();
        }}
    }});

    searchInput.addEventListener('input', render);
    render();
</script>
</body>
</html>
"""

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return dashboard_path
