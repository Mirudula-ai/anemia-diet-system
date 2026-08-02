import json
import time
import os
import sys
from pathlib import Path

# Ensure project src is on PYTHONPATH
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root / "src"))

from anemia_diet_system.crews.diet_crew.diet_crew import DietPlanningCrew

# Helper to parse JSON output (handles possible markdown fences)
def parse_output(raw: str):
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join([l for l in lines if not l.strip().startswith("```")])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

TEST_CASES = [
    {
        "id": "TC-D01",
        "description": "diet_type='vegetarian' -> no meat/fish/poultry",
        "input": {"diet_type": "vegetarian"},
        "check": lambda out: all(
            "meat" not in food.get("name", "").lower()
            and "fish" not in food.get("name", "").lower()
            and "poultry" not in food.get("name", "").lower()
            for food in out.get("timed_foods", [])
        ),
    },
    {
        "id": "TC-D02",
        "description": "vegetarian + dairy allergy -> no dairy items",
        "input": {"diet_type": "vegetarian", "allergies": ["dairy"]},
        "check": lambda out: all(
            not any(dairy in food.get("name", "").lower() for dairy in ["paneer", "milk", "curd"])
            for food in out.get("timed_foods", [])
        ),
    },
    {
        "id": "TC-D03",
        "description": "allergy peanuts -> no peanuts anywhere",
        "input": {"allergies": ["peanuts"]},
        "check": lambda out: all(
            "peanut" not in food.get("name", "").lower()
            for food in out.get("timed_foods", [])
        ),
    },
    {
        "id": "TC-D04",
        "description": "existing_conditions diabetes -> adjustments include diabetes reason",
        "input": {"existing_conditions": ["diabetes"]},
        "check": lambda out: any("diabetes" in adj.lower() for adj in out.get("adjustments", [])),
    },
    {
        "id": "TC-D05",
        "description": "existing_conditions CKD -> adjustments mention potassium or phosphorus",
        "input": {"existing_conditions": ["CKD"]},
        "check": lambda out: any(
            "potassium" in adj.lower() or "phosphorus" in adj.lower()
            for adj in out.get("adjustments", [])
        ),
    },
    {
        "id": "TC-D06",
        "description": "pregnant trimester 2 -> pregnancy notes not empty and mention trimester",
        "input": {"pregnancy_status": "pregnant", "trimester": 2},
        "check": lambda out: out.get("pregnancy_notes") and "trimester" in out.get("pregnancy_notes", "").lower(),
    },
    {
        "id": "TC-D07",
        "description": "not pregnant -> pregnancy_adjusted_foods identical to input list",
        "input": {"pregnancy_status": "not_pregnant"},
        "check": lambda out: out.get("pregnancy_adjusted_foods") == out.get("timed_foods"),
    },
    {
        "id": "TC-D08",
        "description": "standard list -> mentions 60+ minute tea/coffee rule",
        "input": {},
        "check": lambda out: any("60" in food.get("inhibitors", "").lower() or "60" in food.get("enhancers", "").lower() for food in out.get("timed_foods", [])),
    },
    {
        "id": "TC-D09",
        "description": "standard list -> all time_slot values valid",
        "input": {},
        "check": lambda out: all(
            food.get("time_slot", "").lower() in ["morning", "afternoon-evening", "night"]
            for food in out.get("timed_foods", [])
        ),
    },
    {
        "id": "TC-D10",
        "description": "no medications -> medication_interactions is 'none'",
        "input": {"current_medications": []},
        "check": lambda out: out.get("medication_interactions") == "none",
    },
    {
        "id": "TC-D11",
        "description": "levothyroxine medication -> warning present",
        "input": {"current_medications": ["levothyroxine"]},
        "check": lambda out: any("levothyroxine" in str(warn).lower() for warn in out.get("medication_interactions", [])),
    },
    {
        "id": "TC-D12",
        "description": "any input -> final output contains both keys",
        "input": {},
        "check": lambda out: "timed_foods" in out and "medication_interactions" in out,
    },
]

def run_tests():
    results = []
    for tc in TEST_CASES:
        tc_id = tc["id"]
        description = tc["description"]
        patient_id = f"test_{tc_id.lower()}"
        crew = DietPlanningCrew()
        crew._patient_id = patient_id
        # Build crew inputs
        payload = dict(tc["input"]).copy()
        payload["patient_id"] = patient_id
        crew_inputs = {"patient_input": json.dumps(payload)}
        print(f"\n{'='*60}\nRunning {tc_id}: {description}\n{'='*60}\n")
        result = crew.crew().kickoff(inputs=crew_inputs)
        # Respect rate limit
        time.sleep(18)
        raw = result.raw if hasattr(result, "raw") else str(result)
        out = parse_output(raw)
        passed = tc["check"](out)
        status = "✅ PASS" if passed else "❌ FAIL"
        results.append({"id": tc_id, "description": description, "status": status})
        print(f"Result: {status}\n")
    # Summary table
    print("\n" + "="*80)
    print("DIET PLANNING CREW — TEST RESULTS SUMMARY")
    print("="*80)
    header = f"{'ID':<8} {'Status':<10} Description"
    print(header)
    print("-"*80)
    passed_cnt = 0
    for r in results:
        print(f"{r['id']:<8} {r['status']:<10} {r['description']}")
        if r['status'] == "✅ PASS":
            passed_cnt += 1
    print("-"*80)
    print(f"TOTAL: {passed_cnt}/{len(results)} passed")

if __name__ == "__main__":
    run_tests()
