"""
Safety Audit Logger — append-only JSONL log for safety escalation events.

Every time the safety_escalation_agent returns a tier other than NONE,
one line is written to:
    data/patients/<patient_id>/logs/safety_audit.jsonl

Each line contains:
    - timestamp (ISO-8601 UTC)
    - patient_id
    - tier
    - rules_fired
    - redacted_input: symptom names and severities only (no free-text notes)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


# ─── Path helpers ─────────────────────────────────────────────────────────────

def _audit_log_path(patient_id: str) -> Path:
    """Return the path to the patient's safety audit JSONL file."""
    # Resolve relative to the repo root (two levels up from src/anemia_diet_system/tools/)
    repo_root = Path(__file__).resolve().parents[3]
    log_dir = repo_root / "data" / "patients" / patient_id / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "safety_audit.jsonl"


# ─── Redaction helper ─────────────────────────────────────────────────────────

def _redact_symptoms(tagged_symptoms: list[dict]) -> list[dict]:
    """
    Return only name + severity for each tagged symptom.
    Strips raw_text, clinical notes, and any other free-text fields.
    """
    redacted = []
    for sym in (tagged_symptoms or []):
        redacted.append({
            "name": sym.get("name", "unknown"),
            "severity": sym.get("severity", "unknown"),
        })
    return redacted


# ─── Core write function ──────────────────────────────────────────────────────

def log_safety_event(
    patient_id: str,
    tier: str,
    rules_fired: list[str],
    tagged_symptoms: list[dict],
) -> Path | None:
    """
    Append one JSONL line to the patient's safety audit log.
    Only writes if tier != "NONE".

    Returns the path written to, or None if skipped.
    """
    if tier.upper() == "NONE":
        return None

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patient_id": patient_id,
        "tier": tier.upper(),
        "rules_fired": rules_fired,
        "redacted_input": _redact_symptoms(tagged_symptoms),
    }

    log_path = _audit_log_path(patient_id)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    return log_path


# ─── Read helpers ─────────────────────────────────────────────────────────────

def read_recent_events(patient_id: str, n: int = 20) -> list[dict]:
    """
    Return the last *n* audit events for a patient, newest first.
    Returns an empty list if no log file exists yet.
    """
    log_path = _audit_log_path(patient_id)
    if not log_path.exists():
        return []

    lines = log_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    return list(reversed(events[-n:]))


def had_monitor_flag_last_window(patient_id: str, window_days: int = 7) -> bool:
    """
    Return True if any MONITOR-tier event was logged in the prior *window_days* days.
    Used by the safety crew to enforce the escalation-persistence rule.
    """
    log_path = _audit_log_path(patient_id)
    if not log_path.exists():
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    lines = log_path.read_text(encoding="utf-8").splitlines()

    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("tier", "").upper() != "MONITOR":
            continue
        try:
            ts = datetime.fromisoformat(record["timestamp"])
            if ts >= cutoff:
                return True
        except (KeyError, ValueError):
            continue

    return False
