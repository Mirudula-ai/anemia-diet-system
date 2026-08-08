"""
Run a single flow test case (FT01..FT07) with full unbuffered output.
Usage:  uv run python -u tests/run_single_ft.py FT01
"""
from __future__ import annotations

import os, sys, time
from pathlib import Path

# ── Windows UTF-8 ───────────────────────────────────────────────────────────
if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

# ── Env patches (before any crewai/litellm import) ─────────────────────────
os.environ["DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DROP_PARAMS"] = "True"

import litellm

def _clean_dict(obj):
    if isinstance(obj, dict):
        obj.pop("cache_control", None)
        obj.pop("cache_breakpoint", None)
        for v in list(obj.values()):
            _clean_dict(v)
    elif isinstance(obj, list):
        for item in obj:
            _clean_dict(item)

_orig = litellm.completion
def _patched(*a, **kw):
    _clean_dict(kw)
    for attempt in range(8):
        try:
            return _orig(*a, **kw)
        except litellm.exceptions.RateLimitError as exc:
            if attempt == 7:
                raise exc
            wait_sec = 15 * (attempt + 1)
            print(f"\n[RateLimitHandler] Groq limit hit ({exc}). Sleeping {wait_sec}s before retry {attempt + 1}/7...")
            time.sleep(wait_sec)

litellm.completion = _patched
litellm.drop_params = True

from dotenv import load_dotenv
load_dotenv(override=False)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anemia_diet_system.flow import AnemiaFlow

# ── Test-case inputs ────────────────────────────────────────────────────────
SAMPLE_PLAN = [
    {"name": "Spinach (cooked)", "time_slot": "morning"},
    {"name": "Lentils (boiled)", "time_slot": "afternoon-evening"},
    {"name": "Chickpeas (roasted)", "time_slot": "night"},
]

CASES = {
    "FT01": {
        "method": "on_intake_complete",
        "inputs": {
            "patient_id": "test_ft01",
            "diet_type": "vegetarian",
            "symptom_log": ["slightly tired today"],
            "pregnancy_status": "not_pregnant",
            "allergies": [],
            "existing_conditions": [],
            "current_medications": [],
            "biomarkers": {},
        },
    },
    "FT02": {
        "method": "on_intake_complete",
        "inputs": {
            "patient_id": "test_ft02",
            "diet_type": "vegetarian",
            "symptom_log": ["fainted this morning", "chest pain"],
            "pregnancy_status": "not_pregnant",
            "allergies": [],
            "existing_conditions": [],
            "current_medications": [],
            "biomarkers": {},
        },
    },
    "FT03": {
        "method": "on_pdf_upload",
        "inputs": {
            "patient_id": "test_ft03",
            "biomarkers": {"ferritin": 15, "MCV": 72},
            "existing_conditions": [],
            "current_plan": SAMPLE_PLAN,
            "safety_tier": "NONE",
            "safety_message": "",
        },
    },
    "FT04": {
        "method": "on_symptom_logged",
        "inputs": {
            "patient_id": "test_ft04",
            "symptom_log": ["mild fatigue"],
            "last_known_tier": "NONE",
            "life_stage": "menstruating",
        },
    },
    "FT05": {
        "method": "on_symptom_logged",
        "inputs": {
            "patient_id": "test_ft05",
            "symptom_log": ["fainted", "shortness of breath at rest"],
            "last_known_tier": "NONE",
            "life_stage": "menstruating",
            "current_plan": SAMPLE_PLAN,
        },
    },
    "FT06": {
        "method": "on_feedback_submitted",
        "inputs": {
            "patient_id": "test_ft06",
            "raw_feedback_text": "didn't like the lentils",
            "current_plan": SAMPLE_PLAN,
            "logged_meals": [],
        },
    },
    "FT07": {
        "method": "on_feedback_submitted",
        "inputs": {
            "patient_id": "test_ft07",
            "raw_feedback_text": "I think I'm allergic to chickpeas, felt unwell",
            "current_plan": SAMPLE_PLAN,
            "logged_meals": [],
            "diet_type": "vegetarian",
            "allergies": ["chickpeas"],
        },
    },
}

# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1].upper() not in CASES:
        print(f"Usage: python -u tests/run_single_ft.py <{'|'.join(CASES)}>")
        sys.exit(1)

    tc_id = sys.argv[1].upper()
    tc = CASES[tc_id]
    method_name = tc["method"]
    inputs = tc["inputs"]

    print(f"\n{'='*70}")
    print(f"  Running {tc_id} — calling AnemiaFlow.{method_name}()")
    print(f"{'='*70}\n")
    print(f"[runner] Creating AnemiaFlow instance...")
    t0 = time.time()

    flow = AnemiaFlow()
    method = getattr(flow, method_name)

    print(f"[runner] Calling flow.{method_name}()  (t=0s)")
    result = method(inputs)
    elapsed = time.time() - t0

    print(f"\n{'='*70}")
    print(f"  {tc_id} COMPLETED in {elapsed:.1f}s")
    print(f"{'='*70}")
    print(f"[runner] Result type : {type(result).__name__}")
    print(f"[runner] Result keys : {list(result.keys()) if isinstance(result, dict) else 'N/A'}")

    import json
    print(f"\n[runner] Full result JSON:")
    json_str = json.dumps(result, indent=2, default=str, ensure_ascii=False)
    print(json_str)

    with open(f"EXEC_{tc_id}.json", "w", encoding="utf-8") as f:
        json.dump({"passed": True, "elapsed": elapsed, "output": result}, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n[runner] Saved result to EXEC_{tc_id}.json")
    print(f"[runner] Done.")
