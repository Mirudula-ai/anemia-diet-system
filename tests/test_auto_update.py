"""
tests/test_auto_update.py

Integration tests for the Daily Auto-Update Engine check-updates endpoint.
Uses FastAPI's TestClient against main.app with lightweight mocked crew pipeline.

Test Cases:
  TC-AUTO01: Patient with pregnancy_status="pregnant" -> updated=false, reason="not_applicable"
  TC-AUTO02: Patient with no cycle_start_date set -> updated=false, reason="not_applicable"
  TC-AUTO03: Patient with cycle_start_date set, first check (no prior phase recorded) -> updated=false, reason="no_change"
  TC-AUTO04: Stale phase setup -> updated=true, new_phase != previous_phase, get_last_known_cycle_phase updated
  TC-AUTO05: Stale phase setup with safety_tier="EMERGENCY" -> updated=false, reason="safety_override_active"
  TC-AUTO06: Calling check-updates twice in a row -> second call returns updated=false, reason="no_change"
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

# Ensure src/ is in sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from fastapi.testclient import TestClient
from anemia_diet_system.main import app
from anemia_diet_system import storage, cycle_calculator

client = TestClient(app)


def helper_setup_patient(patient_id: str, extra_profile: dict | None = None) -> None:
    """Helper to seed a patient via POST /intake with mock _run_flow."""
    payload = {
        "patient_id": patient_id,
        "diet_type": "vegetarian",
        "pregnancy_status": "not_pregnant",
        "existing_conditions": ["Anemia"],
        "allergies": ["dairy"],
        "current_medications": [],
        "symptom_log": [],
        "biomarkers": {"ferritin": 12},
    }
    with patch("anemia_diet_system.main._run_flow", return_value={"content_mode": "full_plan", "safety_tier": "NONE"}):
        resp = client.post("/intake", json=payload)
        assert resp.status_code == 200, f"Intake setup failed for {patient_id}: {resp.text}"

    if extra_profile:
        storage.update_patient_profile(patient_id, extra_profile)


def test_tc_auto01() -> None:
    """TC-AUTO01: Pregnant patient -> returns updated=false, reason='not_applicable'."""
    pid = "auto_test_01"
    helper_setup_patient(pid, {"pregnancy_status": "pregnant", "cycle_start_date": "2026-08-01"})
    resp = client.get(f"/patient/{pid}/check-updates")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("updated") is False
    assert data.get("reason") == "not_applicable"


def test_tc_auto02() -> None:
    """TC-AUTO02: Patient with no cycle_start_date set -> returns updated=false, reason='not_applicable'."""
    pid = "auto_test_02"
    helper_setup_patient(pid, {"pregnancy_status": "not_pregnant"})
    # Ensure cycle_start_date is absent
    prof = storage.load_patient_profile(pid)
    prof.pop("cycle_start_date", None)
    storage.save_patient_profile(pid, prof)

    resp = client.get(f"/patient/{pid}/check-updates")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("updated") is False
    assert data.get("reason") == "not_applicable"


def test_tc_auto03() -> None:
    """TC-AUTO03: First check (no prior phase recorded) -> returns updated=false, reason='no_change'."""
    pid = "auto_test_03"
    helper_setup_patient(pid, {"cycle_start_date": "2026-08-01", "average_cycle_length": 28})
    # Remove _generated_at_cycle_phase from current_plan if present
    plan = storage.load_current_plan(pid)
    if plan and isinstance(plan, dict):
        plan.pop("_generated_at_cycle_phase", None)
        storage.save_current_plan(pid, plan)

    assert storage.get_last_known_cycle_phase(pid) is None

    resp = client.get(f"/patient/{pid}/check-updates")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("updated") is False
    assert data.get("reason") == "no_change"
    assert "current_phase" in data


def test_tc_auto04() -> None:
    """TC-AUTO04: Stale phase setup -> returns updated=true, new_phase != previous_phase."""
    pid = "auto_test_04"
    helper_setup_patient(pid, {"cycle_start_date": "2026-08-01", "average_cycle_length": 28})

    current_info = cycle_calculator.calculate_cycle_info("2026-08-01", 28)
    curr_phase = current_info["cycle_phase"]

    # Pick a stale phase different from curr_phase
    phases = ["menstruation", "follicular", "ovulation", "luteal"]
    stale_phase = [p for p in phases if p != curr_phase][0]

    plan = storage.load_current_plan(pid) or {}
    storage.save_current_plan(pid, plan, cycle_phase=stale_phase)
    assert storage.get_last_known_cycle_phase(pid) == stale_phase

    with patch("anemia_diet_system.main._run_flow", return_value={"content_mode": "full_plan", "timed_foods": {"morning": ["iron_smoothie"]}}):
        resp = client.get(f"/patient/{pid}/check-updates")

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("updated") is True
    assert data.get("previous_phase") == stale_phase
    assert data.get("new_phase") == curr_phase
    assert "plan" in data
    assert storage.get_last_known_cycle_phase(pid) == curr_phase


def test_tc_auto05() -> None:
    """TC-AUTO05: Stale phase with EMERGENCY safety_tier -> returns updated=false, reason='safety_override_active'."""
    pid = "auto_test_05"
    helper_setup_patient(pid, {"cycle_start_date": "2026-08-01", "average_cycle_length": 28})

    current_info = cycle_calculator.calculate_cycle_info("2026-08-01", 28)
    curr_phase = current_info["cycle_phase"]
    stale_phase = "menstruation" if curr_phase != "menstruation" else "luteal"

    plan = storage.load_current_plan(pid) or {}
    plan["safety_tier"] = "EMERGENCY"
    plan["safety_note"] = "Patient exhibits severe symptoms."
    storage.save_current_plan(pid, plan, cycle_phase=stale_phase)

    resp = client.get(f"/patient/{pid}/check-updates")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("updated") is False
    assert data.get("reason") == "safety_override_active"


def test_tc_auto06() -> None:
    """TC-AUTO06: Calling check-updates twice in a row -> second call returns updated=false, reason='no_change'."""
    pid = "auto_test_06"
    helper_setup_patient(pid, {"cycle_start_date": "2026-08-01", "average_cycle_length": 28})

    current_info = cycle_calculator.calculate_cycle_info("2026-08-01", 28)
    curr_phase = current_info["cycle_phase"]
    stale_phase = "menstruation" if curr_phase != "menstruation" else "luteal"

    plan = storage.load_current_plan(pid) or {}
    storage.save_current_plan(pid, plan, cycle_phase=stale_phase)

    # First call
    with patch("anemia_diet_system.main._run_flow", return_value={"content_mode": "full_plan"}):
        resp1 = client.get(f"/patient/{pid}/check-updates")
    assert resp1.status_code == 200

    # Immediate second call
    resp2 = client.get(f"/patient/{pid}/check-updates")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2.get("updated") is False
    assert data2.get("reason") == "no_change"


TEST_CASES = [
    ("TC-AUTO01", "Pregnant patient -> updated=false, reason='not_applicable'", test_tc_auto01),
    ("TC-AUTO02", "Patient with no cycle_start_date -> updated=false, reason='not_applicable'", test_tc_auto02),
    ("TC-AUTO03", "First check (no prior phase recorded) -> updated=false, reason='no_change'", test_tc_auto03),
    ("TC-AUTO04", "Stale phase setup -> updated=true, new_phase != previous_phase, storage updated", test_tc_auto04),
    ("TC-AUTO05", "Stale phase with EMERGENCY safety_tier -> updated=false, reason='safety_override_active'", test_tc_auto05),
    ("TC-AUTO06", "Calling check-updates twice in a row -> second call returns updated=false, reason='no_change'", test_tc_auto06),
]


def run_auto_update_tests() -> None:
    results = []
    print("\n" + "=" * 90)
    print("  DAILY AUTO-UPDATE ENGINE — INTEGRATION TEST SUITE")
    print("=" * 90)

    for tc_id, desc, func in TEST_CASES:
        try:
            func()
            status = "PASS"
            label = "✅ PASS"
            detail = "OK"
        except AssertionError as exc:
            status = "FAIL"
            label = "❌ FAIL"
            detail = f"AssertionError: {exc}"
        except Exception as exc:
            status = "FAIL"
            label = "❌ FAIL"
            detail = f"Exception: {exc}"

        results.append({
            "id": tc_id,
            "description": desc,
            "status": status,
            "label": label,
            "detail": detail,
        })
        print(f"  {tc_id:<10} {label:<10} {desc}")

    print("\n" + "=" * 90)
    print("  DAILY AUTO-UPDATE ENGINE — TEST RESULTS SUMMARY")
    print("=" * 90)
    print(f"  {'ID':<10} {'Status':<12} Description")
    print("  " + "-" * 86)
    passed_cnt = 0
    for r in results:
        print(f"  {r['id']:<10} {r['label']:<12} {r['description']}")
        if r["status"] == "PASS":
            passed_cnt += 1
    print("  " + "-" * 86)
    for r in results:
        if r["status"] != "PASS":
            print(f"\n  [{r['id']}] Failure Detail:\n    {r['detail']}")
    print("  " + "-" * 86)
    print(f"  TOTAL: {passed_cnt}/{len(results)} passed\n")

    # Clean up test directories
    for i in range(1, 7):
        pid = f"auto_test_0{i}"
        shutil.rmtree(project_root / "data" / "patients" / pid, ignore_errors=True)


if __name__ == "__main__":
    run_auto_update_tests()
