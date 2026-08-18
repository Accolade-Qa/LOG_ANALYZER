from pathlib import Path
import yaml  # type: ignore

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "paths": {
        "log_dir": "logs",
        "artifact_dir": "artifacts",
        "default_log_file": "logs/REL18_TO_REL24.log",
        "raw_anomalies_json": "artifacts/raw_anomalies.json",
        "report_cards_md": "artifacts/report_cards.md",
        "final_report_md": "artifacts/final_report.md",
        "ai_summary_md": "artifacts/ai_summary.md",
        "report_dashboard_html": "artifacts/report_dashboard.html",
    },

    "uart": {
        "default_port": "COM3",
        "default_baudrate": 115200,
        "timeout": 1.0,
    },
    "live_tail": {
        "poll_interval": 0.1,
        "stop_on_idle_sec": 5.0,
    },
    "ai": {
        "model": "gemini-3.6-flash",
        "api_url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent",
    },

    "severity_order": {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    },
    "parsing": {
        "chunk_size": 50000,
        "buffer_flush_size": 1000,
    },
}


def load_config():
    """Load config.yaml if present, otherwise return DEFAULT_CONFIG."""
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
            # Merge user config with defaults
            merged = DEFAULT_CONFIG.copy()
            for key, val in user_cfg.items():
                if isinstance(val, dict) and key in merged:
                    merged[key] = {**merged[key], **val}
                else:
                    merged[key] = val
            return merged
    except Exception as e:
        print(f"Warning: Failed to parse config.yaml ({e}). Using default configuration.")
        return DEFAULT_CONFIG


config = load_config()
