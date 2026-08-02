from __future__ import annotations

import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task

@CrewBase
class FeedbackCrew:
    """Crew that parses patient feedback, tracks adherence, and revises the diet plan."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # ── Agents ────────────────────────────────────────────────────────────────

    @agent
    def feedback_intake_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["feedback_intake_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    @agent
    def adherence_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["adherence_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    @agent
    def plan_reviser_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        llm = LLM(model=model_name, timeout=30)
        return Agent(
            config=self.agents_config["plan_reviser_agent"],  # type: ignore[index]
            llm=llm,
            cache=False,
            verbose=True,
        )

    # ── Tasks ────────────────────────────────────────────────────────────────

    @task
    def parse_feedback_task(self) -> Task:
        return Task(
            config=self.tasks_config["parse_feedback_task"],  # type: ignore[index]
        )

    @task
    def track_adherence_task(self) -> Task:
        return Task(
            config=self.tasks_config["track_adherence_task"],  # type: ignore[index]
        )

    @task
    def revise_plan_task(self) -> Task:
        return Task(
            config=self.tasks_config["revise_plan_task"],  # type: ignore[index]
            context=[self.parse_feedback_task(), self.track_adherence_task()],
        )

    # ── Crew ────────────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        """Creates the Feedback & Adaptation Crew with sequential execution."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            cache=False,
            verbose=True,
        )
