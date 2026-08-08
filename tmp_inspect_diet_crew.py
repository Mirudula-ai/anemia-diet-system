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

# Run DietPlanningCrew
from anemia_diet_system.crews.diet_crew.diet_crew import DietPlanningCrew

diet_payload = {
    "patient_id": "test_ft02",
    "diet_type": "vegetarian",
    "allergies": ["peanuts"],
    "existing_conditions": ["hypertension"],
    "pregnancy_status": "pregnant",
    "trimester": 2,
    "current_medications": ["iron-supplement"],
}

c = DietPlanningCrew()
c._patient_id = "test_ft02"
print("Starting DietPlanningCrew kickoff...")
res = c.crew().kickoff(inputs={"patient_input": json.dumps(diet_payload, default=str)})
print("DietPlanningCrew kickoff completed.")
