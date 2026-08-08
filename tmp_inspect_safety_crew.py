import os, sys, json
os.environ["DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DROP_PARAMS"] = "True"

import litellm
from pathlib import Path

# Setup paths
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

# Load env variables
from dotenv import load_dotenv
load_dotenv(override=True)

# Patch litellm to dump prompts
orig_completion = litellm.completion

def custom_completion(*args, **kwargs):
    print("\n" + "="*80)
    print(f"LITELLM CALL - Model: {kwargs.get('model')}")
    print("="*80)
    messages = kwargs.get("messages", [])
    for msg in messages:
        print(f"\n--- ROLE: {msg.get('role')} ---")
        print(msg.get('content'))
    print("="*80 + "\n")
    return orig_completion(*args, **kwargs)

litellm.completion = custom_completion
litellm.drop_params = True

# Run SafetyCrew
from anemia_diet_system.crews.safety_crew.safety_crew import SafetyCrew

safety_payload = {
    "patient_id": "test_ft02",
    "logged_symptoms": ["fainted this morning", "chest pain"],
    "life_stage": "menstruating",
    "is_pregnant": False,
    "biomarkers": {},
    "family_history_flags": [],
    "prior_monitor_flags_last_window": False,
}

c = SafetyCrew()
c._patient_id = "test_ft02"
print("Starting SafetyCrew kickoff...")
res = c.crew().kickoff(inputs={"patient_input": json.dumps(safety_payload, default=str)})
print("SafetyCrew kickoff completed.")
