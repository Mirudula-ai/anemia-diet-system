"""
Test suite for the Safety Crew — 15 golden test cases.

Run as a script:
    python tests/test_safety_crew.py

Or via pytest:
    pytest tests/test_safety_crew.py -v

Each test calls SafetyCrew().crew().kickoff() with the test-case inputs and
compares the actual tier against the expected tier.
A pass/fail table is printed at the end.
"""
from __future__ import annotations

import json
import sys
import time
import os
from pathlib import Path
from typing import Any

os.environ["DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DROP_PARAMS"] = "True"

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import litellm
litellm.drop_params = True

def _remove_cache_control(kwargs):
    def clean_obj(obj):
        if isinstance(obj, dict):
            obj.pop("cache_control", None)
            obj.pop("cache_breakpoint", None)
            for k, v in list(obj.items()):
                clean_obj(v)
        elif isinstance(obj, list):
            for item in obj:
                clean_obj(item)

    clean_obj(kwargs)

litellm.input_callback = [_remove_cache_control]

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Ensure the src directory is on the Python path ───────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anemia_diet_system.crews.safety_crew.safety_crew import SafetyCrew
from anemia_diet_system.tools.safety_audit_logger import (
    read_recent_events,
    _audit_log_path,
)

# ── Golden test cases ─────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "id": "TC01",
        "description": "Heavy bleeding hourly -> EMERGENCY",
        "input": {
            "logged_symptoms": ["soaking through protection every hour"],
            "life_stage": "menstruating",
        },
        "expected_tier": "EMERGENCY",
    },
    {
        "id": "TC02",
        "description": "Fainting reported -> EMERGENCY",
        "input": {
            "logged_symptoms": ["fainted this morning"],
            "life_stage": "menstruating",
        },
        "expected_tier": "EMERGENCY",
    },
    {
        "id": "TC03",
        "description": "Chest pain -> EMERGENCY",
        "input": {
            "logged_symptoms": ["chest pain since last night"],
            "life_stage": "pregnant",
        },
        "expected_tier": "EMERGENCY",
    },
    {
        "id": "TC04",
        "description": "Shortness of breath at rest -> EMERGENCY",
        "input": {
            "logged_symptoms": ["out of breath just sitting down"],
            "life_stage": "menopausal",
        },
        "expected_tier": "EMERGENCY",
    },
    {
        "id": "TC05",
        "description": "Black tarry stools -> EMERGENCY",
        "input": {
            "logged_symptoms": ["dark, tarry stools for two days"],
            "life_stage": "menstruating",
        },
        "expected_tier": "EMERGENCY",
    },
    {
        "id": "TC06",
        "description": "Postmenopausal + fatigue -> URGENT",
        "input": {
            "logged_symptoms": ["fatigue", "pale skin"],
            "life_stage": "menopausal",
        },
        "expected_tier": "URGENT",
    },
    {
        "id": "TC07",
        "description": "Pregnant + severe dizziness -> URGENT",
        "input": {
            "logged_symptoms": ["severe dizziness when standing"],
            "life_stage": "pregnant",
            "is_pregnant": True,
        },
        "expected_tier": "URGENT",
    },
    {
        "id": "TC08",
        "description": "Palpitations + dizziness -> URGENT",
        "input": {
            "logged_symptoms": ["racing heart", "dizzy spells"],
            "life_stage": "menstruating",
        },
        "expected_tier": "URGENT",
    },
    {
        "id": "TC09",
        "description": "Rapid weight loss -> URGENT",
        "input": {
            "logged_symptoms": ["lost about 5kg this month without trying"],
            "life_stage": "PCOS",
        },
        "expected_tier": "URGENT",
    },
    {
        "id": "TC10",
        "description": "3+ moderate symptoms in 7 days -> URGENT",
        "input": {
            "tagged_symptoms": [
                {"name": "fatigue", "severity": "moderate"},
                {"name": "brain fog", "severity": "moderate"},
                {"name": "brittle nails", "severity": "moderate"},
            ],
            "life_stage": "thyroid-flagged",
        },
        "expected_tier": "URGENT",
    },
    {
        "id": "TC11",
        "description": "Family history of thalassemia + low MCV -> MONITOR",
        "input": {
            "family_history_flags": ["thalassemia"],
            "biomarkers": {"MCV": {"value": 68, "flag": "low"}},
            "life_stage": "menstruating",
        },
        "expected_tier": "MONITOR",
    },
    {
        "id": "TC12",
        "description": "Single mild symptom -> NONE",
        "input": {
            "logged_symptoms": ["slightly tired today"],
            "life_stage": "menstruating",
        },
        "expected_tier": "NONE",
    },
    {
        "id": "TC13",
        "description": "MONITOR recurring second week -> escalate to URGENT",
        "input": {
            "tagged_symptoms": [{"name": "fatigue", "severity": "moderate"}],
            "prior_monitor_flags_last_window": True,
            "prior_monitor_symptom_name": "fatigue",
            "life_stage": "menstruating",
        },
        "expected_tier": "URGENT",
    },
    {
        "id": "TC14",
        "description": "No symptoms logged -> NONE",
        "input": {
            "logged_symptoms": [],
            "life_stage": "menstruating",
        },
        "expected_tier": "NONE",
    },
    {
        "id": "TC15",
        "description": "Overlapping triggers -> highest tier wins",
        "input": {
            "logged_symptoms": ["fainted", "ongoing fatigue"],
            "life_stage": "menopausal",
        },
        "expected_tier": "EMERGENCY",
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_tier(raw: str) -> str:
    """Extract the tier string from raw LLM output (may be JSON or plain text)."""
    raw = raw.strip()
    # Strip markdown fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
    try:
        data = json.loads(raw)
        return data.get("tier", "UNKNOWN").upper()
    except json.JSONDecodeError:
        # Fallback: look for tier keyword in plain text
        for tier in ("EMERGENCY", "URGENT", "MONITOR", "NONE"):
            if tier in raw.upper():
                return tier
        return "UNKNOWN"


def _build_crew_inputs(tc_input: dict[str, Any], patient_id: str) -> dict[str, str]:
    """Wrap test case input as the patient_input JSON string."""
    payload = dict(tc_input)
    payload["patient_id"] = patient_id
    return {"patient_input": json.dumps(payload, default=str)}


# ── Main test runner ──────────────────────────────────────────────────────────

def run_tests() -> None:
    results = []

    for tc in TEST_CASES:
        tc_id = tc["id"]
        description = tc["description"]
        expected = tc["expected_tier"]
        patient_id = f"test_{tc_id.lower()}"

        print(f"\n{'='*60}", flush=True)
        print(f"Running {tc_id}: {description}")
        print(f"Expected tier: {expected}")
        print(f"{'='*60}")

        try:
            crew_instance = SafetyCrew()
            crew_instance._patient_id = patient_id

            crew_inputs = _build_crew_inputs(tc["input"], patient_id)
            print(f"--- About to kickoff {tc_id} with Groq! ---", flush=True)
            result = crew_instance.crew().kickoff(inputs=crew_inputs)
            print(f"--- Finished kickoff for {tc_id} ---", flush=True)
            # Delay to respect TPM limits
            time.sleep(18)

            raw = result.raw if hasattr(result, "raw") else str(result)
            actual = _parse_tier(raw)

            passed = actual == expected
            status = "✅ PASS" if passed else "❌ FAIL"

            results.append(
                {
                    "id": tc_id,
                    "description": description,
                    "expected": expected,
                    "actual": actual,
                    "status": status,
                    "passed": passed,
                }
            )

            print(f"\nActual tier:   {actual}")
            print(f"Result:        {status}")

        except Exception as exc:
            results.append(
                {
                    "id": tc_id,
                    "description": description,
                    "expected": expected,
                    "actual": f"ERROR: {exc}",
                    "status": "💥 ERROR",
                    "passed": False,
                }
            )
            print(f"\n💥 ERROR in {tc_id}: {exc}")

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n")
    print("=" * 80)
    print("SAFETY CREW — TEST RESULTS SUMMARY")
    print("=" * 80)
    header = f"{'ID':<6} {'Expected':<12} {'Actual':<12} {'Status':<10} Description"
    print(header)
    print("-" * 80)

    passed_count = 0
    mismatches = []

    for r in results:
        print(
            f"{r['id']:<6} {r['expected']:<12} {r['actual']:<12} {r['status']:<10} {r['description']}"
        )
        if r["passed"]:
            passed_count += 1
        else:
            mismatches.append(r)

    print("=" * 80)
    print(f"TOTAL: {passed_count}/{len(results)} passed")

    # Audit log verification
    print("\n── Audit Log Verification ──────────────────────────────────────────")
    non_none_cases = [tc for tc in TEST_CASES if tc["expected_tier"] != "NONE"]
    audit_ok = 0
    for tc in non_none_cases:
        patient_id = f"test_{tc['id'].lower()}"
        events = read_recent_events(patient_id, n=5)
        if events:
            audit_ok += 1
            print(f"  ✅ {tc['id']} ({patient_id}): {events[0]['tier']} logged")
        else:
            print(f"  ⚠️  {tc['id']} ({patient_id}): no audit log entry found")
    print(f"Audit entries found: {audit_ok}/{len(non_none_cases)} non-NONE cases")

    if mismatches:
        print("\n── ⚠️  MISMATCHES (do not adjust expected tier without approval) ──")
        for r in mismatches:
            print(f"  {r['id']}: expected={r['expected']}, actual={r['actual']}")
        print("\nNOTE: The expected tiers come from the approved rule design.")
        print("Do not silently change expected tiers — flag mismatches and seek approval.")
        sys.exit(1)
    else:
        print("\n✅ All tests passed.")


# ── pytest-compatible test functions ──────────────────────────────────────────

def test_safety_crew_all_cases():
    """pytest entry point — runs all 15 golden test cases."""
    failed = []
    for tc in TEST_CASES:
        patient_id = f"pytest_{tc['id'].lower()}"
        crew_instance = SafetyCrew()
        crew_instance._patient_id = patient_id
        crew_inputs = _build_crew_inputs(tc["input"], patient_id)
        result = crew_instance.crew().kickoff(inputs=crew_inputs)
        # Respect Groq TPM limits: pause between test cases
        time.sleep(18)
        raw = result.raw if hasattr(result, "raw") else str(result)
        actual = _parse_tier(raw)
        if actual != tc["expected_tier"]:
            failed.append(
                f"{tc['id']}: expected {tc['expected_tier']}, got {actual}"
            )
    if failed:
        raise AssertionError(
            "Safety Crew tier mismatches (see above). "
            "Do NOT adjust expected tiers without approval.\n" + "\n".join(failed)
        )


if __name__ == "__main__":
    run_tests()
