"""
Anemia Diet System — main entry point.
"""
from __future__ import annotations

import json
import os
import sys

from anemia_diet_system.flow import AnemiaFlow


def run() -> None:
    """Run the full anemia diet system flow with a sample patient."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    llm_model = os.getenv("LLM_MODEL")
    if not llm_model:
        raise ValueError("LLM_MODEL is not set in the environment.")
    
    provider = llm_model.split("/")[0] if "/" in llm_model else ""
    if provider == "groq" and not os.getenv("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY is missing from the environment.")
    elif provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is missing from the environment.")
    elif provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY is missing from the environment.")

    sample_input = {
        "patient_id": "demo_patient_001",
        "logged_symptoms": ["feeling tired most of the day", "occasional dizziness"],
        "life_stage": "menstruating",
        "prior_monitor_flags_last_window": False,
    }
    flow = AnemiaFlow()
    result = flow.kickoff(inputs=sample_input)
    print("\n=== Safety Crew Result ===")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    run()
