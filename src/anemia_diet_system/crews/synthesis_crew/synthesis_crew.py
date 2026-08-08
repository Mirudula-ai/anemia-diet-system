from __future__ import annotations

import os
import json
import warnings
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task, after_kickoff

os.environ["DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DROP_PARAMS"] = "True"

import litellm
litellm.drop_params = True

def _remove_cache_control_synthesis(kwargs):
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

if not hasattr(litellm, "input_callback") or not litellm.input_callback:
    litellm.input_callback = [_remove_cache_control_synthesis]
elif _remove_cache_control_synthesis not in litellm.input_callback:
    litellm.input_callback.append(_remove_cache_control_synthesis)

@CrewBase
class SynthesisCrew:
    """Crew that synthesizes the final patient recommendation, enforcing hard safety rules."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # ── Agents ────────────────────────────────────────────────────────────────

    @agent
    def symptom_trend_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["symptom_trend_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    @agent
    def feedback_adherence_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["feedback_adherence_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    @agent
    def synthesis_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["synthesis_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    # ── Tasks ────────────────────────────────────────────────────────────────

    @task
    def track_symptom_trends_task(self) -> Task:
        return Task(
            config=self.tasks_config["track_symptom_trends_task"],  # type: ignore[index]
        )

    @task
    def generate_adherence_feedback_task(self) -> Task:
        return Task(
            config=self.tasks_config["generate_adherence_feedback_task"],  # type: ignore[index]
        )

    @task
    def synthesize_final_output_task(self) -> Task:
        return Task(
            config=self.tasks_config["synthesize_final_output_task"],  # type: ignore[index]
            context=[self.track_symptom_trends_task(), self.generate_adherence_feedback_task()],
        )

    # ── Post‑kickoff safety enforcement ───────────────────────────────────────

    @after_kickoff
    def enforce_safety(self, result):
        """Parse the JSON output of ``synthesize_final_output_task`` and enforce hard safety rules.

        - If ``content_mode`` is ``"safety_override"`` we force ``morning``,
          ``afternoon_evening``, ``night`` and ``closing_line`` to ``None``.
        - If ``safety_tier`` is ``URGENT`` or ``EMERGENCY`` but the model
          did not set ``content_mode`` to ``"safety_override"``, we coerce it
          and also null out the plan fields, emitting a warning.
        The (potentially modified) ``result`` is returned so the crew caller
        receives the corrected JSON string.
        """
        try:
            data = json.loads(result.raw)
        except Exception:
            # If parsing fails, return the original result unchanged.
            return result

        # Enforce null fields when safety override is active.
        if data.get("content_mode") == "safety_override":
            for key in ["morning", "afternoon_evening", "night", "closing_line"]:
                data[key] = None
        else:
            # If safety tier demands an override but the model missed it.
            if data.get("safety_tier") in ("URGENT", "EMERGENCY"):
                warnings.warn(
                    "Safety tier is URGENT/EMERGENCY but content_mode is not 'safety_override'; forcing override."
                )
                data["content_mode"] = "safety_override"
                for key in ["morning", "afternoon_evening", "night", "closing_line"]:
                    data[key] = None

        # Write back the corrected JSON string.
        result.raw = json.dumps(data, ensure_ascii=False, indent=2)
        return result

    # ── Crew ────────────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        """Creates the Synthesis Crew with sequential execution."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            cache=False,
            max_rpm=2,
            verbose=True,
        )
