import json, os, sys, time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(override=True)

# Ensure src on PYTHONPATH for imports
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root / "src"))

# Load environment variables (dummy keys for LLMs, using existing Groq config)
os.environ.setdefault('OPENAI_API_KEY', 'sk-test')
os.environ.setdefault('GROQ_API_KEY', 'test')
os.environ.setdefault('LLM_MODEL', 'groq/llama-3.3-70b-versatile')
os.environ.setdefault('DISABLE_PROMPT_CACHING', 'True')
os.environ.setdefault('LITELLM_DISABLE_PROMPT_CACHING', 'True')
os.environ.setdefault('LITELLM_DROP_PARAMS', 'True')

from anemia_diet_system.crews.synthesis_crew.synthesis_crew import SynthesisCrew

# Sample diet plan (full set of slots)
FULL_DIET_PLAN = [
    {"name": "Spinach (cooked)", "time_slot": "morning"},
    {"name": "Lentils (boiled)", "time_slot": "afternoon-evening"},
    {"name": "Chickpeas (roasted)", "time_slot": "night"},
]

TEST_CASES = [
    {
        "id": "TC-S01",
        "desc": "EMERGENCY safety overrides full plan",
        "payload": {
            "safety_tier": "EMERGENCY",
            "safety_message": "Seek immediate care",
            "diet_plan": FULL_DIET_PLAN,
        },
        "check": lambda out: (
            out.get("content_mode") == "safety_override"
            and out.get("morning") is None
            and out.get("afternoon_evening") is None
            and out.get("night") is None
            and out.get("closing_line") is None
            and out.get("safety_note") == "Seek immediate care"
        ),
    },
    {
        "id": "TC-S02",
        "desc": "URGENT safety overrides full plan",
        "payload": {
            "safety_tier": "URGENT",
            "safety_message": "See a doctor soon",
            "diet_plan": FULL_DIET_PLAN,
        },
        "check": lambda out: (
            out.get("content_mode") == "safety_override"
            and out.get("morning") is None
            and out.get("afternoon_evening") is None
            and out.get("night") is None
            and out.get("closing_line") is None
            and out.get("safety_note") == "See a doctor soon"
        ),
    },
    {
        "id": "TC-S03",
        "desc": "MONITOR includes plan and safety note",
        "payload": {
            "safety_tier": "MONITOR",
            "safety_message": "Family history noted",
            "diet_plan": FULL_DIET_PLAN,
        },
        "check": lambda out: (
            out.get("content_mode") == "full_plan"
            and isinstance(out.get("morning"), list) and out.get("morning")
            and isinstance(out.get("afternoon_evening"), list) and out.get("afternoon_evening")
            and isinstance(out.get("night"), list) and out.get("night")
            and out.get("safety_note") == "Family history noted"
        ),
    },
    {
        "id": "TC-S04",
        "desc": "NONE tier, no safety note, closing line present",
        "payload": {
            "safety_tier": "NONE",
            "diet_plan": FULL_DIET_PLAN,
        },
        "check": lambda out: (
            out.get("content_mode") == "full_plan"
            and isinstance(out.get("morning"), list) and out.get("morning")
            and isinstance(out.get("afternoon_evening"), list) and out.get("afternoon_evening")
            and isinstance(out.get("night"), list) and out.get("night")
            and out.get("safety_note") is None
            and out.get("closing_line") == "This is food-based support, not a diagnosis."
        ),
    },
    {
        "id": "TC-S05",
        "desc": "EMERGENCY overrides positive content",
        "payload": {
            "safety_tier": "EMERGENCY",
            "safety_message": "Critical alert",
            "diet_plan": FULL_DIET_PLAN,
            "symptom_trends": [{"symptom": "fatigue", "status": "stable_chronic"}],
            "adherence_note": "Great adherence this week!",
        },
        "check": lambda out, raw: (
            out.get("content_mode") == "safety_override"
            and "Great adherence" not in raw
            and "fatigue" not in raw
        ),
    },
    {
        "id": "TC-S06",
        "desc": "EMERGENCY overrides biomarker content",
        "payload": {
            "safety_tier": "EMERGENCY",
            "safety_message": "Urgent safety",
            "diet_plan": FULL_DIET_PLAN,
            "biomarker_observations": {"ferritin": 20, "note": "low iron"},
        },
        "check": lambda out, raw: (
            out.get("content_mode") == "safety_override"
            and "ferritin" not in raw
        ),
    },
    {
        "id": "TC-S07",
        "desc": "NONE tier includes symptom trends and adherence note",
        "payload": {
            "safety_tier": "NONE",
            "diet_plan": FULL_DIET_PLAN,
            "symptom_trends": [{"symptom": "fatigue", "status": "stable_chronic"}],
            "adherence_note": "Skipped breakfast three days",
        },
        "check": lambda out, raw: (
            out.get("content_mode") == "full_plan"
            and "fatigue" in raw
            and "Skipped breakfast" in raw
        ),
    },
]

def parse_json(raw: str):
    raw = raw.strip()
    if raw.startswith('```'):
        lines = raw.splitlines()
        raw = "\n".join([l for l in lines if not l.strip().startswith('```')])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

def run_tests():
    results = []
    for tc in TEST_CASES:
        payload = tc["payload"].copy()
        payload["patient_id"] = f"test_{tc['id'].lower()}"
        crew_inputs = {"patient_input": json.dumps(payload)}
        print(f"\n{'='*60}\nRunning {tc['id']}: {tc['desc']}\n{'='*60}\n")
        crew = SynthesisCrew()
        result = crew.crew().kickoff(inputs=crew_inputs)
        time.sleep(18)  # rate‑limit delay
        try:
            tasks = result.tasks_output
        except AttributeError:
            tasks = []
        # The final task is synthesize_final_output_task (last in list)
        raw = tasks[-1].raw if tasks else str(result)
        out = parse_json(raw)
        # Some checks need raw string as well (for content suppression)
        passed = tc["check"](out, raw) if tc["check"].__code__.co_argcount == 2 else tc["check"](out)
        status = "✅ PASS" if passed else "❌ FAIL"
        results.append({"id": tc["id"], "desc": tc["desc"], "status": status})
        print(f"Result: {status}\n")
    # Summary table
    print("\n" + "="*80)
    print("SYNTHESIS CREW — TEST RESULTS SUMMARY")
    print("="*80)
    print(f"{'ID':<8} {'Status':<10} Description")
    print("-"*80)
    passed_cnt = 0
    for r in results:
        print(f"{r['id']:<8} {r['status']:<10} {r['desc']}")
        if r['status'] == "✅ PASS":
            passed_cnt += 1
    print("-"*80)
    print(f"TOTAL: {passed_cnt}/{len(results)} passed")

if __name__ == "__main__":
    run_tests()
