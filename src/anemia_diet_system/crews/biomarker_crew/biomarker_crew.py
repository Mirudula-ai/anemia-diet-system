from __future__ import annotations

import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task

@CrewBase
class BiomarkerCrew:
    """Crew that checks for inflammation confounders and interprets lab biomarkers."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # ── Agents ────────────────────────────────────────────────────────────────

    @agent
    def inflammation_confounder_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["inflammation_confounder_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    @agent
    def biomarker_interpretation_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["biomarker_interpretation_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    # ── Tasks ────────────────────────────────────────────────────────────────

    @task
    def detect_inflammation_task(self) -> Task:
        return Task(
            config=self.tasks_config["detect_inflammation_task"],  # type: ignore[index]
        )

    @task
    def interpret_biomarkers_task(self) -> Task:
        return Task(
            config=self.tasks_config["interpret_biomarkers_task"],  # type: ignore[index]
            context=[self.detect_inflammation_task()],
        )

    # ── Crew ────────────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        """Creates the Biomarker Crew with sequential execution."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            cache=False,
            verbose=True,
        )
