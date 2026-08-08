"""
Safety Crew — symptom tagging → safety tier evaluation.

Two tasks run in sequence:
    1. symptom_tagging_task  (symptom_tagger_agent)
    2. safety_tier_evaluation_task  (symptom_escalation_agent)

After the second task completes, the crew's after-kickoff hook automatically
calls the audit logger for any tier other than NONE.
"""
from __future__ import annotations

import json
import os
from typing import Any

os.environ["DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DROP_PARAMS"] = "True"

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

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, after_kickoff, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

from anemia_diet_system.tools.safety_audit_logger import log_safety_event


@CrewBase
class SafetyCrew:
    """
    Safety Crew for the Anemia Diet System.

    Orchestrates symptom tagging and safety escalation tier evaluation.
    Writes to the safety audit log whenever a non-NONE tier is returned.
    """

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # Injected at kickoff time via inputs; default to a placeholder.
    _patient_id: str = "unknown"

    # ── Agents ────────────────────────────────────────────────────────────────

    @agent
    def symptom_tagger_agent(self) -> Agent:
        # Safety classification MUST use a capable model.
        # SAFETY_LLM_MODEL overrides LLM_MODEL for this crew.
        model_name = os.getenv("SAFETY_LLM_MODEL", "groq/llama-3.3-70b-versatile")
        my_llm = LLM(
            model=model_name,
            timeout=30,
        )
        return Agent(
            config=self.agents_config["symptom_tagger_agent"],  # type: ignore[index]
            llm=my_llm,
            cache=False,
            max_retry_limit=2,
            verbose=True,
        )

    @agent
    def symptom_escalation_agent(self) -> Agent:
        # Safety classification MUST use a capable model.
        # SAFETY_LLM_MODEL overrides LLM_MODEL for this crew.
        model_name = os.getenv("SAFETY_LLM_MODEL", "groq/llama-3.3-70b-versatile")
        my_llm = LLM(
            model=model_name,
            timeout=30,
        )
        return Agent(
            config=self.agents_config["symptom_escalation_agent"],  # type: ignore[index]
            llm=my_llm,
            cache=False,
            max_retry_limit=2,
            verbose=True,
        )

    # ── Tasks ─────────────────────────────────────────────────────────────────

    @task
    def symptom_tagging_task(self) -> Task:
        # Define response format to enforce clinical_flag as a string enum
        from pydantic import BaseModel, Field
        from typing import Literal, List

        class SymptomTag(BaseModel):
            name: str = Field(..., description="Normalized symptom name")
            severity: Literal["mild", "moderate", "severe"] = Field(..., description="Severity level")
            clinical_flag: Literal["routine", "watch", "red_flag"] = Field(..., description="Clinical relevance flag as string")
            raw_text: str = Field(..., description="Original text fragment")

        class TaggedOutput(BaseModel):
            tagged_symptoms: List[SymptomTag]
            life_stage_context: dict = Field(default_factory=dict)
            biomarkers: dict = Field(default_factory=dict)
            family_history_flags: List[str] = Field(default_factory=list)
            prior_monitor_flags_last_window: bool = False

        return Task(
            config=self.tasks_config["symptom_tagging_task"],  # type: ignore[index]
            response_format=TaggedOutput,
        )

    @task
    def safety_tier_evaluation_task(self) -> Task:
        return Task(
            config=self.tasks_config["safety_tier_evaluation_task"],  # type: ignore[index]
            context=[self.symptom_tagging_task()],
        )

    # ── Lifecycle hooks ───────────────────────────────────────────────────────

    @after_kickoff
    def _audit_log(self, result: Any) -> Any:
        """
        After kickoff: parse the final task output and write to audit log
        if the tier is not NONE.
        """
        try:
            # The result.raw may be a JSON string from the evaluation task.
            raw = result.raw if hasattr(result, "raw") else str(result)

            # Strip markdown fences if the LLM wrapped the JSON.
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                ).strip()

            data = json.loads(raw)
            tier = data.get("tier", "NONE").upper()
            rules_fired = data.get("rules_fired", [])
            tagged_symptoms = data.get("tagged_symptoms", [])

            patient_id = getattr(self, "_patient_id", "unknown")
            # Print tagged symptoms for TC03 and TC06 for debugging
            if patient_id.lower().endswith("tc03") or patient_id.lower().endswith("tc06"):
                print(f"[Debug] Tagged symptoms for {patient_id}: {json.dumps(tagged_symptoms, indent=2)}")
            log_safety_event(
                patient_id=patient_id,
                tier=tier,
                rules_fired=rules_fired,
                tagged_symptoms=tagged_symptoms,
            )
        except Exception as exc:
            # Never crash the crew over a logging failure.
            print(f"[SafetyCrew] Audit log warning: {exc}")

        return result

    # ── Crew ──────────────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        """Creates the Safety Crew with sequential task execution."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            cache=False,
            max_rpm=2,
            verbose=True,
        )
