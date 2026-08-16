"""
main.py — FastAPI HTTP layer for the Anemia Diet System.

Wraps AnemiaFlow entry points behind REST endpoints with:
  - Pydantic request/response validation
  - JSON-file patient storage (via storage.py)
  - Per-endpoint error handling: 404 for unknown patients, 500 on crew failure
  - No modifications to flow.py or any crew module

Start the server:
    uv run uvicorn anemia_diet_system.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import os
import traceback
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv(override=False)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from anemia_diet_system.flow import AnemiaFlow
from anemia_diet_system import storage

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("anemia_diet_system.api")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Anemia & Iron-Deficiency Diet Recommendation API",
    description=(
        "Multi-agent AI system that provides personalised iron-rich diet plans, "
        "safety escalation alerts, and adaptive feedback processing."
    ),
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _require_patient(patient_id: str) -> Dict[str, Any]:
    """Load profile or raise 404 with a clear message."""
    profile = storage.load_patient_profile(patient_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Patient '{patient_id}' not found. "
                "Please call POST /intake first to register this patient."
            ),
        )
    return profile


def _flatten_plan(stored_plan: dict | None) -> list:
    """Extract a flat food-item list from a stored SynthesisCrew
    output, for endpoints that need current_plan as a plain list
    rather than the full synthesis dict."""
    if not stored_plan or not isinstance(stored_plan, dict):
        return []
    flat = []
    for slot in ("morning", "afternoon_evening", "night"):
        items = stored_plan.get(slot) or []
        if isinstance(items, list):
            flat.extend(items)
    return flat


def _run_flow(endpoint_name: str, method_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Call an AnemiaFlow method, returning the result dict or raising HTTP 500."""
    try:
        flow = AnemiaFlow()
        method = getattr(flow, method_name)
        return method(inputs)
    except Exception as exc:
        logger.error(
            "AnemiaFlow.%s failed for patient '%s':\n%s",
            method_name,
            inputs.get("patient_id", "?"),
            traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"[{endpoint_name}] Crew execution failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class IntakeRequest(BaseModel):
    patient_id: str = Field(..., description="Unique patient identifier")
    diet_type: str = Field("vegetarian", description="vegetarian / non-vegetarian / vegan / eggetarian")
    pregnancy_status: str = Field("not_pregnant", description="not_pregnant / pregnant / lactating")
    trimester: Optional[str] = Field(None, description="1st / 2nd / 3rd")
    existing_conditions: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    current_medications: List[str] = Field(default_factory=list)
    symptom_log: List[str] = Field(default_factory=list, description="Initial symptom descriptions")
    biomarkers: Dict[str, Any] = Field(default_factory=dict, description="Optional lab values, e.g. {'ferritin': 12}")



class LabReportRequest(BaseModel):
    patient_id: str
    biomarkers: Dict[str, Any] = Field(..., description="New lab values from the uploaded report")


class LogSymptomRequest(BaseModel):
    patient_id: str
    symptom_text: Any = Field(
        ...,
        description="A single symptom string or a list of symptom strings",
    )


class FeedbackRequest(BaseModel):
    patient_id: str
    raw_feedback_text: str = Field(..., description="Free-text feedback from the patient")
    logged_meals: List[Any] = Field(default_factory=list, description="Optional list of meals the patient actually ate")


class ProfileUpdateRequest(BaseModel):
    diet_type: Optional[str] = Field(None, description="vegetarian / non-vegetarian / vegan / eggetarian")
    pregnancy_status: Optional[str] = Field(None, description="not_pregnant / pregnant / lactating")
    trimester: Optional[str] = Field(None, description="1st / 2nd / 3rd")
    existing_conditions: Optional[List[str]] = Field(None)
    allergies: Optional[List[str]] = Field(None)
    current_medications: Optional[List[str]] = Field(None)
    cycle_start_date: Optional[str] = Field(None)
    average_cycle_length: Optional[int] = Field(None)


# Generic response — crews return heterogeneous JSON so we accept Any.
class FlowResponse(BaseModel):
    patient_id: str
    result: Any


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Meta"])
def health_check() -> Dict[str, str]:
    """Basic uptime probe."""
    return {"status": "ok"}


@app.post("/intake", response_model=FlowResponse, tags=["Patient"])
def intake(req: IntakeRequest) -> FlowResponse:
    """
    Register a new patient and run the full initial recommendation pipeline.

    Saves the profile and the resulting plan to persistent storage so
    subsequent endpoints can reference them without re-sending the full profile.
    """
    inputs: Dict[str, Any] = req.model_dump()

    # Persist profile before crew call so it exists even if the crew fails.
    storage.save_patient_profile(req.patient_id, inputs)

    # Seed the symptom log with any symptoms provided at intake.
    for symptom in req.symptom_log:
        storage.append_symptom_log(req.patient_id, symptom)

    result = _run_flow("POST /intake", "on_intake_complete", inputs)
    storage.save_current_plan(req.patient_id, result)

    logger.info("Intake complete for patient '%s'.", req.patient_id)
    return FlowResponse(patient_id=req.patient_id, result=result)


@app.post("/upload-lab-report", response_model=FlowResponse, tags=["Patient"])
def upload_lab_report(req: LabReportRequest) -> FlowResponse:
    """
    Submit new biomarker values from a lab report.

    Loads existing profile + current plan from storage, merges in the new
    biomarkers, and re-runs the synthesis pipeline.
    """
    profile = _require_patient(req.patient_id)
    current_plan = storage.load_current_plan(req.patient_id)
    symptom_logs = storage.load_symptom_logs(req.patient_id)

    inputs: Dict[str, Any] = {
        **profile,
        "patient_id": req.patient_id,
        "biomarkers": req.biomarkers,
        "current_plan": _flatten_plan(current_plan),
        "safety_tier": storage.get_last_known_safety_tier(req.patient_id),
        "safety_message": storage.get_last_known_safety_message(req.patient_id),
        "symptom_log": symptom_logs["symptom_log"],
        "symptom_log_history": symptom_logs["symptom_log_history"],
    }

    result = _run_flow("POST /upload-lab-report", "on_pdf_upload", inputs)
    storage.save_current_plan(req.patient_id, result)

    logger.info("Lab report processed for patient '%s'.", req.patient_id)
    return FlowResponse(patient_id=req.patient_id, result=result)


@app.post("/log-symptom", response_model=FlowResponse, tags=["Patient"])
def log_symptom(req: LogSymptomRequest) -> FlowResponse:
    """
    Log one or more new symptoms and trigger a safety re-evaluation.

    Appends to the patient's symptom history, then runs the symptom-logged
    pipeline. If the safety tier changes, the synthesis pipeline is also
    re-run and the new plan is persisted.
    """
    _require_patient(req.patient_id)

    # Normalise to list
    new_symptoms: List[str] = (
        req.symptom_text if isinstance(req.symptom_text, list) else [str(req.symptom_text)]
    )
    for s in new_symptoms:
        storage.append_symptom_log(req.patient_id, s)

    symptom_logs = storage.load_symptom_logs(req.patient_id)
    current_plan = storage.load_current_plan(req.patient_id)
    profile = storage.load_patient_profile(req.patient_id)

    inputs: Dict[str, Any] = {
        "patient_id": req.patient_id,
        "symptom_log": new_symptoms,
        "symptom_log_history": symptom_logs["symptom_log_history"],
        "last_known_tier": storage.get_last_known_safety_tier(req.patient_id),
        "current_plan": current_plan,
        # Pass life-stage context from profile
        "life_stage": profile.get("life_stage") or (
            "pregnant"
            if profile.get("pregnancy_status") in ("pregnant", "lactating")
            else "menstruating"
        ),
        "is_pregnant": profile.get("pregnancy_status") in ("pregnant", "lactating"),
        "biomarkers": profile.get("biomarkers", {}),
        "family_history_flags": profile.get("family_history_flags", []),
        "prior_monitor_flags_last_window": profile.get("prior_monitor_flags_last_window", False),
    }

    result = _run_flow("POST /log-symptom", "on_symptom_logged", inputs)

    # Only overwrite the plan when a new synthesis output was produced
    # (identified by the presence of content_mode, a SynthesisCrew key).
    if isinstance(result, dict) and "content_mode" in result:
        storage.save_current_plan(req.patient_id, result)

    logger.info(
        "Symptom logged for patient '%s'. Symptoms: %s",
        req.patient_id,
        new_symptoms,
    )
    return FlowResponse(patient_id=req.patient_id, result=result)


@app.post("/feedback", response_model=FlowResponse, tags=["Patient"])
def submit_feedback(req: FeedbackRequest) -> FlowResponse:
    """
    Submit patient feedback about the current plan.

    Loads the current_plan from storage automatically — the caller does
    not need to re-send the plan. Appends the feedback to the log and
    persists any resulting plan update.
    """
    _require_patient(req.patient_id)
    current_plan = storage.load_current_plan(req.patient_id)
    profile = storage.load_patient_profile(req.patient_id)
    feedback_log = storage.load_feedback_log(req.patient_id)

    inputs: Dict[str, Any] = {
        **profile,
        "patient_id": req.patient_id,
        "raw_feedback_text": req.raw_feedback_text,
        "current_plan": _flatten_plan(current_plan),
        "logged_meals": req.logged_meals,
        "feedback_log": feedback_log,
        "safety_tier": storage.get_last_known_safety_tier(req.patient_id),
    }

    result = _run_flow("POST /feedback", "on_feedback_submitted", inputs)

    # Append the raw text to the log after a successful crew run.
    storage.append_feedback_log(req.patient_id, req.raw_feedback_text)

    # Persist an updated plan when the feedback forced a full re-synthesis.
    if isinstance(result, dict) and "content_mode" in result:
        storage.save_current_plan(req.patient_id, result)
    elif isinstance(result, dict) and "revised_plan" in result:
        # Partial revision — merge back into the stored plan structure.
        stored = storage.load_current_plan(req.patient_id) or {}
        stored["revised_plan"] = result.get("revised_plan")
        stored["note"] = result.get("note", "")
        storage.save_current_plan(req.patient_id, stored)

    logger.info("Feedback processed for patient '%s'.", req.patient_id)
    return FlowResponse(patient_id=req.patient_id, result=result)


@app.get("/patient/{patient_id}/plan", response_model=FlowResponse, tags=["Patient"])
def get_current_plan(patient_id: str) -> FlowResponse:
    """
    Retrieve the patient's most-recently generated plan without running any crew.

    Intended for the UI's "what's my plan right now?" fetch.
    """
    _require_patient(patient_id)
    plan = storage.load_current_plan(patient_id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No plan found for patient '{patient_id}'. "
                "A plan is generated by POST /intake or updated by "
                "POST /upload-lab-report, /log-symptom, or /feedback."
            ),
        )
    return FlowResponse(patient_id=patient_id, result=plan)


@app.get("/patient/{patient_id}/profile", response_model=FlowResponse, tags=["Patient"])
def get_patient_profile(patient_id: str) -> FlowResponse:
    """
    Retrieve the full stored profile for a patient. 404 if patient doesn't exist.
    """
    profile = _require_patient(patient_id)
    return FlowResponse(patient_id=patient_id, result=profile)


@app.put("/patient/{patient_id}/profile", response_model=FlowResponse, tags=["Patient"])
def update_patient_profile(patient_id: str, req: ProfileUpdateRequest) -> FlowResponse:
    """
    Update selected profile fields without full replacement.
    Does NOT automatically regenerate the diet plan.
    Includes 'plan_may_need_update' boolean flag in response.
    """
    _require_patient(patient_id)
    updates = req.model_dump(exclude_unset=True)

    plan_affecting_fields = {"diet_type", "allergies", "existing_conditions", "pregnancy_status", "trimester"}
    plan_may_need_update = any(k in plan_affecting_fields for k in updates.keys())

    try:
        updated_profile = storage.update_patient_profile(patient_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = {
        **updated_profile,
        "plan_may_need_update": plan_may_need_update,
    }
    return FlowResponse(patient_id=patient_id, result=result)


# ---------------------------------------------------------------------------
# CLI entry point kept for `uv run anemia-diet`
# ---------------------------------------------------------------------------
def run() -> None:
    """Legacy CLI runner (kept for pyproject.toml script compatibility)."""
    import uvicorn
    uvicorn.run("anemia_diet_system.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
