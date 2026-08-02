from __future__ import annotations

import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task


@CrewBase
class DietPlanningCrew:
    """Diet Planning Crew orchestrating iron-rich diet recommendations."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # ── Agents ────────────────────────────────────────────────────────────────

    @agent
    def diet_type_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["diet_type_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    @agent
    def allergy_filter_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["allergy_filter_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    @agent
    def condition_adjustment_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["condition_adjustment_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    @agent
    def pregnancy_lactation_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["pregnancy_lactation_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    @agent
    def absorption_optimizer_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["absorption_optimizer_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    @agent
    def medication_interaction_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["medication_interaction_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    # ── Tasks ────────────────────────────────────────────────────────────────

    @task
    def generate_diet_candidates_task(self) -> Task:
        return Task(config=self.tasks_config["generate_diet_candidates_task"],  # type: ignore[index]
                    )

    @task
    def filter_allergies_task(self) -> Task:
        return Task(
            config=self.tasks_config["filter_allergies_task"],  # type: ignore[index]
            context=[self.generate_diet_candidates_task()],
        )

    @task
    def adjust_for_conditions_task(self) -> Task:
        return Task(
            config=self.tasks_config["adjust_for_conditions_task"],  # type: ignore[index]
            context=[self.filter_allergies_task()],
        )

    @task
    def adjust_for_pregnancy_task(self) -> Task:
        return Task(
            config=self.tasks_config["adjust_for_pregnancy_task"],  # type: ignore[index]
            context=[self.adjust_for_conditions_task()],
        )

    @task
    def optimize_absorption_timing_task(self) -> Task:
        return Task(
            config=self.tasks_config["optimize_absorption_timing_task"],  # type: ignore[index]
            context=[self.adjust_for_pregnancy_task()],
        )

    @task
    def check_medication_interactions_task(self) -> Task:
        return Task(
            config=self.tasks_config["check_medication_interactions_task"],  # type: ignore[index]
            context=[self.optimize_absorption_timing_task()],
        )

    # ── Crew ────────────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        """Creates the Diet Planning Crew with sequential execution."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            cache=False,
            verbose=True,
        )
