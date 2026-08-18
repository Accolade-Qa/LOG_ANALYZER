from datetime import datetime
import re
from reports.anomaly_collector import collect

TIMESTAMP_PATTERN = re.compile(r"\[(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]")


def _extract_timestamp_seconds(raw_line):
    if not raw_line:
        return None
    match = TIMESTAMP_PATTERN.search(raw_line)
    if not match:
        return None
    ts_str = match.group("ts")
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return dt.timestamp()


class BaseAgent:
    """Base class for telemetry subsystem agents with stateful session management."""

    def __init__(self):
        self.anomalies = []
        self.active_sessions = {}

    def add_anomaly(self, issue):
        """Record an anomaly detected by this agent."""
        self.anomalies.append(issue)

    def open_session(
        self,
        session_key,
        issue,
        source=None,
        category=None,
        severity="medium",
        event=None,
    ):
        """Open an active anomaly session if not already open."""
        raw_line = event.get("raw") if event else None
        line_num = event.get("line_number") if event else None

        if session_key in self.active_sessions:
            self.update_session(session_key, event=event)
            return self.active_sessions[session_key]

        session = {
            "key": session_key,
            "issue": issue,
            "source": source,
            "category": category,
            "severity": severity,
            "start_line": line_num,
            "end_line": line_num,
            "occurrence_count": 1,
            "status": "ACTIVE",
            "start_raw_line": raw_line,
            "end_raw_line": raw_line,
            "start_ts": _extract_timestamp_seconds(raw_line),
            "end_ts": _extract_timestamp_seconds(raw_line),
            "event": event,
        }
        self.active_sessions[session_key] = session
        self.add_anomaly(issue)
        return session

    def update_session(self, session_key, event=None):
        """Update an existing active anomaly session."""
        if session_key not in self.active_sessions:
            return None

        session = self.active_sessions[session_key]
        raw_line = event.get("raw") if event else None
        line_num = event.get("line_number") if event else None

        session["occurrence_count"] += 1
        if line_num is not None:
            session["end_line"] = line_num
        if raw_line:
            session["end_raw_line"] = raw_line
            ts = _extract_timestamp_seconds(raw_line)
            if ts is not None:
                session["end_ts"] = ts

        return session

    def close_session(
        self, session_key, recovery_event=None, recovery_message=None
    ):
        """Close an active anomaly session when recovery telemetry is detected."""
        if session_key not in self.active_sessions:
            return None

        session = self.active_sessions.pop(session_key)
        session["status"] = "RESOLVED"

        raw_line = recovery_event.get("raw") if recovery_event else None
        line_num = recovery_event.get("line_number") if recovery_event else None

        if line_num is not None:
            session["end_line"] = line_num
        if raw_line:
            session["end_raw_line"] = raw_line
            ts = _extract_timestamp_seconds(raw_line)
            if ts is not None:
                session["end_ts"] = ts

        duration_sec = 0.0
        if session.get("start_ts") and session.get("end_ts"):
            duration_sec = max(0.0, session["end_ts"] - session["start_ts"])
        session["duration_seconds"] = round(duration_sec, 3)

        metadata = {
            "start_line": session.get("start_line"),
            "end_line": session.get("end_line"),
            "duration_seconds": session.get("duration_seconds"),
            "occurrence_count": session.get("occurrence_count"),
            "status": "RESOLVED",
            "recovery_line": raw_line,
            "recovery_message": recovery_message,
        }

        collect(
            issue=session["issue"],
            source=session["source"],
            category=session["category"],
            severity=session["severity"],
            event=session.get("event"),
            metadata=metadata,
        )
        return session

    def finalize_open_sessions(self, last_event=None):
        """Finalize any remaining open sessions at end-of-log as UNRESOLVED/ACTIVE."""
        for session_key in list(self.active_sessions.keys()):
            session = self.active_sessions.pop(session_key)
            session["status"] = "UNRESOLVED"

            if last_event:
                line_num = last_event.get("line_number")
                raw_line = last_event.get("raw")
                if line_num is not None:
                    session["end_line"] = line_num
                if raw_line:
                    session["end_raw_line"] = raw_line
                    ts = _extract_timestamp_seconds(raw_line)
                    if ts is not None:
                        session["end_ts"] = ts

            duration_sec = 0.0
            if session.get("start_ts") and session.get("end_ts"):
                duration_sec = max(0.0, session["end_ts"] - session["start_ts"])
            session["duration_seconds"] = round(duration_sec, 3)

            metadata = {
                "start_line": session.get("start_line"),
                "end_line": session.get("end_line"),
                "duration_seconds": session.get("duration_seconds"),
                "occurrence_count": session.get("occurrence_count"),
                "status": "UNRESOLVED",
            }

            collect(
                issue=session["issue"],
                source=session["source"],
                category=session["category"],
                severity=session["severity"],
                event=session.get("event"),
                metadata=metadata,
            )
