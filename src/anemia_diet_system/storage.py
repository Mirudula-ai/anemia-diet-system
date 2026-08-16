"""
storage.py — JSON-file-based persistence layer for the Anemia Diet System.

Layout under data/patients/<patient_id>/:
  profile.json         — immutable intake profile
  current_plan.json    — latest synthesis output (overwritten on each update)
  symptom_log.json     — list of recent symptom entries (current window)
  symptom_log_history.json — flattened prior-week symptom list for SafetyCrew
  feedback_log.json    — list of raw feedback entries

All functions are synchronous and thread-safe via a per-file lock.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Root data directory — relative to the project root, not this file's location.
# Override via DATA_DIR env var if needed.
# ---------------------------------------------------------------------------
_DATA_ROOT = Path(os.getenv("DATA_DIR", "data")) / "patients"

# One lock per patient directory to avoid concurrent write corruption.
_locks: Dict[str, threading.Lock] = {}
_lock_registry = threading.Lock()


def _patient_dir(patient_id: str) -> Path:
    return _DATA_ROOT / patient_id


def _lock_for(patient_id: str) -> threading.Lock:
    with _lock_registry:
        if patient_id not in _locks:
            _locks[patient_id] = threading.Lock()
        return _locks[patient_id]


def _read_json(path: Path) -> Optional[Any]:
    """Return parsed JSON from *path*, or None if missing or corrupt."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_json(path: Path, data: Any) -> None:
    """Atomically write *data* as JSON to *path*, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_patient_profile(patient_id: str, profile_dict: Dict[str, Any]) -> None:
    """Persist the intake profile (typically written once at /intake time)."""
    with _lock_for(patient_id):
        _write_json(_patient_dir(patient_id) / "profile.json", profile_dict)


def load_patient_profile(patient_id: str) -> Optional[Dict[str, Any]]:
    """Return the stored profile dict, or None if /intake has never been called."""
    return _read_json(_patient_dir(patient_id) / "profile.json")


def update_patient_profile(patient_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge *updates* into existing patient profile and persist it.
    Only overwrites fields present in updates, preserving everything else.
    Raises ValueError if no existing profile is found.
    """
    existing = load_patient_profile(patient_id)
    if existing is None:
        raise ValueError(
            f"Patient profile for '{patient_id}' not found. Cannot update a non-existent profile."
        )

    updated = dict(existing)
    for key, val in updates.items():
        updated[key] = val

    save_patient_profile(patient_id, updated)
    return updated




def save_current_plan(patient_id: str, plan_dict: Dict[str, Any]) -> None:
    """Overwrite current_plan.json with the latest synthesis result."""
    with _lock_for(patient_id):
        _write_json(_patient_dir(patient_id) / "current_plan.json", plan_dict)


def load_current_plan(patient_id: str) -> Optional[Dict[str, Any]]:
    """Return the most-recently saved plan, or None if none exists."""
    return _read_json(_patient_dir(patient_id) / "current_plan.json")


def append_symptom_log(patient_id: str, symptom_entry: Any) -> None:
    """
    Append *symptom_entry* (str or dict) to the rolling symptom log.

    When the current log exceeds 7 entries (roughly one week of daily checks),
    the oldest entries are rotated into symptom_log_history.json so the
    SafetyCrew can compute prior_monitor_flags_last_window correctly.
    """
    WINDOW_SIZE = 7
    with _lock_for(patient_id):
        d = _patient_dir(patient_id)

        # ── current log ────────────────────────────────────────────────────
        current: List[Any] = _read_json(d / "symptom_log.json") or []
        if isinstance(current, str):
            current = [current]
        current.append(symptom_entry)

        # ── rotate overflow into history ────────────────────────────────────
        if len(current) > WINDOW_SIZE:
            overflow = current[:-WINDOW_SIZE]
            current = current[-WINDOW_SIZE:]
            history: List[Any] = _read_json(d / "symptom_log_history.json") or []
            history.extend(overflow)
            _write_json(d / "symptom_log_history.json", history)

        _write_json(d / "symptom_log.json", current)


def load_symptom_logs(patient_id: str) -> Dict[str, List[Any]]:
    """Return both current and history symptom lists."""
    d = _patient_dir(patient_id)
    return {
        "symptom_log": _read_json(d / "symptom_log.json") or [],
        "symptom_log_history": _read_json(d / "symptom_log_history.json") or [],
    }


def append_feedback_log(patient_id: str, feedback_entry: Any) -> None:
    """Append one raw feedback entry to feedback_log.json."""
    with _lock_for(patient_id):
        d = _patient_dir(patient_id)
        log: List[Any] = _read_json(d / "feedback_log.json") or []
        log.append(feedback_entry)
        _write_json(d / "feedback_log.json", log)


def load_feedback_log(patient_id: str) -> List[Any]:
    """Return the full feedback log list."""
    return _read_json(_patient_dir(patient_id) / "feedback_log.json") or []


def get_last_known_safety_tier(patient_id: str) -> str:
    """
    Read the safety_tier from the most-recently saved plan.
    Defaults to 'NONE' if no plan exists yet.
    """
    plan = load_current_plan(patient_id)
    if plan and isinstance(plan, dict):
        tier = plan.get("safety_tier") or plan.get("tier") or "NONE"
        return str(tier).upper()
    return "NONE"


def get_last_known_safety_message(patient_id: str) -> str:
    """Read the safety_message/safety_note from the most-recently
    saved plan. Defaults to empty string if none exists."""
    plan = load_current_plan(patient_id)
    if plan and isinstance(plan, dict):
        return plan.get("safety_note") or plan.get("safety_message") or ""
    return ""
