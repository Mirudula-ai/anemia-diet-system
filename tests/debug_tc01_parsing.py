"""
Diagnostic script for TC01 — shows raw crew output vs parsed tier side-by-side.

Runs SafetyCrew for TC01 and prints:
  1. The raw crew output exactly as returned (result.raw)
  2. What _parse_tier() extracts from that raw output
  3. The result object's type and all available attributes

This does NOT change any crew logic or tasks.yaml — purely diagnostic.
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

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

# ── Ensure the src directory is on the Python path ──────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anemia_diet_system.crews.safety_crew.safety_crew import SafetyCrew

# ── The exact _parse_tier from test_safety_crew.py (copied verbatim) ────────

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

# ── TC01 definition ─────────────────────────────────────────────────────────

TC01 = {
    "id": "TC01",
    "description": "Heavy bleeding hourly -> EMERGENCY",
    "input": {
        "logged_symptoms": ["soaking through protection every hour"],
        "life_stage": "menstruating",
    },
    "expected_tier": "EMERGENCY",
}


def main():
    patient_id = "debug_tc01"

    # Build inputs the same way the test does
    payload = dict(TC01["input"])
    payload["patient_id"] = patient_id
    crew_inputs = {"patient_input": json.dumps(payload, default=str)}

    print("=" * 80)
    print("DIAGNOSTIC: TC01 — Raw Output vs Parsed Tier")
    print("=" * 80)
    print(f"Crew inputs: {json.dumps(crew_inputs, indent=2)}")
    print()

    crew_instance = SafetyCrew()
    crew_instance._patient_id = patient_id

    print("--- Kicking off SafetyCrew for TC01 ---")
    result = crew_instance.crew().kickoff(inputs=crew_inputs)
    print("--- Kickoff complete ---\n")

    # ── 1. Inspect the result object ────────────────────────────────────────
    print("=" * 80)
    print("SECTION 1: Result Object Inspection")
    print("=" * 80)
    print(f"  type(result)  = {type(result).__name__}")
    print(f"  type(result).__mro__ = {[c.__name__ for c in type(result).__mro__]}")
    print()

    # List all non-dunder attributes
    attrs = [a for a in dir(result) if not a.startswith("_")]
    print(f"  Public attributes: {attrs}")
    print()

    # Show key attributes
    for attr_name in ["raw", "json_dict", "pydantic", "tasks_output", "token_usage"]:
        if hasattr(result, attr_name):
            val = getattr(result, attr_name)
            val_repr = repr(val)
            if len(val_repr) > 500:
                val_repr = val_repr[:500] + "... [TRUNCATED]"
            print(f"  result.{attr_name} = {val_repr}")
            print(f"    type = {type(val).__name__}")
            print()

    # ── 2. Raw output exactly as returned ───────────────────────────────────
    raw_output = result.raw if hasattr(result, "raw") else str(result)
    print("=" * 80)
    print("SECTION 2: Raw Output (result.raw)")
    print("=" * 80)
    print(f"  type  = {type(raw_output).__name__}")
    print(f"  len   = {len(raw_output)}")
    print(f"  repr  = {repr(raw_output[:2000])}")
    print()
    print("  --- BEGIN RAW OUTPUT ---")
    print(raw_output)
    print("  --- END RAW OUTPUT ---")
    print()

    # ── 3. What _parse_tier extracts ────────────────────────────────────────
    print("=" * 80)
    print("SECTION 3: _parse_tier() Result")
    print("=" * 80)

    # Step through the parsing manually to show each stage
    stripped = raw_output.strip()
    print(f"  After strip(): len={len(stripped)}")
    print(f"  Starts with '```': {stripped.startswith('```')}")

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
        print(f"  After fence removal: len={len(stripped)}")

    try:
        data = json.loads(stripped)
        print(f"  json.loads succeeded: type={type(data).__name__}")
        print(f"  Keys: {list(data.keys()) if isinstance(data, dict) else 'NOT A DICT'}")
        tier_value = data.get("tier", "UNKNOWN") if isinstance(data, dict) else "NOT_A_DICT"
        print(f"  data.get('tier', 'UNKNOWN') = {repr(tier_value)}")
        print(f"  .upper() = {repr(tier_value.upper() if isinstance(tier_value, str) else tier_value)}")
    except json.JSONDecodeError as e:
        print(f"  json.loads FAILED: {e}")
        print(f"  Falling back to keyword search...")
        for tier in ("EMERGENCY", "URGENT", "MONITOR", "NONE"):
            found = tier in stripped.upper()
            print(f"    '{tier}' in raw.upper() = {found}")

    # Final parsed tier
    parsed = _parse_tier(raw_output)
    print()
    print(f"  >>> FINAL _parse_tier() result: {repr(parsed)}")
    print(f"  >>> Expected tier:              {repr(TC01['expected_tier'])}")
    print(f"  >>> Match: {parsed == TC01['expected_tier']}")

    # ── 4. Check task outputs individually ──────────────────────────────────
    if hasattr(result, "tasks_output") and result.tasks_output:
        print()
        print("=" * 80)
        print("SECTION 4: Individual Task Outputs")
        print("=" * 80)
        for i, task_out in enumerate(result.tasks_output):
            print(f"\n  --- Task {i} ---")
            print(f"  type = {type(task_out).__name__}")
            if hasattr(task_out, "raw"):
                task_raw = task_out.raw
                print(f"  .raw type = {type(task_raw).__name__}")
                print(f"  .raw len  = {len(str(task_raw))}")
                raw_str = str(task_raw)
                if len(raw_str) > 1000:
                    raw_str = raw_str[:1000] + "... [TRUNCATED]"
                print(f"  .raw = {raw_str}")
            if hasattr(task_out, "pydantic") and task_out.pydantic is not None:
                print(f"  .pydantic = {task_out.pydantic}")
            if hasattr(task_out, "json_dict") and task_out.json_dict is not None:
                print(f"  .json_dict = {task_out.json_dict}")
            if hasattr(task_out, "description"):
                desc = str(task_out.description)[:100]
                print(f"  .description = {desc}...")

    # ── 5. str(result) vs result.raw ────────────────────────────────────────
    print()
    print("=" * 80)
    print("SECTION 5: str(result) vs result.raw comparison")
    print("=" * 80)
    str_result = str(result)
    print(f"  str(result) == result.raw : {str_result == raw_output}")
    if str_result != raw_output:
        print(f"  str(result) len = {len(str_result)}")
        print(f"  result.raw  len = {len(raw_output)}")
        print(f"  str(result)[:500] = {repr(str_result[:500])}")

    print()
    print("=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
