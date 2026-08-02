"""
Patient profile model — shared across all crews in the anemia diet system.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SymptomEntry(BaseModel):
    """A single symptom log entry with date."""
    date: date
    symptom: str
    severity: Optional[Literal["mild", "moderate", "severe"]] = None
    notes: Optional[str] = None


class FeedbackEntry(BaseModel):
    """A single feedback entry with date."""
    date: date
    feedback: str
    source: Optional[str] = None  # e.g. "user", "clinician"


class Biomarker(BaseModel):
    """A single lab/biomarker value."""
    value: float
    unit: Optional[str] = None
    flag: Optional[Literal["low", "normal", "high"]] = None
    date: Optional[date] = None


class PatientProfile(BaseModel):
    """
    Core patient profile model reused by every crew in the anemia diet system.
    All fields are optional beyond patient_id so that partial profiles are valid
    at intake and filled incrementally as more information becomes available.
    """

    # ── Identity ─────────────────────────────────────────────────────────────
    patient_id: str = Field(..., description="Unique patient identifier")
    preferred_language: str = Field(default="en", description="ISO 639-1 language code")

    # ── Demographics ──────────────────────────────────────────────────────────
    age: Optional[int] = Field(default=None, ge=0, le=150)
    sex: Optional[Literal["female", "male", "intersex", "prefer_not_to_say"]] = None

    # ── Diet & Lifestyle ──────────────────────────────────────────────────────
    diet_type: Optional[str] = Field(
        default=None,
        description="e.g. omnivore, vegetarian, vegan, pescatarian",
    )

    # ── Reproductive / Life-Stage ─────────────────────────────────────────────
    pregnancy_status: Optional[bool] = Field(
        default=False,
        description="True if currently pregnant",
    )
    trimester: Optional[Literal[1, 2, 3]] = Field(
        default=None,
        description="Current trimester (1, 2, or 3) if pregnant",
    )
    life_stage: Optional[str] = Field(
        default=None,
        description=(
            "Descriptive life-stage label used by safety crew. "
            "Examples: menstruating, pregnant, menopausal, PCOS, thyroid-flagged"
        ),
    )

    # ── Medical History ───────────────────────────────────────────────────────
    existing_conditions: list[str] = Field(
        default_factory=list,
        description="Open-ended list of existing medical conditions",
    )
    allergies: list[str] = Field(
        default_factory=list,
        description="Food, medication, or environmental allergies",
    )
    current_medications: list[str] = Field(
        default_factory=list,
        description="Current medications including supplements",
    )
    family_history_flags: list[str] = Field(
        default_factory=list,
        description="Relevant family history flags e.g. thalassemia, haemoglobinopathy",
    )

    # ── Lab / Biomarker Data ──────────────────────────────────────────────────
    biomarkers: dict[str, Biomarker] = Field(
        default_factory=dict,
        description="Dict of biomarker name -> Biomarker. E.g. {'MCV': Biomarker(value=68, flag='low')}",
    )

    # ── Logs ──────────────────────────────────────────────────────────────────
    symptom_log: list[SymptomEntry] = Field(
        default_factory=list,
        description="Dated symptom entries in chronological order",
    )
    feedback_log: list[FeedbackEntry] = Field(
        default_factory=list,
        description="Dated feedback entries from patient or clinician",
    )

    # ── Safety Crew Context ───────────────────────────────────────────────────
    logged_symptoms: list[str] = Field(
        default_factory=list,
        description="Free-text symptom strings passed directly to the safety crew",
    )
    tagged_symptoms: list[dict] = Field(
        default_factory=list,
        description="Pre-tagged symptom dicts if tagging was done upstream",
    )
    prior_monitor_flags_last_window: bool = Field(
        default=False,
        description="True if a MONITOR-tier flag fired in the prior 7-day window",
    )
