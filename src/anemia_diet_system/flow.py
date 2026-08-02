"""
Anemia Diet System — Safety-Crew-only Flow.

Entry point: AnemiaFlow.kickoff(inputs={...})

This flow will be extended with @listen/@router branches for Diet Planning,
Biomarker, and other crews. For now it runs Safety Crew standalone.
"""
from __future__ import annotations

import json
from typing import Any

from crewai.flow.flow import Flow, start

from anemia_diet_system.crews.safety_crew.safety_crew import SafetyCrew


class AnemiaFlow(Flow):
    """
    Top-level flow for the Anemia Diet System.

    Currently: single @start entry that runs Safety Crew and returns its output.
    Future: @listen/@router branches for Diet Planning, Biomarker tracking, etc.
    """

    @start()
    def run_safety_crew(self) -> dict[str, Any]:
        """
        Accepts a PatientProfile-shaped input dict and runs Safety Crew.

        Expected keys (at minimum):
          - patient_id: str
          - logged_symptoms: list[str]   (free-text symptom strings)
          - life_stage: str               (e.g. "menstruating", "pregnant")
          - tagged_symptoms: list[dict]   (optional; pre-tagged)
          - biomarkers: dict              (optional)
          - family_history_flags: list    (optional)
          - prior_monitor_flags_last_window: bool (optional)
          - is_pregnant: bool             (optional)
        """
        inputs: dict[str, Any] = dict(self.state) if self.state else {}  # populated by kickoff(inputs=...)

        patient_id = inputs.get("patient_id", "unknown")

        # Instantiate the crew and inject the patient_id for audit logging.
        crew_instance = SafetyCrew()
        crew_instance._patient_id = patient_id

        # Build the crew input — pass the full profile through as JSON so the
        # LLM agents can reference every field.
        crew_inputs = {
            "patient_input": json.dumps(inputs, default=str),
        }

        result = crew_instance.crew().kickoff(inputs=crew_inputs)

        # Return as dict for downstream @listen steps (future).
        try:
            raw = result.raw.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
            return json.loads(raw)
        except Exception:
            return {"raw": result.raw if hasattr(result, "raw") else str(result)}

    # ── Future extension points (stubs) ───────────────────────────────────────
    # @listen(run_safety_crew)
    # @router(run_safety_crew)
    # def route_by_tier(self, safety_output): ...
