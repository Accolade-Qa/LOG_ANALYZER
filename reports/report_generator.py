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


def generate_html_dashboard(log_path=None, discovered_anomalies=None):
    """
    Generate an automotive multi-domain telemetry diagnostic report for QA & Firmware engineers.
    Combines stateful transition metrics, cross-domain correlations, unsupervised discovered anomalies,
    and Level 4 Agentic AI root-cause synthesis.
    """
    base_dir = Path(__file__).parent.parent
    raw_path = base_dir / config["paths"]["raw_anomalies_json"]
    dashboard_path = base_dir / config["paths"]["report_dashboard_html"]

    anomalies = _load_anomalies(raw_path)
    novel_list = list(discovered_anomalies or [])
    combined_list = anomalies + novel_list
    total = len(combined_list)

    # 1. Generate / Retrieve Level 4 Agentic AI Root Cause Analysis & QA Guidance
    ai_guidance_md = generate_ai_summary(log_path=log_path, discovered_anomalies=novel_list) or ""

    # Convert markdown formatting to clean semantic HTML for embedding
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

    for item in combined_list:
        anomaly_id = item.get("id") or item.get("title") or "TELEMETRY_ANOMALY"
        severity = str(item.get("severity", "medium")).lower()
        source = str(item.get("source", "UNKNOWN")).upper()
        severity_counter[severity] += 1
        domain_counter[source] += 1
        top_types[anomaly_id] += 1

    for anomaly_id, count in top_types.most_common():
        matching = [a for a in combined_list if (a.get("id") or a.get("title")) == anomaly_id]
        item = matching[0]
        title = item.get("title") or anomaly_id or "Telemetry Anomaly"
        description = item.get("description") or title
        severity = str(item.get("severity", "medium")).lower()
        source = str(item.get("source") or "SYSTEM").upper()
        category = str(item.get("category", "")).lower()

        # Dynamic Knowledge Retrieval
        insight = get_rule_insight(anomaly_id or title)
        fix = insight.get("fix") or get_suggested_fix(anomaly_id or title)
        why = insight.get("why")
        if category == "novel_discovery":
            why = f"Unsupervised Discovery: Recurring unhandled error token '{item.get('metadata', {}).get('template')}'."
            lookup = "Inspect peripheral driver source code, RTOS buffer limits, and bus hardware pull-ups."
            fix = "Review code for unhandled exception and add telemetry parameter rule to knowledge base."
        else:
            if not why or why == "Threshold or condition breached.":
                why = item.get("description") or "Threshold or condition breached."
            lookup = insight.get("lookup", "Inspect vehicle bus signals and firmware telemetry parser.")

        meta = item.get("metadata", {})
        status = str(meta.get("status", "RESOLVED")).upper()
        start_ln = meta.get("start_line", "N/A")
        end_ln = meta.get("end_line", "N/A")
        duration_sec = meta.get("duration_seconds")
        duration_str = f"{duration_sec:.2f} s" if duration_sec is not None else "N/A"
        
        start_raw = meta.get("start_raw_line") or meta.get("raw_line") or ""
        recovery_raw = meta.get("recovery_line") or meta.get("raw_line") or ""

        # Sample traces for novel discoveries
        sample_traces = meta.get("sample_traces", [])
        if not start_raw and sample_traces:
            start_raw = sample_traces[0]
        if not recovery_raw and len(sample_traces) > 1:
            recovery_raw = sample_traces[-1]

        # Cross-Domain Correlation Metadata
        correlation = item.get("correlation", {})
        is_cascade = correlation.get("is_cascade_symptom", False)
        cascade_insight = correlation.get("diagnostic_insight", "")
        primary_trigger = correlation.get("primary_trigger", "")

        pattern_cards.append({
            "id": anomaly_id,
            "title": title,
            "description": description,
            "count": meta.get("occurrence_count", count),
            "severity": severity,
            "source": source,
            "category": category,
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
    novel_cnt = len(novel_list)
    log_name = Path(log_path).name if log_path else "Automotive Log Stream"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LOG_ANALYZER | Executive Automotive Diagnostics</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #070a12;
            --bg-glass: rgba(15, 23, 42, 0.7);
            --card-bg: rgba(26, 36, 56, 0.65);
            --card-border: rgba(255, 255, 255, 0.08);
            --card-hover-border: rgba(56, 189, 248, 0.4);
            
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.25);
            
            --critical: #f43f5e;
            --critical-glow: rgba(244, 63, 94, 0.2);
            --high: #fb7185;
            --medium: #fbbf24;
            --low: #34d399;
            --cascade: #818cf8;
            --novel: #c084fc;
            
            --code-bg: #030712;
            --code-border: rgba(255, 255, 255, 0.06);
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            background: var(--bg);
            background-image: 
                radial-gradient(at 10% 10%, rgba(56, 189, 248, 0.08) 0px, transparent 50%),
                radial-gradient(at 90% 20%, rgba(192, 132, 252, 0.06) 0px, transparent 50%),
                radial-gradient(at 50% 90%, rgba(129, 140, 248, 0.05) 0px, transparent 50%);
            background-attachment: fixed;
            color: var(--text-primary);
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            padding: 32px 20px;
            min-height: 100vh;
            line-height: 1.6;
        }}
        
        .container {{ max-width: 1320px; margin: 0 auto; }}
        
        /* Modern Header Bar */
        .header {{
            background: var(--bg-glass);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px 30px;
            margin-bottom: 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
            box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.5);
        }}
        
        .brand-section {{ display: flex; align-items: center; gap: 16px; }}
        .brand-icon {{
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, #0284c7, #6366f1);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 20px rgba(56, 189, 248, 0.4);
        }}
        .brand-icon svg {{ width: 26px; height: 26px; fill: none; stroke: #fff; stroke-width: 2; }}
        
        .header-titles h1 {{
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #f8fafc, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header-titles p {{
            font-size: 13px;
            color: var(--text-secondary);
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 2px;
        }}
        
        .live-dot {{
            width: 8px;
            height: 8px;
            background-color: #10b981;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 10px #10b981;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
            70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}
        
        .badges-header {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .header-badge {{
            padding: 8px 16px;
            border-radius: 30px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.3px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .badge-system {{
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.3);
            color: var(--accent);
        }}
        .badge-ai {{
            background: rgba(192, 132, 252, 0.12);
            border: 1px solid rgba(192, 132, 252, 0.3);
            color: var(--novel);
        }}
        
        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .kpi-card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 20px 22px;
            position: relative;
            overflow: hidden;
            transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
        }}
        .kpi-card:hover {{
            transform: translateY(-3px);
            border-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 12px 30px -10px rgba(0, 0, 0, 0.6);
        }}
        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: var(--accent);
            opacity: 0.8;
        }}
        .kpi-card.critical-kpi::before {{ background: var(--critical); }}
        .kpi-card.high-kpi::before {{ background: var(--high); }}
        .kpi-card.medium-kpi::before {{ background: var(--medium); }}
        .kpi-card.low-kpi::before {{ background: var(--low); }}
        .kpi-card.novel-kpi::before {{ background: var(--novel); }}
        
        .kpi-card .val {{
            font-size: 32px;
            font-weight: 800;
            letter-spacing: -1px;
            color: var(--text-primary);
            line-height: 1;
        }}
        .kpi-card .lbl {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-secondary);
            font-weight: 700;
            margin-top: 8px;
        }}
        .val.critical {{ color: var(--critical); text-shadow: 0 0 12px var(--critical-glow); }}
        .val.high {{ color: var(--high); }}
        .val.medium {{ color: var(--medium); }}
        .val.low {{ color: var(--low); }}
        .val.novel {{ color: var(--novel); }}
        
        /* Agentic AI Section */
        .ai-guidance-card {{
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.85), rgba(30, 41, 59, 0.7));
            backdrop-filter: blur(16px);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 32px;
            box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
            position: relative;
        }}
        .ai-guidance-card::after {{
            content: '';
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
            background: linear-gradient(to bottom, var(--accent), var(--novel));
            border-radius: 16px 0 0 16px;
        }}
        .ai-header-bar {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 18px;
            padding-bottom: 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .ai-spark-icon {{
            width: 32px; height: 32px;
            background: rgba(56, 189, 248, 0.15);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            color: var(--accent);
        }}
        .ai-title-text {{
            font-size: 16px;
            font-weight: 700;
            color: var(--accent);
            letter-spacing: -0.2px;
        }}
        .ai-content {{ font-size: 14px; color: #cbd5e1; line-height: 1.7; }}
        .ai-content h3 {{ font-size: 16px; color: var(--accent); margin: 16px 0 8px 0; font-weight: 700; }}
        .ai-content h4 {{ font-size: 14px; color: var(--text-primary); margin: 12px 0 6px 0; font-weight: 600; }}
        .ai-content ul {{ padding-left: 20px; margin-bottom: 12px; }}
        .ai-content li {{ margin-bottom: 6px; }}
        .ai-content strong {{ color: #f1f5f9; }}
        
        /* Filter Controls */
        .controls-bar {{
            background: var(--bg-glass);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 16px 20px;
            margin-bottom: 28px;
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
        }}
        
        .search-box {{
            position: relative;
            flex: 1;
            min-width: 280px;
        }}
        .search-box svg {{
            position: absolute;
            left: 14px; top: 50%;
            transform: translateY(-50%);
            width: 18px; height: 18px;
            stroke: var(--text-muted);
            fill: none;
        }}
        .search-input {{
            width: 100%;
            padding: 11px 16px 11px 42px;
            background: rgba(3, 7, 18, 0.6);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            color: var(--text-primary);
            font-size: 14px;
            font-family: inherit;
            outline: none;
            transition: all 0.2s ease;
        }}
        .search-input:focus {{
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
            background: rgba(3, 7, 18, 0.9);
        }}
        
        .btn-tabs {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
        .tab-btn {{
            padding: 8px 16px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--card-border);
            color: var(--text-secondary);
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .tab-btn:hover {{
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-primary);
        }}
        .tab-btn.active {{
            background: var(--accent);
            color: #030712;
            border-color: var(--accent);
            font-weight: 700;
            box-shadow: 0 4px 14px rgba(56, 189, 248, 0.3);
        }}
        .tab-btn.novel-tab.active {{
            background: var(--novel);
            color: #030712;
            border-color: var(--novel);
            box-shadow: 0 4px 14px rgba(192, 132, 252, 0.3);
        }}
        
        /* Cards List */
        .cards-list {{ display: grid; gap: 20px; }}
        .card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 24px;
            position: relative;
            transition: all 0.25s ease;
        }}
        .card:hover {{
            border-color: var(--card-hover-border);
            box-shadow: 0 14px 35px -10px rgba(0, 0, 0, 0.6);
        }}
        
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 16px;
            margin-bottom: 16px;
        }}
        .card-title-group {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
        .card-title {{
            font-size: 17px;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.3px;
        }}
        
        .badges-wrapper {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.4px;
            text-transform: uppercase;
        }}
        .badge-source {{ background: rgba(56, 189, 248, 0.12); color: var(--accent); border: 1px solid rgba(56, 189, 248, 0.3); }}
        .badge-novel {{ background: rgba(192, 132, 252, 0.15); color: var(--novel); border: 1px solid rgba(192, 132, 252, 0.4); }}
        .badge-critical {{ background: rgba(244, 63, 94, 0.15); color: var(--critical); border: 1px solid rgba(244, 63, 94, 0.4); }}
        .badge-high {{ background: rgba(251, 113, 133, 0.15); color: var(--high); border: 1px solid rgba(251, 113, 133, 0.3); }}
        .badge-medium {{ background: rgba(251, 191, 36, 0.15); color: var(--medium); border: 1px solid rgba(251, 191, 36, 0.3); }}
        .badge-low {{ background: rgba(52, 211, 153, 0.15); color: var(--low); border: 1px solid rgba(52, 211, 153, 0.3); }}
        
        /* Cascade Banner */
        .cascade-banner {{
            background: linear-gradient(90deg, rgba(129, 140, 248, 0.12), rgba(129, 140, 248, 0.04));
            border-left: 4px solid var(--cascade);
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
            font-size: 13px;
            color: #c7d2fe;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .cascade-banner svg {{ width: 20px; height: 20px; stroke: var(--cascade); flex-shrink: 0; fill: none; }}
        .cascade-banner strong {{ color: #e0e7ff; font-weight: 700; }}
        
        /* Meta Grid */
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            background: rgba(3, 7, 18, 0.5);
            padding: 12px 18px;
            border-radius: 10px;
            font-size: 13px;
            margin-bottom: 18px;
            border: 1px solid rgba(255, 255, 255, 0.04);
        }}
        .meta-item .key {{ color: var(--text-muted); font-size: 10px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; display: block; margin-bottom: 2px; }}
        .meta-item .val {{ font-weight: 600; color: var(--text-primary); font-family: 'JetBrains Mono', monospace; font-size: 12px; }}
        
        /* Diagnostic Analysis Box */
        .analysis-box {{
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-left: 4px solid var(--accent);
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 18px;
            font-size: 13px;
            line-height: 1.6;
        }}
        .analysis-box.novel-box {{ border-left-color: var(--novel); }}
        .analysis-row {{ margin-bottom: 10px; display: flex; gap: 8px; flex-direction: column; }}
        .analysis-row:last-child {{ margin-bottom: 0; }}
        .analysis-row .label {{ color: var(--accent); font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.4px; }}
        .novel-box .analysis-row .label {{ color: var(--novel); }}
        .analysis-row .text {{ color: #cbd5e1; }}
        
        /* Code Box */
        .code-box {{
            background: var(--code-bg);
            border: 1px solid var(--code-border);
            border-radius: 10px;
            padding: 14px 18px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: #e2e8f0;
            overflow-x: auto;
        }}
        .code-header {{
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .tag-start {{ color: var(--high); }}
        .tag-end {{ color: var(--low); }}
        .code-line {{ padding: 2px 0; white-space: pre-wrap; word-break: break-all; }}
        
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
            background: var(--card-bg);
            border: 1px dashed var(--card-border);
            border-radius: 14px;
        }}
    </style>
</head>
<body>

<div class="container">
    <!-- Header -->
    <header class="header">
        <div class="brand-section">
            <div class="brand-icon">
                <svg viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
            </div>
            <div class="header-titles">
                <h1>LOG_ANALYZER <span style="font-weight: 400; font-size: 16px; opacity: 0.7;">| Executive Diagnostic Dashboard</span></h1>
                <p><span class="live-dot"></span> Ingested: <strong>{log_name}</strong> • Level 4 Agentic AI Active</p>
            </div>
        </div>
        <div class="badges-header">
            <div class="header-badge badge-system">⚡ 6 Subsystem Domain Agents</div>
            <div class="header-badge badge-ai">🧠 Autonomous ReAct AI</div>
        </div>
    </header>

    <!-- KPI Summary Grid -->
    <section class="kpi-grid">
        <div class="kpi-card">
            <div class="val">{total}</div>
            <div class="lbl">Total Anomalies</div>
        </div>
        <div class="kpi-card novel-kpi">
            <div class="val novel">{novel_cnt}</div>
            <div class="lbl">Zero-Shot Novel</div>
        </div>
        <div class="kpi-card critical-kpi">
            <div class="val critical">{crit_cnt}</div>
            <div class="lbl">Critical DTCs</div>
        </div>
        <div class="kpi-card high-kpi">
            <div class="val high">{high_cnt}</div>
            <div class="lbl">High Severity</div>
        </div>
        <div class="kpi-card medium-kpi">
            <div class="val medium">{med_cnt}</div>
            <div class="lbl">Medium Severity</div>
        </div>
        <div class="kpi-card low-kpi">
            <div class="val low">{low_cnt}</div>
            <div class="lbl">Low / Standby</div>
        </div>
    </section>

    <!-- Level 4 Agentic AI Executive Guidance -->
    <section class="ai-guidance-card">
        <div class="ai-header-bar">
            <div class="ai-spark-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            </div>
            <div class="ai-title-text">Level 4 Autonomous AI Diagnostic Triage & QA Guidance</div>
        </div>
        <div class="ai-content">
            {ai_guidance_html}
        </div>
    </section>

    <!-- Controls Bar -->
    <section class="controls-bar">
        <div class="search-box">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" id="searchInput" class="search-input" placeholder="Search by anomaly ID, DTC code, root cause, or log snippet...">
        </div>
        <div class="btn-tabs" id="domainBtns">
            <button class="tab-btn active" data-domain="all">All ({total})</button>
            <button class="tab-btn novel-tab" data-domain="novel">Zero-Shot ({novel_cnt})</button>
            <button class="tab-btn" data-domain="CAN">CAN / UDS</button>
            <button class="tab-btn" data-domain="BATTERY">Battery</button>
            <button class="tab-btn" data-domain="GPS">GNSS / GPS</button>
            <button class="tab-btn" data-domain="NET">Cellular</button>
            <button class="tab-btn" data-domain="AIS">AIS-140</button>
            <button class="tab-btn" data-domain="SYSTEM">System RTOS</button>
        </div>
    </section>

    <!-- Anomaly Cards List -->
    <main class="cards-list" id="cardsContainer"></main>
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
            let matchDomain = false;
            if (currentDomain === 'all') {{
                matchDomain = true;
            }} else if (currentDomain === 'novel') {{
                matchDomain = c.category === 'novel_discovery';
            }} else {{
                matchDomain = c.source === currentDomain;
            }}

            const matchQuery = !q || 
                               c.title.toLowerCase().includes(q) || 
                               c.id.toLowerCase().includes(q) || 
                               c.why.toLowerCase().includes(q) || 
                               c.lookup.toLowerCase().includes(q) ||
                               c.fix.toLowerCase().includes(q) ||
                               c.start_raw.toLowerCase().includes(q) ||
                               c.recovery_raw.toLowerCase().includes(q);
            return matchDomain && matchQuery;
        }});

        if (filtered.length === 0) {{
            container.innerHTML = '<div class="empty-state">No matching telemetry anomalies found for the current query/filter.</div>';
            return;
        }}

        filtered.forEach(item => {{
            const card = document.createElement('article');
            card.className = 'card';

            let logTraceHtml = '';
            if (item.start_raw) {{
                const label = item.category === 'novel_discovery' ? '🔍 NOVEL FAULT TRACE' : '🔴 FAULT TRIGGER';
                logTraceHtml += `<div class="code-header tag-start"><span>${{label}}</span> (Line ${{item.start_line}}):</div><div class="code-line">${{item.start_raw}}</div>`;
            }}
            if (item.recovery_raw && item.recovery_raw !== item.start_raw) {{
                const label = item.category === 'novel_discovery' ? '🔍 SUBSEQUENT TRACE' : '🟢 STATE RECOVERED';
                logTraceHtml += `<div class="code-header tag-end" style="margin-top:10px;"><span>${{label}}</span> (Line ${{item.end_line}}):</div><div class="code-line">${{item.recovery_raw}}</div>`;
            }}

            let cascadeHtml = '';
            if (item.is_cascade && item.cascade_insight) {{
                cascadeHtml = `
                <div class="cascade-banner">
                    <svg viewBox="0 0 24 24" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                    <div><strong>Cross-Domain Temporal Cascade:</strong> ${{item.cascade_insight}}</div>
                </div>`;
            }}

            const isNovel = item.category === 'novel_discovery';
            const sourceBadge = isNovel ? '<span class="badge badge-novel">ZERO-SHOT DISCOVERED</span>' : `<span class="badge badge-source">${{item.source}}</span>`;

            card.innerHTML = `
                <div class="card-header">
                    <div class="card-title-group">
                        <div class="card-title">${{item.title}}</div>
                    </div>
                    <div class="badges-wrapper">
                        ${{sourceBadge}}
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
                <div class="analysis-box ${{isNovel ? 'novel-box' : ''}}">
                    <div class="analysis-row">
                        <span class="label">❓ Diagnostic Root Cause Analysis:</span>
                        <span class="text">${{item.why}}</span>
                    </div>
                    <div class="analysis-row">
                        <span class="label">🔍 What Testers Should Inspect:</span>
                        <span class="text">${{item.lookup}}</span>
                    </div>
                    <div class="analysis-row">
                        <span class="label">🛠️ Step-by-Step QA Action Item:</span>
                        <span class="text">${{item.fix}}</span>
                    </div>
                </div>
                ${{logTraceHtml ? `<div class="code-box">${{logTraceHtml}}</div>` : ''}}
            `;
            container.appendChild(card);
        }});
    }}

    domainBtns.addEventListener('click', (e) => {{
        if (e.target.classList.contains('tab-btn')) {{
            document.querySelectorAll('#domainBtns .tab-btn').forEach(b => b.classList.remove('active'));
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
