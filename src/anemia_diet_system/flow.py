from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional, Union

from crewai.flow.flow import Flow, start

os.environ["DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DROP_PARAMS"] = "True"


# ── Python-based safety rule enforcer (no LLM needed) ────────────────────────
_EMERGENCY_KEYWORDS = [
    "faint", "fainting", "fainted", "syncope", "lost consciousness", "blacked out",
    "chest pain", "shortness of breath at rest", "out of breath sitting",
    "black stool", "tarry stool", "melena",
    "soaking through protection every hour", "soaking pad", "heavy bleeding hourly",
]
_URGENT_KEYWORDS = [
    "palpitation", "racing heart", "heart racing", "tachycardia",
]

def _python_safety_tier(symptoms: list[str]) -> Optional[str]:
    """Return EMERGENCY or URGENT if symptom text clearly matches known trigger keywords.
    Returns None if no hard rule matches (LLM tier should be used)."""
    combined = " ".join(str(s).lower() for s in symptoms)
    for kw in _EMERGENCY_KEYWORDS:
        if kw in combined:
            return "EMERGENCY"
    for kw in _URGENT_KEYWORDS:
        if kw in combined:
            return "URGENT"
    return None

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

if not hasattr(litellm, "input_callback") or not litellm.input_callback:
    litellm.input_callback = [_remove_cache_control]
elif _remove_cache_control not in litellm.input_callback:
    litellm.input_callback.append(_remove_cache_control)

from anemia_diet_system.crews.safety_crew.safety_crew import SafetyCrew
from anemia_diet_system.crews.diet_crew.diet_crew import DietPlanningCrew
from anemia_diet_system.crews.biomarker_crew.biomarker_crew import BiomarkerCrew
from anemia_diet_system.crews.feedback_crew.feedback_crew import FeedbackCrew
from anemia_diet_system.crews.synthesis_crew.synthesis_crew import SynthesisCrew
from anemia_diet_system.crews.research_crew.research_crew import ResearchCrew


def parse_json(raw: Any) -> Dict[str, Any]:
    """Helper function to parse JSON string outputs safely, handling markdown code fences."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raw = str(raw)
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}


class AnemiaFlow(Flow):
    """
    Event-driven orchestration flow for the Anemia & Iron-Deficiency Diet Recommendation System.
    
    Wires together six modular crews:
    1. SafetyCrew
    2. DietPlanningCrew
    3. BiomarkerCrew
    4. FeedbackCrew
    5. SynthesisCrew
    6. ResearchCrew
    """

    @start()
    def on_intake_complete(self, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Entry point 1: Initial patient intake processing.
        
        Input: PatientProfile-shaped dict (patient_id, diet_type, pregnancy_status,
               existing_conditions, allergies, current_medications, symptom_log, biomarkers)
        """
        if inputs is None:
            inputs = getattr(self, "state", {}) or {}
        if isinstance(inputs, str):
            inputs = parse_json(inputs)

        patient_id = inputs.get("patient_id", "unknown")
        print(f"\n[AnemiaFlow] >>> Starting initial intake processing for patient: '{patient_id}'")

        # ── Step a: Run SafetyCrew ──────────────────────────────────────────
        logged_symptoms = inputs.get("symptom_log") or inputs.get("logged_symptoms") or []
        is_pregnant = bool(
            inputs.get("is_pregnant")
            or (inputs.get("pregnancy_status") in ("pregnant", "lactating"))
        )
        life_stage = inputs.get("life_stage") or (
            "pregnant" if is_pregnant else "menstruating"
        )

        safety_payload = {
            "patient_id": patient_id,
            "logged_symptoms": logged_symptoms,
            "life_stage": life_stage,
            "is_pregnant": is_pregnant,
            "biomarkers": inputs.get("biomarkers") or {},
            "family_history_flags": inputs.get("family_history_flags") or [],
            "prior_monitor_flags_last_window": inputs.get("prior_monitor_flags_last_window") or False,
        }

        print(f"[AnemiaFlow] Step 1a: Running SafetyCrew...")
        safety_crew = SafetyCrew()
        safety_crew._patient_id = patient_id
        safety_result = safety_crew.crew().kickoff(
            inputs={"patient_input": json.dumps(safety_payload, default=str)}
        )
        safety_raw = safety_result.raw if hasattr(safety_result, "raw") else str(safety_result)
        safety_data = parse_json(safety_raw)
        print(f"[AnemiaFlow][DEBUG] safety_raw[:300] = {repr(safety_raw[:300])}")
        print(f"[AnemiaFlow][DEBUG] safety_data = {safety_data}")

        tier = safety_data.get("tier", "NONE").upper()
        safety_message = safety_data.get("rationale") or safety_data.get("safety_message", "")
        print(f"[AnemiaFlow][DEBUG] tier = {tier}")


        # ── Step b: Evaluate Safety Tier & Route ────────────────────────────
        if tier in ("URGENT", "EMERGENCY"):
            print(f"[AnemiaFlow] Step 1b: Safety tier is {tier}! Skipping DietPlanningCrew and BiomarkerCrew, but executing SynthesisCrew.")
            diet_plan = None
            biomarker_obs = {"status": "no_lab_data", "message": "No laboratory data available for interpretation."}
        else:
            print(f"[AnemiaFlow] Step 1b: Safety tier is {tier}. Proceeding with diet and biomarker evaluation.")

            # ── Step c & d: DietPlanningCrew & BiomarkerCrew ───────────────────
            diet_payload = {
                "patient_id": patient_id,
                "diet_type": inputs.get("diet_type", "vegetarian"),
                "allergies": inputs.get("allergies", []),
                "existing_conditions": inputs.get("existing_conditions", []),
                "pregnancy_status": inputs.get("pregnancy_status", "not_pregnant"),
                "trimester": inputs.get("trimester"),
                "current_medications": inputs.get("current_medications", []),
            }

            has_biomarkers = bool(inputs.get("biomarkers"))

            if has_biomarkers:
                print(f"[AnemiaFlow] Step 1c & 1d: Biomarkers present. Running DietPlanningCrew and BiomarkerCrew sequentially...")
                bio_payload = {
                    "patient_id": patient_id,
                    "biomarkers": inputs.get("biomarkers", {}),
                    "existing_conditions": inputs.get("existing_conditions", []),
                }

                def run_diet():
                    dc = DietPlanningCrew()
                    dc._patient_id = patient_id
                    res = dc.crew().kickoff(inputs={"patient_input": json.dumps(diet_payload, default=str)})
                    return parse_json(res.raw if hasattr(res, "raw") else str(res))

                def run_biomarker():
                    bc = BiomarkerCrew()
                    res = bc.crew().kickoff(inputs={"patient_input": json.dumps(bio_payload, default=str)})
                    return parse_json(res.raw if hasattr(res, "raw") else str(res))

                diet_data = run_diet()
                biomarker_obs = run_biomarker()
            else:
                print(f"[AnemiaFlow] Step 1c & 1d: No biomarkers provided. Skipping BiomarkerCrew.")
                biomarker_obs = {"status": "no_lab_data", "message": "No laboratory data available for interpretation."}

                dc = DietPlanningCrew()
                dc._patient_id = patient_id
                res = dc.crew().kickoff(inputs={"patient_input": json.dumps(diet_payload, default=str)})
                diet_data = parse_json(res.raw if hasattr(res, "raw") else str(res))

            diet_plan = diet_data.get("timed_foods", diet_data)
        print(f"[AnemiaFlow] Step 1e: Running SynthesisCrew...")

        synthesis_payload = {
            "patient_id": patient_id,
            "safety_tier": tier,
            "safety_message": safety_message,
            "diet_plan": diet_plan,
            "biomarker_observations": biomarker_obs,
            "symptom_log": logged_symptoms,
            "symptom_log_history": inputs.get("symptom_log_history") or [],
            "adherence_summary": inputs.get("adherence_summary") or [],
            "feedback_log": inputs.get("feedback_log") or [],
        }

        synthesis_crew = SynthesisCrew()
        syn_result = synthesis_crew.crew().kickoff(
            inputs={"patient_input": json.dumps(synthesis_payload, default=str)}
        )
        syn_raw = syn_result.raw if hasattr(syn_result, "raw") else str(syn_result)
        final_output = parse_json(syn_raw)

        print(f"[AnemiaFlow] Step 1f: Intake processing complete for patient '{patient_id}'.")
        return final_output

    def on_pdf_upload(self, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Entry point 2: Lab report PDF / new biomarker upload.
        
        Input: patient_id, new biomarkers dict, optional existing plan & safety context.
        """
        if inputs is None:
            inputs = getattr(self, "state", {}) or {}
        if isinstance(inputs, str):
            inputs = parse_json(inputs)

        patient_id = inputs.get("patient_id", "unknown")
        new_biomarkers = inputs.get("biomarkers") or inputs.get("new_biomarkers") or {}
        print(f"\n[AnemiaFlow] >>> PDF Lab Report Uploaded for patient '{patient_id}'")

        # Run BiomarkerCrew with new lab data
        bio_payload = {
            "patient_id": patient_id,
            "biomarkers": new_biomarkers,
            "existing_conditions": inputs.get("existing_conditions", []),
        }

        print(f"[AnemiaFlow] Step 2a: Running BiomarkerCrew with new lab report...")
        bc = BiomarkerCrew()
        bio_result = bc.crew().kickoff(inputs={"patient_input": json.dumps(bio_payload, default=str)})
        biomarker_obs = parse_json(bio_result.raw if hasattr(bio_result, "raw") else str(bio_result))

        # Re-run SynthesisCrew with updated biomarker observations
        print(f"[AnemiaFlow] Step 2b: Re-running SynthesisCrew with updated biomarker observations...")
        synthesis_payload = {
            "patient_id": patient_id,
            "safety_tier": inputs.get("safety_tier", "NONE"),
            "safety_message": inputs.get("safety_message", ""),
            "diet_plan": inputs.get("current_plan") or inputs.get("diet_plan"),
            "biomarker_observations": biomarker_obs,
            "symptom_log": inputs.get("symptom_log") or inputs.get("logged_symptoms") or [],
            "symptom_log_history": inputs.get("symptom_log_history") or [],
            "adherence_summary": inputs.get("adherence_summary") or [],
            "feedback_log": inputs.get("feedback_log") or [],
        }

        sc = SynthesisCrew()
        syn_result = sc.crew().kickoff(inputs={"patient_input": json.dumps(synthesis_payload, default=str)})
        syn_raw = syn_result.raw if hasattr(syn_result, "raw") else str(syn_result)
        return parse_json(syn_raw)

    def on_symptom_logged(self, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Entry point 3: Symptom log submission for monitoring / escalation.
        
        Input: patient_id, new symptom log entry, existing symptom_log history.
        """
        if inputs is None:
            inputs = getattr(self, "state", {}) or {}
        if isinstance(inputs, str):
            inputs = parse_json(inputs)

        patient_id = inputs.get("patient_id", "unknown")
        last_known_tier = (inputs.get("last_known_tier") or inputs.get("previous_tier") or "NONE").upper()
        print(f"\n[AnemiaFlow] >>> Symptom logged for patient '{patient_id}' (last known tier: {last_known_tier})")

        logged_symptoms = inputs.get("symptom_log") or inputs.get("logged_symptoms") or []
        is_pregnant = bool(
            inputs.get("is_pregnant")
            or (inputs.get("pregnancy_status") in ("pregnant", "lactating"))
        )
        life_stage = inputs.get("life_stage") or (
            "pregnant" if is_pregnant else "menstruating"
        )

        safety_payload = {
            "patient_id": patient_id,
            "logged_symptoms": logged_symptoms,
            "life_stage": life_stage,
            "is_pregnant": is_pregnant,
            "biomarkers": inputs.get("biomarkers", {}),
            "family_history_flags": inputs.get("family_history_flags", []),
            "prior_monitor_flags_last_window": inputs.get("prior_monitor_flags_last_window", False),
        }

        print(f"[AnemiaFlow] Step 3a: Re-running SafetyCrew...")
        safety_crew = SafetyCrew()
        safety_crew._patient_id = patient_id
        safety_result = safety_crew.crew().kickoff(
            inputs={"patient_input": json.dumps(safety_payload, default=str)}
        )
        safety_raw = safety_result.raw if hasattr(safety_result, "raw") else str(safety_result)
        safety_data = parse_json(safety_raw)

        new_tier = safety_data.get("tier", "NONE").upper()
        safety_message = safety_data.get("rationale") or safety_data.get("safety_message", "")

        tier_changed = new_tier != last_known_tier
        is_escalated = new_tier in ("URGENT", "EMERGENCY")

        if tier_changed or is_escalated:
            print(
                f"[AnemiaFlow] Step 3b: Safety tier changed ({last_known_tier} -> {new_tier})! "
                f"Re-running SynthesisCrew to update patient output."
            )
            synthesis_payload = {
                "patient_id": patient_id,
                "safety_tier": new_tier,
                "safety_message": safety_message,
                "diet_plan": inputs.get("current_plan") or inputs.get("diet_plan"),
                "biomarker_observations": inputs.get("biomarker_observations"),
                "symptom_log": logged_symptoms,
                "symptom_log_history": inputs.get("symptom_log_history") or [],
                "adherence_summary": inputs.get("adherence_summary") or [],
                "feedback_log": inputs.get("feedback_log") or [],
            }

            sc = SynthesisCrew()
            syn_result = sc.crew().kickoff(inputs={"patient_input": json.dumps(synthesis_payload, default=str)})
            syn_raw = syn_result.raw if hasattr(syn_result, "raw") else str(syn_result)
            return parse_json(syn_raw)

        print(
            f"[AnemiaFlow] Step 3b: Safety tier unchanged ({new_tier}). "
            f"Returning SafetyCrew evaluation result directly without re-running SynthesisCrew."
        )
        return safety_data

    def on_feedback_submitted(self, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Entry point 4: Patient feedback & meal adherence submission.
        
        Input: patient_id, raw_feedback_text, current_plan, logged_meals.
        """
        if inputs is None:
            inputs = getattr(self, "state", {}) or {}
        if isinstance(inputs, str):
            inputs = parse_json(inputs)

        patient_id = inputs.get("patient_id", "unknown")
        raw_feedback_text = inputs.get("raw_feedback_text", "")
        current_plan = inputs.get("current_plan", [])
        logged_meals = inputs.get("logged_meals", [])
        print(f"\n[AnemiaFlow] >>> Feedback submitted for patient '{patient_id}': '{raw_feedback_text}'")

        feedback_payload = {
            "patient_id": patient_id,
            "raw_feedback_text": raw_feedback_text,
            "current_plan": current_plan,
            "logged_meals": logged_meals,
        }

        print(f"[AnemiaFlow] Step 4a: Running FeedbackCrew...")
        fc = FeedbackCrew()
        fc_result = fc.crew().kickoff(inputs={"patient_input": json.dumps(feedback_payload, default=str)})

        adh_summary = inputs.get("adherence_summary") or []
        try:
            tasks = fc_result.tasks_output
            raw_revise = tasks[-1].raw if tasks else str(fc_result)
            if tasks and len(tasks) >= 2:
                adh_data = parse_json(tasks[1].raw)
                if "adherence_summary" in adh_data:
                    adh_summary = adh_data["adherence_summary"]
        except AttributeError:
            raw_revise = str(fc_result)

        feedback_data = parse_json(raw_revise)
        requires_allergy = feedback_data.get("requires_allergy_recheck", False)

        if requires_allergy:
            print(
                f"[AnemiaFlow] Step 4b: requires_allergy_recheck=True! "
                f"Re-running DietPlanningCrew and SynthesisCrew due to potential allergy/safety issue."
            )
            diet_payload = {
                "patient_id": patient_id,
                "diet_type": inputs.get("diet_type", "vegetarian"),
                "allergies": inputs.get("allergies", []),
                "existing_conditions": inputs.get("existing_conditions", []),
                "pregnancy_status": inputs.get("pregnancy_status", "not_pregnant"),
                "trimester": inputs.get("trimester"),
                "current_medications": inputs.get("current_medications", []),
            }

            dc = DietPlanningCrew()
            dc._patient_id = patient_id
            diet_res = dc.crew().kickoff(inputs={"patient_input": json.dumps(diet_payload, default=str)})
            diet_data = parse_json(diet_res.raw if hasattr(diet_res, "raw") else str(diet_res))
            new_plan = diet_data.get("timed_foods", diet_data)

            feedback_log = inputs.get("feedback_log") or ([raw_feedback_text] if raw_feedback_text else [])

            synthesis_payload = {
                "patient_id": patient_id,
                "safety_tier": inputs.get("safety_tier", "NONE"),
                "safety_message": inputs.get("safety_message", ""),
                "diet_plan": new_plan,
                "biomarker_observations": inputs.get("biomarker_observations"),
                "symptom_log": inputs.get("symptom_log") or inputs.get("logged_symptoms") or [],
                "symptom_log_history": inputs.get("symptom_log_history") or [],
                "adherence_summary": adh_summary,
                "feedback_log": feedback_log,
            }

            sc = SynthesisCrew()
            syn_res = sc.crew().kickoff(inputs={"patient_input": json.dumps(synthesis_payload, default=str)})
            syn_raw = syn_res.raw if hasattr(syn_res, "raw") else str(syn_res)
            return parse_json(syn_raw)

        print(
            f"[AnemiaFlow] Step 4b: requires_allergy_recheck=False. "
            f"Merging targeted plan revisions into existing plan without full crew re-runs."
        )
        revised_items = feedback_data.get("revised_plan", [])
        if not isinstance(revised_items, list):
            revised_items = [revised_items]

        merged_plan = list(current_plan)
        revised_names = {
            item.get("name"): item for item in revised_items if isinstance(item, dict) and "name" in item
        }

        updated_plan = []
        for orig_item in merged_plan:
            if isinstance(orig_item, dict) and orig_item.get("name") in revised_names:
                updated_plan.append(revised_names[orig_item["name"]])
            else:
                updated_plan.append(orig_item)

        existing_names = {item.get("name") for item in updated_plan if isinstance(item, dict)}
        for item in revised_items:
            if isinstance(item, dict) and item.get("name") not in existing_names:
                updated_plan.append(item)

        return {
            "revised_plan": updated_plan if updated_plan else revised_items,
            "requires_allergy_recheck": False,
            "note": feedback_data.get("note", ""),
        }

    def on_research_needed(self, inputs: Union[Dict[str, Any], str] = None) -> Dict[str, Any]:
        """
        Entry point 5: Standalone deep research query execution.
        
        Input: research_query (string or dict with "research_query" key).
        """
        if isinstance(inputs, dict):
            query = inputs.get("research_query", "")
        elif inputs is not None:
            query = str(inputs)
        else:
            query = ""

        print(f"\n[AnemiaFlow] >>> Deep research query requested: '{query}'")
        rc = ResearchCrew()
        res = rc.crew().kickoff(inputs={"research_query": query})
        raw = res.raw if hasattr(res, "raw") else str(res)
        return parse_json(raw)
