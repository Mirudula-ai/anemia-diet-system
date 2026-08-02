import os
import litellm

os.environ["DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DROP_PARAMS"] = "True"

def _clean_dict(obj):
    if isinstance(obj, dict):
        obj.pop("cache_control", None)
        obj.pop("cache_breakpoint", None)
        for k, v in list(obj.items()):
            _clean_dict(v)
    elif isinstance(obj, list):
        for item in obj:
            _clean_dict(item)

_orig_completion = litellm.completion

def _patched_completion(*args, **kwargs):
    _clean_dict(kwargs)
    return _orig_completion(*args, **kwargs)

litellm.completion = _patched_completion
litellm.drop_params = True

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

@CrewBase
class ResearchCrew:
    """Crew that performs a deep medical and nutritional search for a given query."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # ── Agent ────────────────────────────────────────────────────────────────
    @agent
    def medical_deep_search_agent(self) -> Agent:
        model_name = os.getenv("LLM_MODEL", "groq/llama-3.1-8b-instant")
        llm = LLM(model=model_name, timeout=30, drop_params=True)
        return Agent(
            config=self.agents_config["medical_deep_search_agent"],  # type: ignore[index]
            llm=llm,
            tools=[SerperDevTool()],
            cache=False,
            max_rpm=1,
            verbose=True,
        )

    # ── Task ────────────────────────────────────────────────────────────────
    @task
    def research_query_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_query_task"],  # type: ignore[index]
        )

    # ── Crew ────────────────────────────────────────────────────────────────
    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            cache=False,
            verbose=True,
        )
