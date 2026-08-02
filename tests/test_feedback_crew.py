import json, os, sys, time
from pathlib import Path

# Ensure src is on PYTHONPATH for imports
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root / "src"))

# Set dummy API key and deterministic model / caching (mirrors other tests)
os.environ.setdefault('OPENAI_API_KEY', 'dummy')
os.environ.setdefault('LLM_MODEL', 'openai/gpt-4o-mini')
os.environ.setdefault('DISABLE_PROMPT_CACHING', 'True')
os.environ.setdefault('LITELLM_DISABLE_PROMPT_CACHING', 'True')
os.environ.setdefault('LITELLM_DROP_PARAMS', 'True')

from anemia_diet_system.crews.feedback_crew.feedback_crew import FeedbackCrew

CURRENT_PLAN = [
    {"name": "Spinach (cooked)", "time_slot": "morning"},
    {"name": "Lentils (boiled)", "time_slot": "afternoon-evening"},
    {"name": "Chickpeas (roasted)", "time_slot": "night"},
]

TEST_CASES = [
    {
        "id": "TC-F01",
        "desc": "dislike lentils",
        "input": {"raw_feedback_text": "didn't like the lentils", "current_plan": CURRENT_PLAN, "logged_meals": []},
        "check": lambda out, tasks: (
            out.get('feedback_type') == 'dislike' and 'lentils' in (out.get('target_item') or '').lower()
        ),
    },
    {
        "id": "TC-F02",
        "desc": "symptom after spinach",
        "input": {"raw_feedback_text": "felt dizzy after eating spinach", "current_plan": CURRENT_PLAN, "logged_meals": []},
        "check": lambda out, tasks: (
            out.get('feedback_type') == 'symptom' and 'spinach' in (out.get('target_item') or '').lower()
        ),
    },
    {
        "id": "TC-F03",
        "desc": "lentils skipped 3 days",
        "input": {
            "raw_feedback_text": "",  # no new feedback
            "current_plan": CURRENT_PLAN,
            "logged_meals": [
                {"day": 1, "skipped": ["Lentils (boiled)"]},
                {"day": 2, "skipped": ["Lentils (boiled)"]},
                {"day": 3, "skipped": ["Lentils (boiled)"]},
            ],
        },
        "check": lambda out, tasks: (
            out.get('pattern_note') and 'lentils' in out.get('pattern_note').lower()
        ),
    },
    {
        "id": "TC-F04",
        "desc": "single skip, no pattern",
        "input": {
            "raw_feedback_text": "",  # no new feedback
            "current_plan": CURRENT_PLAN,
            "logged_meals": [
                {"day": 1, "skipped": ["Lentils (boiled)"]},
                {"day": 2, "skipped": []},
                {"day": 3, "skipped": []},
            ],
        },
        "check": lambda out, tasks: (out.get('pattern_note') == '' or out.get('pattern_note') is None),
    },
    {
        "id": "TC-F05",
        "desc": "revise plan changes only lentils",
        "input": {"raw_feedback_text": "didn't like the lentils", "current_plan": CURRENT_PLAN, "logged_meals": []},
        "check": lambda out, tasks: (
            isinstance(out.get('revised_plan'), list) and
            any('lentils' in item.get('name', '').lower() for item in out.get('revised_plan')) and
            all(
                any(item.get('name') == orig.get('name') for item in out.get('revised_plan'))
                for orig in [
                    {"name": "Spinach (cooked)"},
                    {"name": "Chickpeas (roasted)"},
                ]
            )
        ),
    },
    {
        "id": "TC-F06",
        "desc": "allergy mention triggers recheck",
        "input": {"raw_feedback_text": "I think I'm allergic to chickpeas, felt unwell", "current_plan": CURRENT_PLAN, "logged_meals": []},
        "check": lambda out, tasks: out.get('requires_allergy_recheck') is True,
    },
    {
        "id": "TC-F07",
        "desc": "dislike without allergy does not trigger recheck",
        "input": {"raw_feedback_text": "didn't like the lentils", "current_plan": CURRENT_PLAN, "logged_meals": []},
        "check": lambda out, tasks: out.get('requires_allergy_recheck') is False,
    },
    {
        "id": "TC-F08",
        "desc": "positive feedback, encouraging note",
        "input": {"raw_feedback_text": "everything was great today", "current_plan": CURRENT_PLAN, "logged_meals": []},
        "check": lambda out, tasks: (
            isinstance(out.get('note'), str) and out.get('note') and not any(word in out.get('note').lower() for word in ['bad', 'scold', 'negative'])
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
        payload = {
            "raw_feedback_text": tc["input"].get("raw_feedback_text", ""),
            "current_plan": tc["input"]["current_plan"],
            "logged_meals": tc["input"].get("logged_meals", []),
            "patient_id": f"test_{tc['id'].lower()}",
        }
        crew_inputs = {"patient_input": json.dumps(payload)}
        print(f"\n{'='*60}\nRunning {tc['id']}: {tc['desc']}\n{'='*60}\n")
        crew = FeedbackCrew()
        result = crew.crew().kickoff(inputs=crew_inputs)
        time.sleep(18)  # rate‑limit delay
        # task outputs list
        try:
            tasks = result.tasks_output
        except AttributeError:
            tasks = []
        # parse the relevant task output (revise_plan_task is last)
        raw = tasks[-1].raw if tasks else str(result)
        out = parse_json(raw)
        passed = tc["check"](out, tasks)
        status = "✅ PASS" if passed else "❌ FAIL"
        results.append({"id": tc["id"], "desc": tc["desc"], "status": status})
        print(f"Result: {status}\n")
    # Summary
    print("\n" + "="*80)
    print("FEEDBACK CREW — TEST RESULTS SUMMARY")
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
