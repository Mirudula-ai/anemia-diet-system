"""
tests/test_profile_editing.py

Integration tests for patient profile management GET and PUT endpoints.
Uses FastAPI's TestClient against main.app.

Test Cases:
  TC-PROF01: GET /patient/profile_test_01/profile -> check 200, returned profile matches intake data
  TC-PROF02: PUT /patient/profile_test_01/profile (allergies update) -> check 200, partial merge
  TC-PROF03: PUT (plan-affecting field: allergies) -> check plan_may_need_update is True
  TC-PROF04: PUT (non-plan-affecting field: cycle_start_date) -> check plan_may_need_update is False
  TC-PROF05: PUT (pregnancy_status="not_pregnant", trimester=null) -> check trimester is cleared to null
  TC-PROF06: GET /patient/nonexistent_profile_test/profile -> check 404
  TC-PROF07: PUT /patient/nonexistent_profile_test/profile -> check 404 (not 500)
"""
from __future__ import annotations

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

client = TestClient(app)


def setup_patient() -> None:
    """Setup patient_id='profile_test_01' via POST /intake with mock _run_flow."""
    payload = {
        "patient_id": "profile_test_01",
        "diet_type": "vegetarian",
        "pregnancy_status": "pregnant",
        "trimester": "2nd",
        "existing_conditions": ["Anemia"],
        "allergies": ["dairy"],
        "current_medications": ["iron_supplement"],
        "symptom_log": ["mild fatigue"],
        "biomarkers": {"ferritin": 12},
    }
    with patch("anemia_diet_system.main._run_flow", return_value={"content_mode": "full_plan"}):
        resp = client.post("/intake", json=payload)
        assert resp.status_code == 200, f"Intake setup failed: {resp.text}"


def test_tc_prof01() -> None:
    """TC-PROF01: GET /patient/profile_test_01/profile -> check 200, returned profile matches intake."""
    setup_patient()
    resp = client.get("/patient/profile_test_01/profile")
    assert resp.status_code == 200
    data = resp.json().get("result", {})
    assert data.get("patient_id") == "profile_test_01"
    assert data.get("diet_type") == "vegetarian"
    assert data.get("pregnancy_status") == "pregnant"
    assert data.get("trimester") == "2nd"
    assert data.get("allergies") == ["dairy"]
    assert data.get("existing_conditions") == ["Anemia"]


def test_tc_prof02() -> None:
    """TC-PROF02: PUT allergies -> check 200, updated allergies, diet_type unchanged."""
    setup_patient()
    payload = {"allergies": ["shellfish", "peanuts"]}
    resp = client.put("/patient/profile_test_01/profile", json=payload)
    assert resp.status_code == 200
    data = resp.json().get("result", {})
    assert data.get("allergies") == ["shellfish", "peanuts"]
    assert data.get("diet_type") == "vegetarian"
    assert data.get("pregnancy_status") == "pregnant"


def test_tc_prof03() -> None:
    """TC-PROF03: PUT allergies -> check plan_may_need_update is True."""
    setup_patient()
    payload = {"allergies": ["shellfish", "peanuts"]}
    resp = client.put("/patient/profile_test_01/profile", json=payload)
    assert resp.status_code == 200
    data = resp.json().get("result", {})
    assert data.get("plan_may_need_update") is True


def test_tc_prof04() -> None:
    """TC-PROF04: PUT cycle_start_date -> check plan_may_need_update is False."""
    setup_patient()
    payload = {"cycle_start_date": "2026-08-01"}
    resp = client.put("/patient/profile_test_01/profile", json=payload)
    assert resp.status_code == 200
    data = resp.json().get("result", {})
    assert data.get("plan_may_need_update") is False


def test_tc_prof05() -> None:
    """TC-PROF05: PUT pregnancy_status='not_pregnant', trimester=null -> check trimester is null/None."""
    setup_patient()
    payload = {"pregnancy_status": "not_pregnant", "trimester": None}
    resp = client.put("/patient/profile_test_01/profile", json=payload)
    assert resp.status_code == 200
    data = resp.json().get("result", {})
    assert data.get("pregnancy_status") == "not_pregnant"
    assert data.get("trimester") is None


def test_tc_prof06() -> None:
    """TC-PROF06: GET /patient/nonexistent_profile_test/profile -> check 404."""
    resp = client.get("/patient/nonexistent_profile_test/profile")
    assert resp.status_code == 404


def test_tc_prof07() -> None:
    """TC-PROF07: PUT /patient/nonexistent_profile_test/profile -> check 404 (not 500)."""
    payload = {"diet_type": "vegan"}
    resp = client.put("/patient/nonexistent_profile_test/profile", json=payload)
    assert resp.status_code == 404


TEST_CASES = [
    ("TC-PROF01", "GET /patient/profile_test_01/profile -> check 200 and matching intake profile", test_tc_prof01),
    ("TC-PROF02", "PUT allergies -> check 200, partial merge (diet_type unchanged)", test_tc_prof02),
    ("TC-PROF03", "PUT allergies (plan-affecting) -> check plan_may_need_update is True", test_tc_prof03),
    ("TC-PROF04", "PUT cycle_start_date (non-plan-affecting) -> check plan_may_need_update is False", test_tc_prof04),
    ("TC-PROF05", "PUT pregnancy_status='not_pregnant', trimester=null -> check trimester cleared to null", test_tc_prof05),
    ("TC-PROF06", "GET /patient/nonexistent_profile_test/profile -> check 404 status", test_tc_prof06),
    ("TC-PROF07", "PUT /patient/nonexistent_profile_test/profile -> check 404 status (not 500/crash)", test_tc_prof07),
]


def run_profile_tests() -> None:
    results = []
    print("\n" + "=" * 80)
    print("  PATIENT PROFILE EDITING — INTEGRATION TEST SUITE")
    print("=" * 80)

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
    print("  PATIENT PROFILE EDITING — TEST RESULTS SUMMARY")
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

    import shutil
    shutil.rmtree(project_root / "data" / "patients" / "profile_test_01", ignore_errors=True)
    shutil.rmtree(project_root / "data" / "patients" / "nonexistent_profile_test", ignore_errors=True)


if __name__ == "__main__":
    run_profile_tests()

