"""
i18n.py — Internationalisation (English / Tamil) for the Anemia Diet System.

Usage
-----
from anemia_diet_system.i18n import t

# In any screen function call:
st.markdown(t("login_title"))

Language is read from st.session_state["language"] (default "en").
Falls back to the English value if a key is missing in the active language.
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Translation dictionary
# ---------------------------------------------------------------------------
# Keys should be lowercase_with_underscores.
# Values must be plain strings (no f-strings — callers handle interpolation).
# Do NOT translate backend API values (diet_type, pregnancy_status, etc.).
# ---------------------------------------------------------------------------

TRANSLATIONS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ ENGLISH
    "en": {
        # App-wide
        "app_title":                       "Anemia Diet System",
        "app_subtitle":                    "Your personalised iron-rich nutrition guide.",
        "language_en":                     "English",
        "language_ta":                     "தமிழ்",
        "disclaimer":                      (
            "This plan is for nutritional guidance only and is not a substitute "
            "for professional medical advice."
        ),

        # Login screen
        "login_heading":                   "Anemia Diet System",
        "patient_id_label":                "Patient ID",
        "patient_id_placeholder":          "e.g. P001",
        "name_label":                      "Your Name",
        "name_placeholder":                "e.g. Asha",
        "continue_btn":                    "Continue →",
        "checking_record":                 "Checking your record…",

        # Intake screen
        "intake_heading":                  "Health Intake",
        "step_basics":                     "Basics",
        "step_health":                     "Health",
        "step_symptoms":                   "Symptoms",
        "step_review":                     "Review",
        "step1_heading":                   "Step 1 — Basic Information",
        "step2_heading":                   "Step 2 — Health Context",
        "step3_heading":                   "Step 3 — Symptoms",
        "step4_heading":                   "Step 4 — Review your information",
        "next_btn":                        "Next →",
        "back_btn":                        "← Back",
        "edit_btn":                        "Edit",
        "generate_plan_btn":               "🌿 Generate My Plan",
        "generating_plan_spinner":         (
            "Creating your personalised plan… (this may take 1–3 minutes)"
        ),

        # Step 1
        "diet_type_label":                 "Diet type",
        "diet_vegetarian":                 "Vegetarian",
        "diet_non_vegetarian":             "Non-vegetarian",
        "diet_vegan":                      "Vegan",
        "diet_eggetarian":                 "Eggetarian",
        "pregnancy_label":                 "Pregnancy / lactation status",
        "preg_not_pregnant":               "Not pregnant",
        "preg_pregnant":                   "Pregnant",
        "preg_lactating":                  "Lactating",
        "trimester_label":                 "Trimester",
        "trimester_1st":                   "1st",
        "trimester_2nd":                   "2nd",
        "trimester_3rd":                   "3rd",

        # Step 2
        "conditions_label":                "Existing health conditions (select all that apply)",
        "other_conditions_label":          "Other conditions (if any)",
        "other_conditions_placeholder":    "e.g. Sickle cell trait",
        "allergies_label":                 "Food allergies (comma-separated)",
        "allergies_placeholder":           "e.g. Nuts, Shellfish",
        "medications_label":               "Current medications (comma-separated)",
        "medications_placeholder":         "e.g. Metformin, Levothyroxine",

        # Step 3
        "symptoms_heading":                "Step 3 — Symptoms",
        "symptoms_chip_hint":              (
            "Tap a common symptom below to add it, or type freely in the box."
        ),
        "symptom_text_label":              (
            "How are you feeling? Describe any symptoms in your own words"
        ),
        "symptom_text_placeholder":        (
            "e.g. I feel tired all day and get dizzy when I stand up quickly."
        ),
        # Quick-symptom chip labels (displayed only; text appended as-is)
        "chip_fatigue":                    "Fatigue",
        "chip_dizziness":                  "Dizziness",
        "chip_pale_skin":                  "Pale skin",
        "chip_headache":                   "Headache",

        # Step 4 – review section titles
        "review_basics_title":             "🥗 Basics",
        "review_diet_type":                "Diet type:",
        "review_pregnancy":                "Pregnancy status:",
        "review_trimester":                "Trimester:",
        "review_health_title":             "🏥 Health Context",
        "review_conditions":               "Conditions:",
        "review_allergies":                "Allergies:",
        "review_medications":              "Medications:",
        "review_symptoms_title":           "💬 Symptoms",
        "none_label":                      "None",
        "none_described":                  "None described",

        # Plan screen
        "plan_empty_heading":              "📋 Your Diet Plan",
        "plan_empty_error":                "No plan available yet. Please complete the intake form first.",
        "plan_go_back_btn":                "← Go Back",
        "plan_heading":                    "🌿 Your Personalised Diet Plan",
        "plan_continue_btn":               "Continue to Home →",
        "safety_alert_heading":            "⚠️ Important Health Alert",
        "safety_alert_seek_care":          "Please seek medical care as soon as possible.",

        # Meal slot labels
        "slot_morning":                    "☀️ Morning",
        "slot_afternoon_evening":          "🌤️ Afternoon & Evening",
        "slot_night":                      "🌙 Night",
        "meal_have_with":                  "↑ Have with:",
        "meal_avoid_with":                 "↓ Avoid with:",

        # Home screen
        "home_welcome":                    "Welcome back",
        "home_subtitle":                   "Your personalised anemia diet support hub.",
        "view_plan_btn":                   "📋 View my current plan",
        "log_symptom_heading":             "💬 Log a Symptom",
        "log_symptom_desc":                (
            "How are you feeling today? Describe any new symptoms and we'll check "
            "if your plan needs updating."
        ),
        "log_symptom_btn":                 "Log Symptom →",
        "symptom_input_label":             "Describe your symptom",
        "symptom_input_placeholder":       (
            "e.g. I've been feeling very tired and short of breath."
        ),
        "evaluating_spinner":              "Evaluating your symptoms…",
        "symptom_logged_msg":              (
            "Your symptom has been logged. We'll keep monitoring your health."
        ),
        "submit_btn":                      "Submit",
        "cancel_btn":                      "Cancel",
        "feedback_heading":                "📝 Feedback on My Plan",
        "feedback_desc":                   (
            "Tell us what's working or not — we'll adjust your recommendations."
        ),
        "feedback_btn":                    "Give Feedback →",
        "feedback_input_label":            "Your feedback",
        "feedback_input_placeholder":      (
            "e.g. The lentil soup worked well, but I can't eat spinach — I'm allergic."
        ),
        "processing_feedback_spinner":     "Processing your feedback…",
        "feedback_response_label":         "Response:",
        "feedback_thankyou_msg":           (
            "Thank you! Your feedback has been recorded and your plan may be updated."
        ),

        # Error / connection messages
        "err_connection_refused":          (
            "Cannot connect to the server. "
            "Please make sure the backend is running at http://localhost:8000."
        ),
        "err_generic":                     "Something went wrong. Please try again in a moment.",
        "err_timeout_check":               (
            "The server is taking too long to respond. Please try again."
        ),
        "err_timeout_plan":                (
            "The plan generation is taking longer than expected. "
            "Please wait a moment and try again."
        ),
        "err_timeout_short":               "The server is taking too long. Please try again.",
        "err_unknown_screen":              "Unknown screen:",
        "return_to_login_btn":             "Return to Login",
    },

    # ------------------------------------------------------------------ TAMIL
    "ta": {
        # App-wide
        "app_title":                       "இரத்தசோகை உணவு அமைப்பு",
        "app_subtitle":                    "உங்களுக்கேற்ற இரும்புச் சத்து மிக்க உணவு வழிகாட்டி.",
        "language_en":                     "English",
        "language_ta":                     "தமிழ்",
        "disclaimer":                      (
            "இந்தத் திட்டம் உணவு வழிகாட்டுதலுக்கு மட்டுமே; மருத்துவ ஆலோசனையின் மாற்றாகாது."
        ),

        # Login screen
        "login_heading":                   "இரத்தசோகை உணவு அமைப்பு",
        "patient_id_label":                "நோயாளி அடையாள எண்",
        "patient_id_placeholder":          "எ.கா. P001",
        "name_label":                      "உங்கள் பெயர்",
        "name_placeholder":                "எ.கா. ஆஷா",
        "continue_btn":                    "தொடரவும் →",
        "checking_record":                 "உங்கள் பதிவை சரிபார்க்கிறோம்…",

        # Intake screen
        "intake_heading":                  "சுகாதர விவரம்",
        "step_basics":                     "அடிப்படை",
        "step_health":                     "ஆரோக்கியம்",
        "step_symptoms":                   "அறிகுறிகள்",
        "step_review":                     "மதிப்பாய்வு",
        "step1_heading":                   "படி 1 — அடிப்படை தகவல்",
        "step2_heading":                   "படி 2 — ஆரோக்கிய விவரங்கள்",
        "step3_heading":                   "படி 3 — அறிகுறிகள்",
        "step4_heading":                   "படி 4 — உங்கள் தகவலை மதிப்பாய்வு செய்யவும்",
        "next_btn":                        "அடுத்து →",
        "back_btn":                        "← பின்",
        "edit_btn":                        "திருத்து",
        "generate_plan_btn":               "🌿 என் திட்டத்தை உருவாக்கு",
        "generating_plan_spinner":         (
            "உங்கள் தனிப்பட்ட திட்டம் தயாரிக்கப்படுகிறது… (1–3 நிமிடங்கள் ஆகலாம்)"
        ),

        # Step 1
        "diet_type_label":                 "உணவு வகை",
        "diet_vegetarian":                 "சைவம்",
        "diet_non_vegetarian":             "அசைவம்",
        "diet_vegan":                      "வீகன்",
        "diet_eggetarian":                 "முட்டை சாப்பிடுவோர்",
        "pregnancy_label":                 "கர்ப்பம் / தாய்ப்பால் நிலை",
        "preg_not_pregnant":               "கர்ப்பமில்லை",
        "preg_pregnant":                   "கர்ப்பிணி",
        "preg_lactating":                  "தாய்ப்பால் கொடுக்கும் தாய்",
        "trimester_label":                 "மூன்று மாத கட்டம்",
        "trimester_1st":                   "1ம்",
        "trimester_2nd":                   "2ம்",
        "trimester_3rd":                   "3ம்",

        # Step 2
        "conditions_label":                "தற்போதுள்ள நோய்கள் (பொருந்துவனவற்றை தேர்ந்தெடுக்கவும்)",
        "other_conditions_label":          "வேறு நோய்கள் (ஏதேனும் இருப்பின்)",
        "other_conditions_placeholder":    "எ.கா. சிக்கிள் செல் பண்பு",
        "allergies_label":                 "உணவு ஒவ்வாமை (கால்புள்ளியால் பிரிக்கவும்)",
        "allergies_placeholder":           "எ.கா. கொட்டைகள், இறால்",
        "medications_label":               "தற்போதுள்ள மருந்துகள் (கால்புள்ளியால் பிரிக்கவும்)",
        "medications_placeholder":         "எ.கா. மெட்ஃபோர்மின், லெவோதைராக்ஸின்",

        # Step 3
        "symptoms_heading":                "படி 3 — அறிகுறிகள்",
        "symptoms_chip_hint":              (
            "பொதுவான அறிகுறியை கீழே தொட்டு சேர்க்கவும், அல்லது நேரடியாக தட்டச்சு செய்யவும்."
        ),
        "symptom_text_label":              "உங்கள் அறிகுறிகளை உங்கள் வார்த்தைகளில் விவரிக்கவும்",
        "symptom_text_placeholder":        (
            "எ.கா. நான் நாள் முழுவதும் களைப்பாக உணர்கிறேன், எழுந்திரிக்கும்போது தலைசுற்றுகிறது."
        ),
        # Quick-symptom chip labels
        "chip_fatigue":                    "களைப்பு",
        "chip_dizziness":                  "தலைசுற்றல்",
        "chip_pale_skin":                  "வெளிர் சருமம்",
        "chip_headache":                   "தலைவலி",

        # Step 4 – review
        "review_basics_title":             "🥗 அடிப்படை",
        "review_diet_type":                "உணவு வகை:",
        "review_pregnancy":                "கர்ப்ப நிலை:",
        "review_trimester":                "மூன்று மாத கட்டம்:",
        "review_health_title":             "🏥 ஆரோக்கிய விவரங்கள்",
        "review_conditions":               "நோய்கள்:",
        "review_allergies":                "ஒவ்வாமைகள்:",
        "review_medications":              "மருந்துகள்:",
        "review_symptoms_title":           "💬 அறிகுறிகள்",
        "none_label":                      "எதுவுமில்லை",
        "none_described":                  "எதுவும் விவரிக்கப்படவில்லை",

        # Plan screen
        "plan_empty_heading":              "📋 உங்கள் உணவுத் திட்டம்",
        "plan_empty_error":                "இன்னும் திட்டம் இல்லை. முதலில் விவர படிவத்தை நிரப்பவும்.",
        "plan_go_back_btn":                "← திரும்பு",
        "plan_heading":                    "🌿 உங்கள் தனிப்பட்ட உணவுத் திட்டம்",
        "plan_continue_btn":               "முகப்புக்குத் தொடரவும் →",
        "safety_alert_heading":            "⚠️ முக்கியமான உடல்நல எச்சரிக்கை",
        "safety_alert_seek_care":          "கூடிய விரைவில் மருத்துவ உதவியை நாடுங்கள்.",

        # Meal slot labels
        "slot_morning":                    "☀️ காலை",
        "slot_afternoon_evening":          "🌤️ பகல் & மாலை",
        "slot_night":                      "🌙 இரவு",
        "meal_have_with":                  "↑ இதனுடன் சாப்பிடவும்:",
        "meal_avoid_with":                 "↓ இதனுடன் தவிர்க்கவும்:",

        # Home screen
        "home_welcome":                    "மீண்டும் வரவேற்கிறோம்",
        "home_subtitle":                   "உங்கள் தனிப்பட்ட இரத்தசோகை உணவு ஆதரவு மையம்.",
        "view_plan_btn":                   "📋 என் திட்டத்தை காண்க",
        "log_symptom_heading":             "💬 அறிகுறியை பதிவு செய்य",
        "log_symptom_desc":                (
            "இன்று உங்களுக்கு எப்படி உள்ளது? புதிய அறிகுறிகளை விவரிக்கவும்; "
            "உங்கள் திட்டத்தை புதுப்பிக்க வேண்டுமா என்று சரிபார்க்கிறோம்."
        ),
        "log_symptom_btn":                 "அறிகுறி பதிவு →",
        "symptom_input_label":             "உங்கள் அறிகுறியை விவரிக்கவும்",
        "symptom_input_placeholder":       (
            "எ.கா. நான் மிகவும் களைப்பாகவும் மூச்சுத் திணறலாகவும் உணர்கிறேன்."
        ),
        "evaluating_spinner":              "உங்கள் அறிகுறிகளை மதிப்பிடுகிறோம்…",
        "symptom_logged_msg":              (
            "உங்கள் அறிகுறி பதிவு செய்யப்பட்டது. உங்கள் ஆரோக்கியத்தை தொடர்ந்து கண்காணிக்கிறோம்."
        ),
        "submit_btn":                      "சமர்ப்பி",
        "cancel_btn":                      "ரத்து செய்",
        "feedback_heading":                "📝 என் திட்டத்தில் கருத்து",
        "feedback_desc":                   (
            "என்ன வேலை செய்கிறது, என்ன செய்யவில்லை என்று சொல்லுங்கள் — "
            "உங்கள் பரிந்துரைகளை திருத்துகிறோம்."
        ),
        "feedback_btn":                    "கருத்து தெரிவி →",
        "feedback_input_label":            "உங்கள் கருத்து",
        "feedback_input_placeholder":      (
            "எ.கா. பருப்பு சூப் நன்றாக இருந்தது, ஆனால் கீரை என்னால் சாப்பிட முடியாது — ஒவ்வாமை."
        ),
        "processing_feedback_spinner":     "உங்கள் கருத்தை செயலாக்குகிறோம்…",
        "feedback_response_label":         "பதில்:",
        "feedback_thankyou_msg":           (
            "நன்றி! உங்கள் கருத்து பதிவு செய்யப்பட்டது; உங்கள் திட்டம் புதுப்பிக்கப்படலாம்."
        ),

        # Error / connection messages
        "err_connection_refused":          (
            "சேவையகத்துடன் இணைக்க முடியவில்லை. "
            "பின்தளம் http://localhost:8000 இல் இயங்குகிறதா என்று சரிபார்க்கவும்."
        ),
        "err_generic":                     "ஏதோ தவறு நடந்தது. சற்று நேரம் கழித்து மீண்டும் முயற்சிக்கவும்.",
        "err_timeout_check":               (
            "சேவையகம் பதிலளிக்க அதிக நேரம் எடுக்கிறது. மீண்டும் முயற்சிக்கவும்."
        ),
        "err_timeout_plan":                (
            "திட்டம் உருவாக்குவதற்கு எதிர்பார்த்ததை விட அதிக நேரம் ஆகிறது. "
            "கொஞ்சம் காத்திருந்து மீண்டும் முயற்சிக்கவும்."
        ),
        "err_timeout_short":               "சேவையகம் பதிலளிக்க அதிக நேரம் ஆகிறது. மீண்டும் முயற்சிக்கவும்.",
        "err_unknown_screen":              "தெரியாத திரை:",
        "return_to_login_btn":             "உள்நுழைவுக்கு திரும்பு",
    },
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def t(key: str) -> str:
    """
    Look up *key* in the active language (from st.session_state["language"],
    default "en").  Falls back to the English value if the key is missing in
    the requested language; returns the key itself if it is not found anywhere.
    """
    try:
        lang: str = st.session_state.get("language", "en")
        lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
        if key in lang_dict:
            return lang_dict[key]
        # Fallback to English
        return TRANSLATIONS["en"].get(key, key)
    except Exception:
        # Never crash on a translation lookup
        return TRANSLATIONS["en"].get(key, key)


from functools import lru_cache

@lru_cache(maxsize=256)
def _cached_google_translate(text: str, target_lang: str) -> str:
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="en", target=target_lang).translate(text)
    except Exception:
        return text

def translate_dynamic(text: str) -> str:
    """
    Translate dynamic AI-generated text to Tamil if language is set to 'ta'.
    Caches results in memory using lru_cache to keep the UI snappy and avoid API limits.
    Fails gracefully returning original text if translation fails.
    """
    if st.session_state.get("language") != "ta" or not text or not isinstance(text, str):
        return text
    return _cached_google_translate(text, "ta")

