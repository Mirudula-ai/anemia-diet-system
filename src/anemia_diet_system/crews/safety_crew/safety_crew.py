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


def _enforce_safety_floor(data: dict[str, Any], task1_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Deterministic post-processing safety checks that act as a tier floor.
    Ensures safety rules are strictly enforced even if LLM output missed them.
    """
    tier_map = {"NONE": 0, "MONITOR": 1, "URGENT": 2, "EMERGENCY": 3}
    rev_tier_map = {0: "NONE", 1: "MONITOR", 2: "URGENT", 3: "EMERGENCY"}

    current_tier_str = str(data.get("tier", "NONE")).upper()
    current_tier_val = tier_map.get(current_tier_str, 0)
    target_tier_val = current_tier_val

    rules_fired = list(data.get("rules_fired", []))
    tagged_symptoms = data.get("tagged_symptoms", [])

    # Emergency check across name and raw_text
    emergency_terms = [
        "faint", "syncope", "lost consciousness", "blacked out", "chest pain",
        "shortness of breath", "out of breath", "breathless", "black stool",
        "tarry stool", "melena", "soaking through protection", "soaking pad", "heavy bleeding hourly"
    ]
    for tag in tagged_symptoms:
        text = f"{tag.get('name', '')} {tag.get('raw_text', '')}".lower()
        if any(term in text for term in emergency_terms):
            if target_tier_val < tier_map["EMERGENCY"]:
                target_tier_val = tier_map["EMERGENCY"]
                rules_fired.append("Deterministic floor: Emergency symptom detected")
            break

    # 1. Palpitations + Dizziness check
    palp_terms = ["palpitation", "racing heart", "heart racing", "tachycardia"]
    dizzy_terms = ["dizzy", "dizziness", "lightheaded"]

    has_palp = any(
        any(pt in f"{t.get('name', '')} {t.get('raw_text', '')}".lower() for pt in palp_terms)
        for t in tagged_symptoms
    )
    has_dizzy = any(
        any(dt in f"{t.get('name', '')} {t.get('raw_text', '')}".lower() for dt in dizzy_terms)
        for t in tagged_symptoms
    )

    if has_palp and has_dizzy:
        if target_tier_val < tier_map["URGENT"]:
            target_tier_val = tier_map["URGENT"]
            rules_fired.append("Deterministic floor: Palpitations + Dizziness combo detected")

    # 2. 3+ moderate symptoms check
    mod_count = sum(1 for t in tagged_symptoms if str(t.get("severity", "")).lower() == "moderate")
    if mod_count >= 3:
        if target_tier_val < tier_map["URGENT"]:
            target_tier_val = tier_map["URGENT"]
            rules_fired.append("Deterministic floor: 3+ moderate symptoms detected")

    # 3. Escalation-persistence check (Option A)
    prior_monitor = False
    prior_symptom_name = None

    if task1_data and isinstance(task1_data, dict):
        prior_monitor = bool(task1_data.get("prior_monitor_flags_last_window", False))
        prior_symptom_name = task1_data.get("prior_monitor_symptom_name") or task1_data.get("prior_symptom_name")
    elif "prior_monitor_flags_last_window" in data:
        prior_monitor = bool(data.get("prior_monitor_flags_last_window", False))
        prior_symptom_name = data.get("prior_monitor_symptom_name") or data.get("prior_symptom_name")

    if prior_monitor and len(tagged_symptoms) > 0:
        if prior_symptom_name:
            matched = any(
                prior_symptom_name.lower() in f"{t.get('name', '')} {t.get('raw_text', '')}".lower()
                for t in tagged_symptoms
            )
            if matched and target_tier_val < tier_map["URGENT"]:
                target_tier_val = tier_map["URGENT"]
                rules_fired.append(f"Deterministic floor: Recurring MONITOR flag matched symptom '{prior_symptom_name}'")
        else:
            has_mod_or_severe = any(str(t.get("severity", "")).lower() in ["moderate", "severe"] for t in tagged_symptoms)
            if has_mod_or_severe and target_tier_val < tier_map["URGENT"]:
                print("[SafetyCrew] Warning: prior_monitor_flags_last_window is True but prior_monitor_symptom_name was not specified. Escalating based on moderate+ symptom recurrence.")
                target_tier_val = tier_map["URGENT"]
                rules_fired.append("Deterministic floor: Recurring MONITOR flag with moderate+ symptom")

    new_tier_str = rev_tier_map[target_tier_val]
    data["tier"] = new_tier_str
    data["rules_fired"] = rules_fired
    return data


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
        After kickoff: parse the final task output, apply deterministic safety floor,
        update result.raw, and write to audit log if the tier is not NONE.
        """
        try:
            raw = result.raw if hasattr(result, "raw") else str(result)

            # Strip markdown fences if the LLM wrapped the JSON.
            raw_clean = raw.strip()
            if raw_clean.startswith("```"):
                lines = raw_clean.splitlines()
                raw_clean = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                ).strip()

            data = json.loads(raw_clean)

            # Retrieve task 1 output for prior_monitor_flags_last_window check
            task1_data = None
            if hasattr(result, "tasks_output") and len(result.tasks_output) > 0:
                t1_raw = str(result.tasks_output[0].raw).strip()
                if t1_raw.startswith("```"):
                    lines = t1_raw.splitlines()
                    t1_raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
                try:
                    task1_data = json.loads(t1_raw)
                except Exception:
                    pass

            # Apply deterministic safety floor
            data = _enforce_safety_floor(data, task1_data)

            # Update result.raw so test runners receive the enforced tier
            updated_json = json.dumps(data, indent=2)
            if hasattr(result, "raw"):
                result.raw = updated_json

            tier = data.get("tier", "NONE").upper()
            rules_fired = data.get("rules_fired", [])
            tagged_symptoms = data.get("tagged_symptoms", [])

            patient_id = getattr(self, "_patient_id", "unknown")
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
