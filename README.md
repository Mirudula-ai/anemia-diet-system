# Anemia Diet System — Safety Crew

A multi-agent system for iron-deficiency anaemia diet recommendations, built with [CrewAI](https://crewai.com).

## Project Structure

```
src/anemia_diet_system/
├── main.py                          # Entry point
├── flow.py                          # AnemiaFlow (Safety Crew only; extensible)
├── crews/
│   └── safety_crew/
│       ├── config/
│       │   ├── agents.yaml          # Symptom Tagger + Safety Escalation Evaluator
│       │   └── tasks.yaml           # Tagging task + Tier evaluation task
│       └── safety_crew.py           # SafetyCrew @CrewBase class
├── tools/
│   └── safety_audit_logger.py       # Append-only JSONL audit logger
└── models/
    └── patient_profile.py           # PatientProfile Pydantic model (shared)
tests/
└── test_safety_crew.py              # 15 golden test cases
data/
└── patients/<patient_id>/logs/      # Auto-created audit log directory
```

## Setup

```bash
# 1. Install uv (if not present)
#    Windows: irm https://astral.sh/uv/install.ps1 | iex

# 2. Copy and configure environment variables
cp .env.example .env
# Edit .env — set OPENAI_API_KEY (or your preferred LLM provider key)

# 3. Sync dependencies
uv sync

# 4. Run the demo
uv run python src/anemia_diet_system/main.py
```

## Safety Crew Tiers

| Tier | Description |
|------|-------------|
| `EMERGENCY` | Immediate medical attention required (e.g., fainting, chest pain, heavy bleeding) |
| `URGENT` | See a doctor within 24–48 hours |
| `MONITOR` | Watch and track; may escalate if pattern persists |
| `NONE` | No safety concerns at this time |

> **Escalation persistence rule:** If a MONITOR-tier flag fired in the prior 7-day window,
> a new MONITOR trigger automatically escalates to URGENT.

## Running Tests

```bash
# Direct script
uv run python tests/test_safety_crew.py

# Via pytest
uv run pytest tests/test_safety_crew.py -v
```

## Adding New Crews

Extend `flow.py` by adding `@listen`/`@router` branches after `run_safety_crew`.
Each new crew follows the same `@CrewBase` pattern in `src/anemia_diet_system/crews/`.

## Notes

- **Do not adjust test expected tiers** without approval — they come from the approved safety rule design.
- Audit logs are append-only JSONL; no free-text patient notes are written (redacted to symptom names and severities only).
- `PatientProfile` in `models/patient_profile.py` is the shared data contract across all crews.
