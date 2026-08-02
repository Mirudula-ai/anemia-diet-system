import json, os, sys, time
from pathlib import Path

# Ensure src is on PYTHONPATH for imports
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root / "src"))

# Use a deterministic small model and disable caching (mirrors test suite)
os.environ.setdefault('LLM_MODEL', 'openai/gpt-4o-mini')
os.environ.setdefault('DISABLE_PROMPT_CACHING', 'True')
os.environ.setdefault('LITELLM_DISABLE_PROMPT_CACHING', 'True')
os.environ.setdefault('LITELLM_DROP_PARAMS', 'True')

from anemia_diet_system.crews.biomarker_crew.biomarker_crew import BiomarkerCrew

# Helper to parse JSON output (handles markdown fences)
def parse_output(raw: str):
    raw = raw.strip()
    if raw.startswith('```'):
        lines = raw.splitlines()
        raw = "\n".join([l for l in lines if not l.strip().startswith('```')])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

TEST_CASES = [
    {
        "id": "TC-B01",
        "description": "empty biomarkers -> status 'no_lab_data'",
        "input": {"biomarkers": {}, "existing_conditions": []},
        "check": lambda out, tasks: out.get('status') == 'no_lab_data',
    },
    {
        "id": "TC-B02",
        "description": "low ferritin, no inflammation -> flag false, normal cutoff",
        "input": {"biomarkers": {"ferritin": 15, "MCV": 75}, "existing_conditions": []},
        "check": lambda out, tasks: (
            json.loads(tasks[0].raw if hasattr(tasks[0], 'raw') else '{}').get('inflammation_flag') is False
            and out.get('cutoff_used') == 'normal'
        ),
    },
    {
        "id": "TC-B03",
        "description": "elevated CRP & IBD -> flag true, inflamed cutoff",
        "input": {"biomarkers": {"ferritin": 45, "CRP": "elevated"}, "existing_conditions": ["IBD"]},
        "check": lambda out, tasks: (
            json.loads(tasks[0].raw if hasattr(tasks[0], 'raw') else '{}').get('inflammation_flag') is True
            and out.get('cutoff_used') == 'inflamed'
        ),
    },
    {
        "id": "TC-B04",
        "description": "ferritin 90 with inflamed cutoff -> deficiency observation present",
        "input": {"biomarkers": {"ferritin": 90, "CRP": "elevated"}, "existing_conditions": ["IBD"]},
        "check": lambda out, tasks: (
            json.loads(tasks[0].raw if hasattr(tasks[0], 'raw') else '{}').get('inflammation_flag') is True
            and out.get('cutoff_used') == 'inflamed'
            and any('deficiency' in obs.lower() for obs in out.get('observations', []))
        ),
    },
    {
        "id": "TC-B05",
        "description": "same ferritin 45 without inflammation -> no deficiency observation",
        "input": {"biomarkers": {"ferritin": 45}, "existing_conditions": []},
        "check": lambda out, tasks: (
            json.loads(tasks[0].raw if hasattr(tasks[0], 'raw') else '{}').get('inflammation_flag') is False
            and out.get('cutoff_used') == 'normal'
            and not any('deficiency' in obs.lower() for obs in out.get('observations', []))
        ),
    },
    {
        "id": "TC-B06",
        "description": "ambiguous data -> inflammation_flag defaults false",
        "input": {"biomarkers": {"ferritin": 30}, "existing_conditions": []},
        "check": lambda out, tasks: json.loads(tasks[0].raw if hasattr(tasks[0], 'raw') else '{}').get('inflammation_flag') is False,
    },
    {
        "id": "TC-B07",
        "description": "inflamed case with reticulocyte hemoglobin weighted",
        "input": {"biomarkers": {"ferritin": 45, "reticulocyte_hemoglobin": 22, "CRP": "elevated"}, "existing_conditions": ["PCOS"]},
        "check": lambda out, tasks: (
            json.loads(tasks[0].raw if hasattr(tasks[0], 'raw') else '{}').get('inflammation_flag') is True
            and out.get('cutoff_used') == 'inflamed'
            and any('reticulocyte' in obs.lower() or 'stfr' in obs.lower() for obs in out.get('observations', []))
        ),
    },
]

def run_tests():
    results = []
    for tc in TEST_CASES:
        tc_id = tc["id"]
        description = tc["description"]
        payload = dict(tc["input"]).copy()
        payload["patient_id"] = f"test_{tc_id.lower()}"
        crew_inputs = {"patient_input": json.dumps(payload)}
        print(f"\n{'='*60}\nRunning {tc_id}: {description}\n{'='*60}\n")
        crew = BiomarkerCrew()
        result = crew.crew().kickoff(inputs=crew_inputs)
        time.sleep(18)  # rate‑limit delay
        raw = result.raw if hasattr(result, "raw") else str(result)
        out = parse_output(raw)
        # Grab task outputs for inflammation flag checks
        try:
            tasks = result.tasks_output
        except AttributeError:
            tasks = []
        passed = tc["check"](out, tasks)
        status = "✅ PASS" if passed else "❌ FAIL"
        results.append({"id": tc_id, "description": description, "status": status})
        print(f"Result: {status}\n")
    # Summary table
    print("\n" + "="*80)
    print("BIOMARKER CREW — TEST RESULTS SUMMARY")
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
