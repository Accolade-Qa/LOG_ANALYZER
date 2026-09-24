import json
from collections import Counter, defaultdict
from pathlib import Path

from config_loader import config
from knowledge.knowledge_loader import get_rule_insight, get_suggested_fix

DEFAULT_SEVERITY_ORDER = config.get(
    "severity_order", {"critical": 0, "high": 1, "medium": 2, "low": 3}
)


def _load_anomalies(raw_path):
    with open(raw_path, "r", encoding="utf-8") as f:
        anomalies = json.load(f)

    if not anomalies:
        return []

    if isinstance(anomalies[0], str):
        normalized = []
        for issue in anomalies:
            normalized.append(
                {
                    "id": None,
                    "title": issue,
                    "description": issue,
                    "severity": "medium",
                    "category": None,
                    "source": None,
                    "detected_at": None,
                    "metadata": {"raw_line": None, "event_type": None},
                }
            )
        return normalized

    return anomalies


def _group_counts(anomalies, key):
    counter = Counter()
    for anomaly in anomalies:
        counter[anomaly.get(key) or "unknown"] += 1
    return counter


def generate_report_cards():
    base_dir = Path(__file__).parent.parent
    raw_path = base_dir / config["paths"]["raw_anomalies_json"]
    report_path = base_dir / config["paths"]["report_cards_md"]

    if not raw_path.is_file():
        raise FileNotFoundError(f"Raw anomalies file not found: {raw_path}")

    anomalies = _load_anomalies(raw_path)
    total = len(anomalies)
    type_counter = _group_counts(anomalies, "id")
    severity_counter = _group_counts(anomalies, "severity")
    source_counter = _group_counts(anomalies, "source")

    sorted_types = sorted(
        type_counter.items(),
        key=lambda kv: (-kv[1], kv[0] or ""),
    )

    lines = ["# Anomaly Report Cards for QA Testers", f"**Total anomalies detected:** {total}", ""]
    lines.append("## Severity summary")
    for severity, count in sorted(
        severity_counter.items(), key=lambda kv: DEFAULT_SEVERITY_ORDER.get(kv[0], 99)
    ):
        lines.append(f"- **{severity.title()}**: {count}")
    lines.append("")

    lines.append("## Source summary")
    for source, count in sorted(
        source_counter.items(), key=lambda kv: (-kv[1], kv[0] or "")
    ):
        lines.append(f"- **{source or 'unknown'}**: {count}")
    lines.append("")

    for anomaly_id, count in sorted_types:
        matching = [
            a for a in anomalies if (a.get("id") or a.get("title")) == anomaly_id
        ]
        if not matching:
            continue
        anomaly = matching[0]
        title = anomaly.get("title") or anomaly_id or "Unknown anomaly"
        description = anomaly.get("description") or title
        severity = anomaly.get("severity", "medium")
        source = anomaly.get("source") or "unknown"

        # Dynamic Knowledge Retrieval
        insight = get_rule_insight(anomaly_id or title)
        fix = insight.get("fix") or get_suggested_fix(anomaly_id or title)

        meta = anomaly.get("metadata", {})
        status_str = meta.get("status", "RESOLVED").title()
        start_ln = meta.get("start_line", "N/A")
        end_ln = meta.get("end_line", "N/A")
        duration_sec = meta.get("duration_seconds")
        duration_str = f"{duration_sec:.2f} seconds" if duration_sec is not None else "N/A"

        start_raw = meta.get("start_raw_line") or meta.get("raw_line")
        recovery_raw = meta.get("recovery_line") or meta.get("raw_line")

        lines.extend(
            [
                "---",
                f"## {title}",
                f"- **Occurrences:** {count}",
                f"- **Severity:** {severity.title()}",
                f"- **Status:** {status_str}",
                f"- **Line Transition:** Line {start_ln} → Line {end_ln} (Outage Duration: {duration_str})",
                f"- **Source Subsystem:** {source}",
                f"- **Description:** {description}",
                f"- **Why It Happened:** {insight['why']}",
                f"- **What Testers Should Look Up:** {insight['lookup']}",
                f"- **Recommended Fix:** {fix}",
                "",
            ]
        )

        if start_raw or recovery_raw:
            lines.append("**Stateful Transition Evidence (Before vs After):**")
            if start_raw:
                lines.append(f"🔴 **Fault Triggered (Line {start_ln}):**")
                lines.append("```text")
                lines.append(start_raw.strip())
                lines.append("```")
            if recovery_raw and recovery_raw != start_raw:
                lines.append(f"🟢 **State Recovered (Line {end_ln}):**")
                lines.append("```text")
                lines.append(recovery_raw.strip())
                lines.append("```")
            lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return report_path


def generate_final_report():
    base_dir = Path(__file__).parent.parent
    raw_path = base_dir / config["paths"]["raw_anomalies_json"]
    report_path = base_dir / config["paths"]["final_report_md"]

    if not raw_path.is_file():
        raise FileNotFoundError(f"Raw anomalies file not found: {raw_path}")

    anomalies = _load_anomalies(raw_path)
    if not anomalies:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(
                "# Telemetry Analysis Executive Report\n\nNo anomalies were detected.\n"
            )
        return report_path

    total = len(anomalies)
    unique_types = len({(a.get("id") or a.get("title")) for a in anomalies})
    severity_counter = _group_counts(anomalies, "severity")
    source_counter = _group_counts(anomalies, "source")
    top_types = Counter((a.get("id") or a.get("title")) for a in anomalies)

    lines = [
        "# Telemetry Analysis QA Tester Executive Report",
        "",
        "## 1. Executive Summary",
        f"- Total anomalies detected: **{total}**",
        f"- Unique anomaly patterns: **{unique_types}**",
        "",
    ]
    lines.append("## 2. Severity Distribution")
    for severity, count in sorted(
        severity_counter.items(), key=lambda kv: DEFAULT_SEVERITY_ORDER.get(kv[0], 99)
    ):
        lines.append(f"- **{severity.title()}**: {count}")
    lines.append("")

    lines.append("## 3. Subsystem Breakdown")
    for source, count in sorted(
        source_counter.items(), key=lambda kv: (-kv[1], kv[0] or "")
    ):
        lines.append(f"- **{source or 'unknown'}**: {count}")
    lines.append("")

    lines.append("## 4. Top Anomaly Patterns & Tester Action Items")
    for anomaly_id, count in top_types.most_common(20):
        matching = [
            a for a in anomalies if (a.get("id") or a.get("title")) == anomaly_id
        ]
        anomaly = matching[0]
        title = anomaly.get("title") or anomaly_id or "Unknown anomaly"
        description = anomaly.get("description") or title
        severity = anomaly.get("severity", "medium")
        source = anomaly.get("source") or "unknown"

        # Dynamic Knowledge Retrieval
        insight = get_rule_insight(anomaly_id or title)
        fix = insight.get("fix") or get_suggested_fix(anomaly_id or title)

        meta = anomaly.get("metadata", {})
        status_str = meta.get("status", "RESOLVED").title()
        start_ln = meta.get("start_line", "N/A")
        end_ln = meta.get("end_line", "N/A")
        duration_sec = meta.get("duration_seconds")
        duration_str = f"{duration_sec:.2f} seconds" if duration_sec is not None else "N/A"

        start_raw = meta.get("start_raw_line") or meta.get("raw_line")
        recovery_raw = meta.get("recovery_line") or meta.get("raw_line")

        lines.extend(
            [
                "---",
                f"### {title}",
                f"- **Occurrences:** {count}",
                f"- **Severity:** {severity.title()}",
                f"- **Status:** {status_str}",
                f"- **Line Transition:** Line {start_ln} → Line {end_ln} (Outage Duration: {duration_str})",
                f"- **Subsystem:** {source}",
                f"- **Why It Happened:** {insight['why']}",
                f"- **What Testers Should Look Up:** {insight['lookup']}",
                f"- **Recommended Fix:** {fix}",
                "",
            ]
        )

        if start_raw or recovery_raw:
            lines.append("**Stateful Transition (Before vs After):**")
            if start_raw:
                lines.append(f"🔴 **Fault Start (Line {start_ln}):** `{start_raw.strip()}`")
            if recovery_raw and recovery_raw != start_raw:
                lines.append(f"🟢 **Recovery Line (Line {end_ln}):** `{recovery_raw.strip()}`")
            lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return report_path


def generate_html_dashboard():
    """Generate an interactive HTML report dashboard dynamically loading from knowledge base."""
    base_dir = Path(__file__).parent.parent
    raw_path = base_dir / config["paths"]["raw_anomalies_json"]
    dashboard_path = base_dir / config["paths"]["report_dashboard_html"]

    if not raw_path.is_file():
        return dashboard_path

    anomalies = _load_anomalies(raw_path)
    total = len(anomalies)
    severity_counter = _group_counts(anomalies, "severity")
    top_types = Counter((a.get("id") or a.get("title")) for a in anomalies)

    pattern_cards = []
    for anomaly_id, count in top_types.most_common():
        matching = [a for a in anomalies if (a.get("id") or a.get("title")) == anomaly_id]
        anomaly = matching[0]
        title = anomaly.get("title") or anomaly_id or "Unknown anomaly"
        description = anomaly.get("description") or title
        severity = anomaly.get("severity", "medium").lower()
        source = anomaly.get("source") or "GENERAL"

        # Dynamic Knowledge Retrieval
        insight = get_rule_insight(anomaly_id or title)
        fix = insight.get("fix") or get_suggested_fix(anomaly_id or title)

        meta = anomaly.get("metadata", {})
        status = meta.get("status", "RESOLVED").upper()
        start_ln = meta.get("start_line", "N/A")
        end_ln = meta.get("end_line", "N/A")
        duration_sec = meta.get("duration_seconds", "N/A")
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
            "duration": duration_sec,
            "why": insight["why"],
            "lookup": insight["lookup"],
            "fix": fix,
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
    <title>Telemetry Analysis QA Tester Dashboard</title>
    <style>
        :root {{
            --bg-dark: #0b0f19;
            --card-bg: #151d2a;
            --accent: #38bdf8;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: #263346;
            --critical: #ef4444;
            --high: #f97316;
            --medium: #eab308;
            --low: #22c55e;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}
        body {{ background-color: var(--bg-dark); color: var(--text-main); padding: 24px; line-height: 1.5; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }}
        .title h1 {{ font-size: 24px; font-weight: 700; color: var(--accent); display: flex; align-items: center; gap: 10px; }}
        .title p {{ font-size: 14px; color: var(--text-muted); }}

        /* KPI Cards */
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-bottom: 24px; }}
        .kpi-card {{ background: var(--card-bg); padding: 16px; border-radius: 12px; border: 1px solid var(--border); text-align: center; }}
        .kpi-card .num {{ font-size: 28px; font-weight: 800; }}
        .kpi-card .label {{ font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600; letter-spacing: 0.5px; }}

        .critical {{ color: var(--critical); }}
        .high {{ color: var(--high); }}
        .medium {{ color: var(--medium); }}
        .low {{ color: var(--low); }}

        /* Controls & Filters */
        .controls {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; align-items: center; justify-content: space-between; background: var(--card-bg); padding: 16px; border-radius: 12px; border: 1px solid var(--border); }}
        .search-box {{ flex: 1; min-width: 250px; position: relative; }}
        .search-box input {{ width: 100%; padding: 10px 16px; background: #0b0f19; border: 1px solid var(--border); border-radius: 8px; color: var(--text-main); font-size: 14px; outline: none; }}
        .search-box input:focus {{ border-color: var(--accent); }}

        .filter-buttons {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .btn {{ padding: 8px 14px; border: 1px solid var(--border); background: #0b0f19; color: var(--text-main); border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s; }}
        .btn:hover, .btn.active {{ background: var(--accent); color: #000; border-color: var(--accent); }}

        /* Pattern Cards */
        .cards-container {{ display: grid; gap: 16px; }}
        .anomaly-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; transition: transform 0.2s, border-color 0.2s; }}
        .anomaly-card:hover {{ border-color: var(--accent); }}
        .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; gap: 12px; }}
        .card-title {{ font-size: 16px; font-weight: 700; color: #fff; }}
        .badge {{ padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; }}
        .badge-critical {{ background: rgba(239, 68, 68, 0.2); color: var(--critical); border: 1px solid var(--critical); }}
        .badge-high {{ background: rgba(249, 115, 22, 0.2); color: var(--high); border: 1px solid var(--high); }}
        .badge-medium {{ background: rgba(234, 179, 8, 0.2); color: var(--medium); border: 1px solid var(--medium); }}
        .badge-low {{ background: rgba(34, 197, 94, 0.2); color: var(--low); border: 1px solid var(--low); }}

        .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; background: rgba(11, 15, 25, 0.6); padding: 12px; border-radius: 8px; margin-bottom: 14px; font-size: 13px; border: 1px solid rgba(255,255,255,0.05); }}
        .meta-item .val {{ font-weight: 600; color: var(--accent); }}

        .insight-box {{ background: rgba(14, 165, 233, 0.08); border-left: 4px solid var(--accent); padding: 12px 16px; border-radius: 6px; font-size: 13px; margin-bottom: 14px; }}
        .insight-box div {{ margin-bottom: 4px; }}
        .insight-box div:last-child {{ margin-bottom: 0; }}

        .transition-box {{ background: #070a11; border-radius: 8px; padding: 14px; font-family: monospace; font-size: 12px; color: #a5b4fc; border: 1px solid var(--border); overflow-x: auto; }}
        .log-tag {{ font-weight: 700; margin-bottom: 4px; display: inline-block; font-family: sans-serif; font-size: 11px; }}
        .tag-start {{ color: var(--critical); }}
        .tag-rec {{ color: var(--low); }}
    </style>
</head>
<body>

    <div class="header">
        <div class="title">
            <h1>🔬 QA Tester Telemetry Dashboard</h1>
            <p>Stateful Transition Analysis & Dynamic Knowledge Base Insights</p>
        </div>
        <div>
            <span class="badge badge-medium">LOG_ANALYZER v2.0</span>
        </div>
    </div>

    <div class="kpi-grid">
        <div class="kpi-card"><div class="num" style="color: var(--accent);">{total}</div><div class="label">Total Events</div></div>
        <div class="kpi-card"><div class="num">{len(top_types)}</div><div class="label">Unique Patterns</div></div>
        <div class="kpi-card"><div class="num critical">{crit_cnt}</div><div class="label">Critical</div></div>
        <div class="kpi-card"><div class="num high">{high_cnt}</div><div class="label">High</div></div>
        <div class="kpi-card"><div class="num medium">{med_cnt}</div><div class="label">Medium</div></div>
        <div class="kpi-card"><div class="num low">{low_cnt}</div><div class="label">Low</div></div>
    </div>

    <div class="controls">
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="🔍 Search anomaly titles, register codes, log line keywords...">
        </div>
        <div class="filter-buttons" id="filterBtns">
            <button class="btn active" data-filter="all">All</button>
            <button class="btn" data-filter="critical">Critical</button>
            <button class="btn" data-filter="high">High</button>
            <button class="btn" data-filter="medium">Medium</button>
            <button class="btn" data-filter="low">Low</button>
        </div>
    </div>

    <div class="cards-container" id="cardsContainer"></div>

    <script>
        const cardsData = {cards_json};
        const container = document.getElementById('cardsContainer');
        const searchInput = document.getElementById('searchInput');
        const filterBtns = document.getElementById('filterBtns');

        let currentFilter = 'all';

        function renderCards() {{
            const query = searchInput.value.toLowerCase().trim();
            container.innerHTML = '';

            const filtered = cardsData.filter(card => {{
                const matchesFilter = currentFilter === 'all' || 
                                     card.severity === currentFilter || 
                                     card.source.toLowerCase() === currentFilter;
                
                const matchesSearch = !query || 
                                     card.title.toLowerCase().includes(query) || 
                                     card.description.toLowerCase().includes(query) ||
                                     card.why.toLowerCase().includes(query) ||
                                     card.lookup.toLowerCase().includes(query) ||
                                     card.start_raw.toLowerCase().includes(query) ||
                                     card.recovery_raw.toLowerCase().includes(query);

                return matchesFilter && matchesSearch;
            }});

            if (filtered.length === 0) {{
                container.innerHTML = `<div style="text-align:center; padding: 40px; color: var(--text-muted);">No anomalies match your search criteria.</div>`;
                return;
            }}

            filtered.forEach(card => {{
                const el = document.createElement('div');
                el.className = 'anomaly-card';
                
                let transitionHtml = '';
                if (card.start_raw) {{
                    transitionHtml += `<div class="log-tag tag-start">🔴 FAULT START (Line ${{card.start_line}}):</div><div>${{card.start_raw}}</div>`;
                }}
                if (card.recovery_raw && card.recovery_raw !== card.start_raw) {{
                    transitionHtml += `<div class="log-tag tag-rec" style="margin-top:8px;">🟢 RECOVERY LINE (Line ${{card.end_line}}):</div><div>${{card.recovery_raw}}</div>`;
                }}
                if (!transitionHtml) {{
                    transitionHtml = 'No transition log captured.';
                }}

                el.innerHTML = `
                    <div class="card-header">
                        <div class="card-title">${{card.title}}</div>
                        <span class="badge badge-${{card.severity}}">${{card.severity}}</span>
                    </div>
                    <div class="meta-grid">
                        <div class="meta-item">Occurrences: <span class="val">${{card.count}}</span></div>
                        <div class="meta-item">Subsystem: <span class="val">${{card.source}}</span></div>
                        <div class="meta-item">Status: <span class="val">${{card.status}}</span></div>
                        <div class="meta-item">Transition: <span class="val">Line ${{card.start_line}} → ${{card.end_line}}</span></div>
                        <div class="meta-item">Outage Duration: <span class="val">${{card.duration}}s</span></div>
                    </div>
                    <div class="insight-box">
                        <div><strong>❓ Why It Happened:</strong> ${{card.why}}</div>
                        <div><strong>🔍 What Testers Should Look Up:</strong> ${{card.lookup}}</div>
                        <div><strong>💡 Recommended Remediation:</strong> ${{card.fix}}</div>
                    </div>
                    <div class="transition-box">
                        ${{transitionHtml}}
                    </div>
                `;
                container.appendChild(el);
            }});
        }}

        filterBtns.addEventListener('click', (e) => {{
            if (e.target.classList.contains('btn')) {{
                document.querySelectorAll('#filterBtns .btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                currentFilter = e.target.getAttribute('data-filter');
                renderCards();
            }}
        }});

        searchInput.addEventListener('input', renderCards);
        renderCards();
    </script>
</body>
</html>
"""

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return dashboard_path


if __name__ == "__main__":
    generate_report_cards()
    generate_final_report()
    generate_html_dashboard()
