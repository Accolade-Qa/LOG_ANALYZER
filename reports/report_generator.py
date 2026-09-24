import json
from collections import Counter
from pathlib import Path

from config_loader import config
from knowledge.knowledge_loader import get_rule_insight, get_suggested_fix


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


def generate_html_dashboard():
    """
    Generate a clean, professional HTML telemetry report.
    Pulls rule insights dynamically from parameters.yaml.
    """
    base_dir = Path(__file__).parent.parent
    raw_path = base_dir / config["paths"]["raw_anomalies_json"]
    dashboard_path = base_dir / config["paths"]["report_dashboard_html"]

    anomalies = _load_anomalies(raw_path)
    total = len(anomalies)

    severity_counter = Counter()
    top_types = Counter()
    pattern_cards = []

    for anomaly in anomalies:
        anomaly_id = anomaly.get("id") or anomaly.get("title") or "GPS_ANOMALY"
        severity = str(anomaly.get("severity", "medium")).lower()
        severity_counter[severity] += 1
        top_types[anomaly_id] += 1

    for anomaly_id, count in top_types.most_common():
        matching = [a for a in anomalies if (a.get("id") or a.get("title")) == anomaly_id]
        anomaly = matching[0]
        title = anomaly.get("title") or anomaly_id or "GPS Telemetry Anomaly"
        description = anomaly.get("description") or title
        severity = str(anomaly.get("severity", "medium")).lower()
        source = anomaly.get("source") or "GPS"

        # Dynamic Knowledge Retrieval from parameters.yaml
        insight = get_rule_insight(anomaly_id or title)
        fix = insight.get("fix") or get_suggested_fix(anomaly_id or title)

        meta = anomaly.get("metadata", {})
        status = str(meta.get("status", "RESOLVED")).upper()
        start_ln = meta.get("start_line", "N/A")
        end_ln = meta.get("end_line", "N/A")
        duration_sec = meta.get("duration_seconds")
        duration_str = f"{duration_sec:.2f} s" if duration_sec is not None else "N/A"
        
        start_raw = meta.get("start_raw_line") or meta.get("raw_line") or ""
        recovery_raw = meta.get("recovery_line") or meta.get("raw_line") or ""

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
            "why": insight.get("why", "Threshold or state condition breached."),
            "lookup": insight.get("lookup", "Inspect GPS hardware lines and NMEA parser logic."),
            "fix": fix,
            "start_raw": start_raw.strip(),
            "recovery_raw": recovery_raw.strip(),
        })

    cards_json = json.dumps(pattern_cards)
    high_cnt = severity_counter.get("high", 0) + severity_counter.get("critical", 0)
    med_cnt = severity_counter.get("medium", 0)
    low_cnt = severity_counter.get("low", 0)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GPS Telemetry Diagnostic Report</title>
    <style>
        :root {{
            --bg: #0f172a;
            --panel: #1e293b;
            --panel-border: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #38bdf8;
            --high: #ef4444;
            --medium: #f59e0b;
            --low: #10b981;
            --code-bg: #020617;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            padding: 32px 24px;
            line-height: 1.6;
        }}
        .container {{ max-width: 1100px; margin: 0 auto; }}
        
        /* Header */
        .header {{
            margin-bottom: 28px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--panel-border);
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

        /* Summary KPIs */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .kpi-card {{
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 16px 20px;
        }}
        .kpi-card .val {{
            font-size: 28px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        .kpi-card .lbl {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            font-weight: 600;
            margin-top: 2px;
        }}
        .val.high {{ color: var(--high); }}
        .val.medium {{ color: var(--medium); }}
        .val.low {{ color: var(--low); }}

        /* Filter Controls */
        .controls {{
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }}
        .search-input {{
            flex: 1;
            min-width: 240px;
            padding: 10px 14px;
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 6px;
            color: var(--text-primary);
            font-size: 14px;
            outline: none;
        }}
        .search-input:focus {{ border-color: var(--accent); }}

        .btn-group {{ display: flex; gap: 8px; }}
        .filter-btn {{
            padding: 8px 14px;
            background: var(--panel);
            border: 1px solid var(--panel-border);
            color: var(--text-secondary);
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .filter-btn:hover, .filter-btn.active {{
            background: var(--accent);
            color: #0f172a;
            border-color: var(--accent);
        }}

        /* Anomaly Cards */
        .cards-list {{ display: grid; gap: 20px; }}
        .card {{
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 24px;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        .card-title {{
            font-size: 17px;
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        /* Badges */
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .badge-high {{ background: rgba(239, 68, 68, 0.15); color: var(--high); border: 1px solid rgba(239, 68, 68, 0.3); }}
        .badge-medium {{ background: rgba(245, 158, 11, 0.15); color: var(--medium); border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-low {{ background: rgba(16, 185, 129, 0.15); color: var(--low); border: 1px solid rgba(16, 185, 129, 0.3); }}

        /* Meta Table */
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            background: rgba(15, 23, 42, 0.5);
            padding: 12px 16px;
            border-radius: 6px;
            font-size: 13px;
            margin-bottom: 16px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .meta-item .key {{ color: var(--text-secondary); display: block; font-size: 11px; text-transform: uppercase; }}
        .meta-item .val {{ font-weight: 600; color: var(--text-primary); }}

        /* Analysis Box */
        .analysis-section {{
            margin-bottom: 16px;
            font-size: 14px;
        }}
        .analysis-item {{ margin-bottom: 8px; }}
        .analysis-item strong {{ color: var(--accent); font-weight: 600; }}

        /* Code Trace Box */
        .code-box {{
            background: var(--code-bg);
            border: 1px solid var(--panel-border);
            border-radius: 6px;
            padding: 12px 16px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            color: #cbd5e1;
            overflow-x: auto;
        }}
        .code-label {{ font-family: sans-serif; font-size: 11px; font-weight: 700; margin-bottom: 4px; display: inline-block; }}
        .tag-start {{ color: var(--high); }}
        .tag-end {{ color: var(--low); }}
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <h1>GPS Telemetry Diagnostic Report</h1>
        <p>Automated Analysis & Stateful Telemetry Outage Tracking</p>
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
            <div class="val high">{high_cnt}</div>
            <div class="lbl">High Severity</div>
        </div>
        <div class="kpi-card">
            <div class="val medium">{med_cnt}</div>
            <div class="lbl">Medium Severity</div>
        </div>
        <div class="kpi-card">
            <div class="val low">{low_cnt}</div>
            <div class="lbl">Low Severity</div>
        </div>
    </div>

    <div class="controls">
        <input type="text" id="searchInput" class="search-input" placeholder="Search by rule ID, description, or raw log text...">
        <div class="btn-group" id="filterBtns">
            <button class="filter-btn active" data-filter="all">All</button>
            <button class="filter-btn" data-filter="high">High</button>
            <button class="filter-btn" data-filter="medium">Medium</button>
            <button class="filter-btn" data-filter="low">Low</button>
        </div>
    </div>

    <div class="cards-list" id="cardsContainer"></div>
</div>

<script>
    const data = {cards_json};
    const container = document.getElementById('cardsContainer');
    const searchInput = document.getElementById('searchInput');
    const filterBtns = document.getElementById('filterBtns');
    let currentFilter = 'all';

    function render() {{
        const q = searchInput.value.toLowerCase().trim();
        container.innerHTML = '';

        const filtered = data.filter(c => {{
            const matchFilter = currentFilter === 'all' || c.severity === currentFilter;
            const matchQuery = !q || 
                               c.title.toLowerCase().includes(q) || 
                               c.why.toLowerCase().includes(q) || 
                               c.fix.toLowerCase().includes(q) ||
                               c.start_raw.toLowerCase().includes(q) ||
                               c.recovery_raw.toLowerCase().includes(q);
            return matchFilter && matchQuery;
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
                logTraceHtml += `<div class="code-label tag-start">FAULT TRIGGER (Line ${{item.start_line}}):</div><div>${{item.start_raw}}</div>`;
            }}
            if (item.recovery_raw && item.recovery_raw !== item.start_raw) {{
                logTraceHtml += `<div class="code-label tag-end" style="margin-top:10px;">STATE RECOVERED (Line ${{item.end_line}}):</div><div>${{item.recovery_raw}}</div>`;
            }}

            card.innerHTML = `
                <div class="card-header">
                    <div class="card-title">${{item.title}}</div>
                    <span class="badge badge-${{item.severity}}">${{item.severity}}</span>
                </div>
                <div class="meta-grid">
                    <div class="meta-item"><span class="key">Occurrences</span><span class="val">${{item.count}}</span></div>
                    <div class="meta-item"><span class="key">Status</span><span class="val">${{item.status}}</span></div>
                    <div class="meta-item"><span class="key">Line Transition</span><span class="val">Line ${{item.start_line}} &rarr; ${{item.end_line}}</span></div>
                    <div class="meta-item"><span class="key">Outage Duration</span><span class="val">${{item.duration}}</span></div>
                </div>
                <div class="analysis-section">
                    <div class="analysis-item"><strong>Root Cause:</strong> ${{item.why}}</div>
                    <div class="analysis-item"><strong>Tester Inspection:</strong> ${{item.lookup}}</div>
                    <div class="analysis-item"><strong>Recommended Fix:</strong> ${{item.fix}}</div>
                </div>
                ${{logTraceHtml ? `<div class="code-box">${{logTraceHtml}}</div>` : ''}}
            `;
            container.appendChild(card);
        }});
    }}

    filterBtns.addEventListener('click', (e) => {{
        if (e.target.classList.contains('filter-btn')) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.getAttribute('data-filter');
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
