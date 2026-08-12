"""
streamlit_app.py — Clinical-grade Light Glassmorphism Streamlit frontend for Anemia Diet System.

Connects to FastAPI backend running at http://localhost:8000.
Start backend separately:
    uv run uvicorn anemia_diet_system.main:app --reload --port 8000
Start frontend:
    uv run streamlit run src/anemia_diet_system/streamlit_app.py
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager

import requests
import streamlit as st

from anemia_diet_system.i18n import t, translate_dynamic

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_BASE = "http://localhost:8000"
INTAKE_TIMEOUT = 240
DEFAULT_TIMEOUT = 30

COMMON_CONDITIONS = [
    "Diabetes",
    "Thyroid disorder",
    "PCOS",
    "CKD",
    "Celiac disease",
    "IBD",
]

QUICK_SYMPTOM_KEYS = [
    ("chip_fatigue",   "Fatigue"),
    ("chip_dizziness", "Dizziness"),
    ("chip_pale_skin", "Pale skin"),
    ("chip_headache",  "Headache"),
]

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Anemia Diet System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Global CSS — Light Clean Clinical Theme & Specific Chip State Styles
# ---------------------------------------------------------------------------
GLASS_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  /* Base Light Styling */
  html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 17px;
    color: #1A1A2E;
  }

  /* Light Lavender-to-White Soft Gradient Background */
  .stApp {
    background: linear-gradient(135deg, #E8E4F3 0%, #F4F1FA 45%, #FFFFFF 100%);
    min-height: 100vh;
    position: relative;
    overflow-x: hidden;
  }

  /* Soft Background Blobs */
  .blob-mint {
    position: fixed;
    top: -120px;
    left: -140px;
    width: 600px;
    height: 600px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(167, 243, 208, 0.55) 0%, rgba(167, 243, 208, 0) 70%);
    filter: blur(90px);
    pointer-events: none;
    z-index: 0;
    transition: transform 0.2s cubic-bezier(0.1, 0.5, 0.1, 1);
  }

  .blob-peach {
    position: fixed;
    bottom: -140px;
    right: -120px;
    width: 580px;
    height: 580px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(253, 186, 116, 0.50) 0%, rgba(253, 186, 116, 0) 70%);
    filter: blur(90px);
    pointer-events: none;
    z-index: 0;
    transition: transform 0.2s cubic-bezier(0.1, 0.5, 0.1, 1);
  }

  .blob-lavender {
    position: fixed;
    top: 35%;
    left: 40%;
    width: 500px;
    height: 500px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(196, 181, 253, 0.45) 0%, rgba(196, 181, 253, 0) 70%);
    filter: blur(90px);
    pointer-events: none;
    z-index: 0;
    transition: transform 0.2s cubic-bezier(0.1, 0.5, 0.1, 1);
  }

  /* Minimal Translucent Light Top Header Bar */
  .app-header-bar {
    position: sticky;
    top: 0;
    z-index: 999;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 2rem;
    background: rgba(255, 255, 255, 0.65);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.8);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
    margin-bottom: 1.5rem;
  }
  .app-brand {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    font-weight: 700;
    font-size: 1.15rem;
    color: #1A1A2E;
    letter-spacing: -0.01em;
  }
  .app-brand-icon {
    width: 28px;
    height: 28px;
    fill: #0F766E;
  }

  .main-content-wrap {
    max-width: 1000px;
    margin: 0 auto;
    padding: 0 1rem 2rem 1rem;
    position: relative;
    z-index: 1;
  }

  /* 3D Glass Cards — applied to Streamlit native containers via data attrs */
  /* glass-card: standard card */
  [data-testid="stVerticalBlockBorderWrapper"].gc-card > div > [data-testid="stVerticalBlock"],
  [data-testid="stVerticalBlockBorderWrapper"].gc-card {
    background: rgba(255, 255, 255, 0.60) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border-radius: 20px !important;
    border: 1.5px solid rgba(255, 255, 255, 0.8) !important;
    box-shadow: 0 12px 36px rgba(31, 38, 135, 0.08) !important;
    padding: 2.25rem !important;
    margin-bottom: 1.75rem !important;
    position: relative;
    z-index: 1;
    transition: transform 0.15s ease-out, box-shadow 0.15s ease-out !important;
  }
  [data-testid="stVerticalBlockBorderWrapper"].gc-card:hover {
    transform: perspective(1000px) rotateX(1.5deg) rotateY(-1.5deg) translateY(-3px) !important;
    box-shadow: 0 18px 42px rgba(31, 38, 135, 0.13) !important;
  }

  /* glass-card-alert: alert/safety card */
  [data-testid="stVerticalBlockBorderWrapper"].gc-alert > div > [data-testid="stVerticalBlock"],
  [data-testid="stVerticalBlockBorderWrapper"].gc-alert {
    background: rgba(254, 242, 242, 0.75) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border-radius: 20px !important;
    border: 1.5px solid rgba(220, 38, 38, 0.3) !important;
    box-shadow: 0 12px 36px rgba(220, 38, 38, 0.12) !important;
    padding: 2.25rem !important;
    margin-bottom: 1.75rem !important;
    position: relative;
    z-index: 1;
    transition: transform 0.15s ease-out, box-shadow 0.15s ease-out !important;
  }
  [data-testid="stVerticalBlockBorderWrapper"].gc-alert:hover {
    transform: perspective(1000px) rotateX(1.5deg) rotateY(-1.5deg) translateY(-3px) !important;
    box-shadow: 0 18px 42px rgba(220, 38, 38, 0.18) !important;
  }

  /* glass-card-info: compact info card */
  [data-testid="stVerticalBlockBorderWrapper"].gc-info > div > [data-testid="stVerticalBlock"],
  [data-testid="stVerticalBlockBorderWrapper"].gc-info {
    background: rgba(255, 255, 255, 0.50) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border-radius: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.7) !important;
    box-shadow: 0 6px 20px rgba(31, 38, 135, 0.05) !important;
    padding: 1.3rem 1.6rem !important;
    margin-bottom: 1.25rem !important;
    position: relative;
    z-index: 1;
    transition: transform 0.15s ease-out, box-shadow 0.15s ease-out !important;
  }
  [data-testid="stVerticalBlockBorderWrapper"].gc-info:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 24px rgba(31, 38, 135, 0.08) !important;
  }

  /* Helper: inject class onto the nearest stVerticalBlockBorderWrapper */
  .gc-inject-card + div [data-testid="stVerticalBlockBorderWrapper"] { display: none; }

  /* Old-style .glass-card class kept for any inline HTML blocks */
  .glass-card {
    background: rgba(255, 255, 255, 0.60);
    backdrop-filter: blur(20px);
    border-radius: 20px;
    border: 1.5px solid rgba(255, 255, 255, 0.8);
    box-shadow: 0 12px 36px rgba(31, 38, 135, 0.08);
    padding: 2.25rem;
    margin-bottom: 1.75rem;
  }
  .glass-card-alert {
    background: rgba(254, 242, 242, 0.75);
    backdrop-filter: blur(20px);
    border-radius: 20px;
    border: 1.5px solid rgba(220, 38, 38, 0.3);
    box-shadow: 0 12px 36px rgba(220, 38, 38, 0.12);
    padding: 2.25rem;
    margin-bottom: 1.75rem;
  }
  .glass-card-info {
    background: rgba(255, 255, 255, 0.50);
    backdrop-filter: blur(12px);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.7);
    box-shadow: 0 6px 20px rgba(31, 38, 135, 0.05);
    padding: 1.3rem 1.6rem;
    margin-bottom: 1.25rem;
  }

  /* Typography */
  h1 { font-size: 2.2rem !important; font-weight: 800 !important; color: #0F766E !important; letter-spacing: -0.02em !important; }
  h2 { font-size: 1.7rem !important; font-weight: 700 !important; color: #1A1A2E !important; }
  h3 { font-size: 1.3rem !important; font-weight: 700 !important; color: #0F766E !important; }
  h4 { font-size: 1.15rem !important; font-weight: 600 !important; color: #334155 !important; }

  /* Hero Panel */
  .hero-panel {
    padding: 2rem 1.5rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
    height: 100%;
  }
  .hero-title-large {
    font-size: 3rem;
    font-weight: 800;
    color: #0F766E;
    line-height: 1.15;
    margin-bottom: 0.75rem;
    letter-spacing: -0.02em;
  }
  .hero-tagline {
    font-size: 1.25rem;
    color: #475569;
    font-weight: 500;
    margin-bottom: 2rem;
    line-height: 1.5;
  }
  .trust-list { list-style: none; padding: 0; margin: 0; }
  .trust-item {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    font-size: 1.05rem;
    color: #334155;
    font-weight: 600;
    margin-bottom: 0.9rem;
    background: rgba(255, 255, 255, 0.40);
    padding: 0.75rem 1.1rem;
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(8px);
  }

  /* Micro-interactions: Primary Buttons & Inputs */
  .stButton > button {
    border-radius: 12px !important;
    background: #0F766E !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    padding: 0.7rem 1.8rem !important;
    border: none !important;
    min-height: 48px !important;
    width: 100% !important;
    transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow: 0 4px 14px rgba(15, 118, 110, 0.25) !important;
  }
  .stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 22px rgba(15, 118, 110, 0.38) !important;
    background: #0d655e !important;
  }
  .stButton > button:active {
    transform: scale(0.97) translateY(0px) !important;
    box-shadow: 0 2px 6px rgba(15, 118, 110, 0.4) !important;
  }
  .stButton > button:disabled {
    background: #CBD5E1 !important;
    color: #94A3B8 !important;
    cursor: not-allowed !important;
    transform: none !important;
    box-shadow: none !important;
  }

  /* Glowing Teal Focus Ring for Inputs */
  .stTextInput > div > div > input:focus,
  .stTextArea > div > div > textarea:focus {
    border-color: #0F766E !important;
    box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.25) !important;
    outline: none !important;
  }

  /* 
   * Distinct Button States for Options (Issue 3 & Issue 4 Fix)
   * Target container wrapper classes `.chip-unselected` and `.chip-selected`
   */
  .chip-unselected > div.stButton > button {
    background: #FFFFFF !important;
    color: #0F766E !important;
    border: 1.5px solid #0F766E !important;
    box-shadow: none !important;
    font-weight: 600 !important;
  }
  .chip-unselected > div.stButton > button:hover {
    background: rgba(15, 118, 110, 0.08) !important;
    color: #0D655E !important;
    border-color: #0D655E !important;
    transform: translateY(-1px) !important;
  }

  .chip-selected > div.stButton > button {
    background: #0F766E !important;
    color: #FFFFFF !important;
    border: 1.5px solid #0F766E !important;
    box-shadow: 0 4px 14px rgba(15, 118, 110, 0.35) !important;
    font-weight: 700 !important;
  }
  .chip-selected > div.stButton > button:hover {
    background: #0D655E !important;
    color: #FFFFFF !important;
    border-color: #0D655E !important;
    transform: translateY(-1px) !important;
  }

  /* Step Bar */
  .step-bar { display: flex; justify-content: center; align-items: center; gap: 0; margin-bottom: 1.75rem; }
  .step-item { display: flex; align-items: center; gap: 0; }
  .step-circle {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.95rem;
    border: 2px solid #CBD5E1;
    background: #FFF;
    color: #94A3B8;
    transition: all 0.25s ease;
  }
  .step-circle.active { background: #0F766E; border-color: #0F766E; color: #FFF; box-shadow: 0 0 0 4px rgba(15,118,110,0.18); }
  .step-circle.done { background: #D1FAE5; border-color: #0F766E; color: #0F766E; }
  .step-label { font-size: 0.82rem; font-weight: 500; color: #64748B; margin-top: 5px; text-align: center; width: 75px; }
  .step-label.active { color: #0F766E; font-weight: 700; }
  .step-connector { width: 45px; height: 3px; background: #E2E8F0; margin: 0 2px 20px 2px; }
  .step-connector.done { background: #0F766E; }

  /* Meal Slots */
  .meal-slot-section { border-radius: 14px; padding: 1.1rem 1.3rem; margin-bottom: 1.1rem; }
  .meal-slot-morning { background: rgba(20, 184, 166, 0.08); border-left: 4px solid #0F766E; }
  .meal-slot-afternoon { background: rgba(245, 158, 11, 0.08); border-left: 4px solid #D97706; }
  .meal-slot-night { background: rgba(99, 102, 241, 0.08); border-left: 4px solid #4F46E5; }
  .meal-slot-label { font-size: 0.88rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; color: #0F766E; margin-bottom: 0.5rem; }
  .meal-item { font-size: 1.05rem; font-weight: 600; color: #1A1A2E; padding: 0.35rem 0; border-bottom: 1px solid rgba(15,118,110,0.08); }
  .meal-sub { font-size: 0.88rem; color: #475569; padding-left: 0.75rem; font-weight: 400; }

  .disclaimer { font-size: 0.88rem; color: #64748B; font-style: italic; text-align: center; margin-top: 1.5rem; }
  .error-box { background: rgba(254, 242, 242, 0.9); border: 1.5px solid rgba(220, 38, 38, 0.35); border-radius: 12px; padding: 1rem 1.25rem; color: #991B1B; margin-bottom: 1rem; font-weight: 500; }
  .success-box { background: rgba(240, 253, 244, 0.9); border: 1.5px solid rgba(15, 118, 110, 0.3); border-radius: 12px; padding: 1rem 1.25rem; color: #065F46; margin-bottom: 1rem; font-weight: 500; }

  label { font-size: 1rem !important; font-weight: 600 !important; color: #334155 !important; }
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }
  header { visibility: hidden; }
</style>

<!-- Parallax Mouse Movement Script -->
<script>
  document.addEventListener('mousemove', function(e) {
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    const dx = (e.clientX - cx) / cx;
    const dy = (e.clientY - cy) / cy;
    
    const b1 = document.querySelector('.blob-mint');
    const b2 = document.querySelector('.blob-peach');
    const b3 = document.querySelector('.blob-lavender');
    
    if (b1) b1.style.transform = `translate(${dx * 12}px, ${dy * 12}px)`;
    if (b2) b2.style.transform = `translate(${dx * -15}px, ${dy * -15}px)`;
    if (b3) b3.style.transform = `translate(${dx * 8}px, ${dy * 8}px)`;
  });
</script>
"""

st.markdown(GLASS_CSS, unsafe_allow_html=True)
st.markdown('<div class="blob-mint"></div><div class="blob-peach"></div><div class="blob-lavender"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------
def _init_state() -> None:
    defaults = {
        "current_screen": "login",
        "patient_id": "",
        "patient_name": "",
        "intake_step": 1,
        "language": "en",
        "f_diet_type": "vegetarian",
        "f_pregnancy_status": "not_pregnant",
        "f_trimester": "1st",
        "f_conditions": [],
        "f_conditions_other": "",
        "f_allergies": "",
        "f_medications": "",
        "f_symptom_text": "",
        "current_plan": None,
        "show_symptom_panel": False,
        "show_feedback_panel": False,
        "symptom_confirm_msg": "",
        "feedback_confirm_msg": "",
        "sym_draft": "",
        "feed_draft": "",
        "api_error": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def _connection_refused_msg() -> str:
    return t("err_connection_refused")

def _generic_error_msg() -> str:
    return t("err_generic")

def api_check_patient(patient_id: str) -> str:
    try:
        resp = requests.get(f"{API_BASE}/patient/{patient_id}/plan", timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            return "found"
        if resp.status_code == 404:
            return "not_found"
        return f"error:{_generic_error_msg()}"
    except requests.exceptions.ConnectionError:
        return f"error:{_connection_refused_msg()}"
    except requests.exceptions.Timeout:
        return f"error:{t('err_timeout_check')}"
    except requests.exceptions.RequestException:
        return f"error:{_generic_error_msg()}"

def api_get_plan(patient_id: str) -> tuple[dict | None, str]:
    try:
        resp = requests.get(f"{API_BASE}/patient/{patient_id}/plan", timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            return resp.json().get("result", {}), ""
        return None, _generic_error_msg()
    except requests.exceptions.ConnectionError:
        return None, _connection_refused_msg()
    except requests.exceptions.Timeout:
        return None, t("err_timeout_check")
    except requests.exceptions.RequestException:
        return None, _generic_error_msg()

def api_post_intake(payload: dict) -> tuple[dict | None, str]:
    try:
        resp = requests.post(f"{API_BASE}/intake", json=payload, timeout=INTAKE_TIMEOUT)
        if resp.status_code == 200:
            return resp.json().get("result", {}), ""
        try:
            detail = resp.json().get("detail", _generic_error_msg())
        except Exception:
            detail = _generic_error_msg()
        return None, str(detail)
    except requests.exceptions.ConnectionError:
        return None, _connection_refused_msg()
    except requests.exceptions.Timeout:
        return None, t("err_timeout_plan")
    except requests.exceptions.RequestException:
        return None, _generic_error_msg()

def api_log_symptom(patient_id: str, symptom_text: str) -> tuple[dict | None, str]:
    try:
        resp = requests.post(
            f"{API_BASE}/log-symptom",
            json={"patient_id": patient_id, "symptom_text": symptom_text},
            timeout=INTAKE_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("result", {}), ""
        try:
            detail = resp.json().get("detail", _generic_error_msg())
        except Exception:
            detail = _generic_error_msg()
        return None, str(detail)
    except requests.exceptions.ConnectionError:
        return None, _connection_refused_msg()
    except requests.exceptions.Timeout:
        return None, t("err_timeout_short")
    except requests.exceptions.RequestException:
        return None, _generic_error_msg()

def api_give_feedback(patient_id: str, feedback_text: str) -> tuple[dict | None, str]:
    try:
        resp = requests.post(
            f"{API_BASE}/feedback",
            json={"patient_id": patient_id, "raw_feedback_text": feedback_text, "logged_meals": []},
            timeout=INTAKE_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("result", {}), ""
        try:
            detail = resp.json().get("detail", _generic_error_msg())
        except Exception:
            detail = _generic_error_msg()
        return None, str(detail)
    except requests.exceptions.ConnectionError:
        return None, _connection_refused_msg()
    except requests.exceptions.Timeout:
        return None, t("err_timeout_short")
    except requests.exceptions.RequestException:
        return None, _generic_error_msg()

# ---------------------------------------------------------------------------
# UI Helpers
# ---------------------------------------------------------------------------
def _show_error(msg: str) -> None:
    st.markdown(f'<div class="error-box">⚠️ {msg}</div>', unsafe_allow_html=True)

def _show_success(msg: str) -> None:
    st.markdown(f'<div class="success-box">✅ {msg}</div>', unsafe_allow_html=True)

def _goto(screen: str, **kwargs) -> None:
    st.session_state["current_screen"] = screen
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()

def _render_header_bar() -> None:
    """Fixed minimal light translucent top header bar."""
    st.markdown(
        """
        <div class="app-header-bar">
          <div class="app-brand">
            <svg class="app-brand-icon" viewBox="0 0 24 24">
              <path d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4M11,7V13H17V11H13V7H11Z"/>
            </svg>
            <span>Clinical Anemia Diet System</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _render_language_toggle() -> None:
    lang = st.session_state.get("language", "en")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button(t("language_en"), key="hdr_lang_en"):
            st.session_state["language"] = "en"
            st.rerun()
    with c2:
        if st.button(t("language_ta"), key="hdr_lang_ta"):
            st.session_state["language"] = "ta"
            st.rerun()

def _render_step_progress(current_step: int) -> None:
    steps = [t("step_basics"), t("step_health"), t("step_symptoms"), t("step_review")]
    html = '<div class="step-bar">'
    for i, label in enumerate(steps, start=1):
        if i < current_step:
            circle_cls, tick, label_cls, connector_cls = "step-circle done", "✓", "step-label", "step-connector done"
        elif i == current_step:
            circle_cls, tick, label_cls, connector_cls = "step-circle active", str(i), "step-label active", "step-connector"
        else:
            circle_cls, tick, label_cls, connector_cls = "step-circle", str(i), "step-label", "step-connector"

        html += f"""
          <div class="step-item" style="flex-direction:column;align-items:center;">
            <div class="{circle_cls}">{tick}</div>
            <div class="{label_cls}">{label}</div>
          </div>
        """
        if i < len(steps):
            html += f'<div class="{connector_cls}"></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def _build_intake_payload() -> dict:
    s = st.session_state
    conditions = list(s.get("f_conditions", []))
    other = s.get("f_conditions_other", "").strip()
    if other:
        conditions.append(other)

    allergies = [a.strip() for a in s.get("f_allergies", "").split(",") if a.strip()]
    medications = [m.strip() for m in s.get("f_medications", "").split(",") if m.strip()]
    symptom_text = s.get("f_symptom_text", "").strip()
    symptom_log = [symptom_text] if symptom_text else []

    return {
        "patient_id": s["patient_id"],
        "diet_type": s.get("f_diet_type", "vegetarian"),
        "pregnancy_status": s.get("f_pregnancy_status", "not_pregnant"),
        "existing_conditions": conditions,
        "allergies": allergies,
        "current_medications": medications,
        "symptom_log": symptom_log,
        "biomarkers": {},
    }

# ===========================================================================
# SCREEN 1: LOGIN
# ===========================================================================
def screen_login() -> None:
    col_left, col_right = st.columns([11, 10], gap="large")

    with col_left:
        st.markdown(
            f"""
            <div class="hero-panel">
              <div class="hero-title-large">{t("login_heading")}</div>
              <div class="hero-tagline">{t("app_subtitle")}</div>
              <ul class="trust-list">
                <li class="trust-item"><svg style="width:20px;height:20px;fill:#0F766E;" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg> Personalised to diet & health conditions</li>
                <li class="trust-item"><svg style="width:20px;height:20px;fill:#0F766E;" viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/></svg> Safety-checked clinical protocol</li>
                <li class="trust-item"><svg style="width:20px;height:20px;fill:#0F766E;" viewBox="0 0 24 24"><path d="M12.87 15.07l-2.54-2.51.03-.03c1.74-1.94 2.98-4.17 3.71-6.53H17V4h-7V2H8v2H1v2h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2.1l1.1-3h4.6l1.1 3H23l-4.5-12zm-2.6 7l1.6-4.33L19.1 17h-3.2z"/></svg> Multilingual (English & தமிழ்)</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_right:
        with _card():
            _render_language_toggle()
            st.markdown("<br>", unsafe_allow_html=True)

            patient_id_val = st.text_input(
                t("patient_id_label"),
                value=st.session_state.get("patient_id", ""),
                placeholder=t("patient_id_placeholder"),
                key="input_pid",
            )
            name_val = st.text_input(
                t("name_label"),
                value=st.session_state.get("patient_name", ""),
                placeholder=t("name_placeholder"),
                key="input_name",
            )

            st.session_state["patient_id"] = patient_id_val
            st.session_state["patient_name"] = name_val
            can_continue = bool(patient_id_val.strip() and name_val.strip())

            if st.session_state.get("api_error"):
                _show_error(st.session_state["api_error"])

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(t("continue_btn"), disabled=not can_continue, key="login_continue_btn"):
                st.session_state["api_error"] = ""
                pid = patient_id_val.strip()

                with st.spinner(t("checking_record")):
                    status = api_check_patient(pid)

                if status == "found":
                    plan, err = api_get_plan(pid)
                    if err:
                        st.session_state["api_error"] = err
                        st.rerun()
                    else:
                        st.session_state["current_plan"] = plan
                        _goto("home")
                elif status == "not_found":
                    _goto("intake", intake_step=1)
                else:
                    st.session_state["api_error"] = status.removeprefix("error:")
                    st.rerun()

# ===========================================================================
# SCREEN 2: MULTI-STEP INTAKE
# ===========================================================================
def screen_intake() -> None:
    st.markdown(f"### 📋 {t('intake_heading')}")

    step = st.session_state["intake_step"]
    with _card():
        _render_step_progress(step)

        if step == 1:
            _intake_step1()
        elif step == 2:
            _intake_step2()
        elif step == 3:
            _intake_step3()
        elif step == 4:
            _intake_step4()

def _intake_step1() -> None:
    st.markdown(f"#### {t('step1_heading')}")
    st.markdown(f"<label>{t('diet_type_label')}</label>", unsafe_allow_html=True)
    diet_opts = [
        ("vegetarian", t("diet_vegetarian")),
        ("non-vegetarian", t("diet_non_vegetarian")),
        ("vegan", t("diet_vegan")),
        ("eggetarian", t("diet_eggetarian")),
    ]
    curr_diet = st.session_state.get("f_diet_type", "vegetarian")
    d_cols = st.columns(len(diet_opts))
    for col, (val, label) in zip(d_cols, diet_opts):
        with col:
            cls = "chip-selected" if (curr_diet == val) else "chip-unselected"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(label, key=f"btn_diet_{val}"):
                st.session_state["f_diet_type"] = val
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"<label>{t('pregnancy_label')}</label>", unsafe_allow_html=True)
    preg_opts = [
        ("not_pregnant", t("preg_not_pregnant")),
        ("pregnant", t("preg_pregnant")),
        ("lactating", t("preg_lactating")),
    ]
    curr_preg = st.session_state.get("f_pregnancy_status", "not_pregnant")
    p_cols = st.columns(len(preg_opts))
    for col, (val, label) in zip(p_cols, preg_opts):
        with col:
            cls = "chip-selected" if (curr_preg == val) else "chip-unselected"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(label, key=f"btn_preg_{val}"):
                st.session_state["f_pregnancy_status"] = val
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state["f_pregnancy_status"] == "pregnant":
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"<label>{t('trimester_label')}</label>", unsafe_allow_html=True)
        trim_opts = [("1st", t("trimester_1st")), ("2nd", t("trimester_2nd")), ("3rd", t("trimester_3rd"))]
        curr_trim = st.session_state.get("f_trimester", "1st")
        t_cols = st.columns(len(trim_opts))
        for col, (val, label) in zip(t_cols, trim_opts):
            with col:
                cls = "chip-selected" if (curr_trim == val) else "chip-unselected"
                st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
                if st.button(label, key=f"btn_trim_{val}"):
                    st.session_state["f_trimester"] = val
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button(t("next_btn"), key="s1_next"):
        st.session_state["intake_step"] = 2
        st.rerun()

def _intake_step2() -> None:
    st.markdown(f"#### {t('step2_heading')}")
    st.markdown(f"<label>{t('conditions_label')}</label>", unsafe_allow_html=True)

    # Issue 4 Fix: Use list stored in session state & robust toggle logic
    current_conds = list(st.session_state.get("f_conditions", []))
    c_cols = st.columns(3)
    for idx, cond in enumerate(COMMON_CONDITIONS):
        with c_cols[idx % 3]:
            is_sel = (cond in current_conds)
            cls = "chip-selected" if is_sel else "chip-unselected"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(cond, key=f"btn_cond_{cond}"):
                updated_conds = list(st.session_state.get("f_conditions", []))
                if cond in updated_conds:
                    updated_conds.remove(cond)
                else:
                    updated_conds.append(cond)
                st.session_state["f_conditions"] = updated_conds
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    other_cond = st.text_input(
        t("other_conditions_label"),
        value=st.session_state.get("f_conditions_other", ""),
        placeholder=t("other_conditions_placeholder"),
        key="s2_other",
    )
    st.session_state["f_conditions_other"] = other_cond

    allergies = st.text_input(
        t("allergies_label"),
        value=st.session_state.get("f_allergies", ""),
        placeholder=t("allergies_placeholder"),
        key="s2_allergies",
    )
    st.session_state["f_allergies"] = allergies

    meds = st.text_input(
        t("medications_label"),
        value=st.session_state.get("f_medications", ""),
        placeholder=t("medications_placeholder"),
        key="s2_meds",
    )
    st.session_state["f_medications"] = meds

    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_next = st.columns(2)
    with col_back:
        if st.button(t("back_btn"), key="s2_back"):
            st.session_state["intake_step"] = 1
            st.rerun()
    with col_next:
        if st.button(t("next_btn"), key="s2_next"):
            st.session_state["intake_step"] = 3
            st.rerun()

def _intake_step3() -> None:
    st.markdown(f"#### {t('step3_heading')}")
    st.markdown(f"<p style='color:#64748B;'>{t('symptoms_chip_hint')}</p>", unsafe_allow_html=True)

    chip_cols = st.columns(len(QUICK_SYMPTOM_KEYS))
    for col, (chip_key, english_value) in zip(chip_cols, QUICK_SYMPTOM_KEYS):
        with col:
            st.markdown('<div class="chip-unselected">', unsafe_allow_html=True)
            if st.button(t(chip_key), key=f"chip_{english_value}"):
                current = st.session_state.get("f_symptom_text", "")
                separator = ", " if current.strip() else ""
                st.session_state["f_symptom_text"] = current + separator + english_value
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    symptom_text = st.text_area(
        t("symptom_text_label"),
        value=st.session_state.get("f_symptom_text", ""),
        height=140,
        placeholder=t("symptom_text_placeholder"),
        key="s3_symptoms",
    )
    st.session_state["f_symptom_text"] = symptom_text

    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_next = st.columns(2)
    with col_back:
        if st.button(t("back_btn"), key="s3_back"):
            st.session_state["intake_step"] = 2
            st.rerun()
    with col_next:
        if st.button(t("next_btn"), key="s3_next"):
            st.session_state["intake_step"] = 4
            st.rerun()

def _intake_step4() -> None:
    st.markdown(f"#### {t('step4_heading')}")
    s = st.session_state

    preg_display_map = {"not_pregnant": t("preg_not_pregnant"), "pregnant": t("preg_pregnant"), "lactating": t("preg_lactating")}
    trim_display_map = {"1st": t("trimester_1st"), "2nd": t("trimester_2nd"), "3rd": t("trimester_3rd")}
    diet_display_map = {"vegetarian": t("diet_vegetarian"), "non-vegetarian": t("diet_non_vegetarian"), "vegan": t("diet_vegan"), "eggetarian": t("diet_eggetarian")}

    # Basics review card
    st.markdown('<div class="glass-card-info">', unsafe_allow_html=True)
    col_title, col_edit = st.columns([5, 1])
    with col_title:
        st.markdown(f"**{t('review_basics_title')}**")
        st.markdown(f"{t('review_diet_type')} **{diet_display_map.get(s.get('f_diet_type', 'vegetarian'), s.get('f_diet_type', ''))}**")
        st.markdown(f"{t('review_pregnancy')} **{preg_display_map.get(s.get('f_pregnancy_status', 'not_pregnant'), s.get('f_pregnancy_status', ''))}**")
        if s.get("f_pregnancy_status") == "pregnant":
            st.markdown(f"{t('review_trimester')} **{trim_display_map.get(s.get('f_trimester', '1st'), s.get('f_trimester', ''))}**")
    with col_edit:
        if st.button(t("edit_btn"), key="rev_edit1"):
            st.session_state["intake_step"] = 1
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Health review card
    st.markdown('<div class="glass-card-info">', unsafe_allow_html=True)
    col_title2, col_edit2 = st.columns([5, 1])
    with col_title2:
        st.markdown(f"**{t('review_health_title')}**")
        conds = list(s.get("f_conditions", []))
        if s.get("f_conditions_other", "").strip():
            conds.append(s.get("f_conditions_other", "").strip())
        st.markdown(f"{t('review_conditions')} **{', '.join(conds) if conds else t('none_label')}**")
        allergy_list = [a.strip() for a in s.get("f_allergies", "").split(",") if a.strip()]
        st.markdown(f"{t('review_allergies')} **{', '.join(allergy_list) if allergy_list else t('none_label')}**")
        med_list = [m.strip() for m in s.get("f_medications", "").split(",") if m.strip()]
        st.markdown(f"{t('review_medications')} **{', '.join(med_list) if med_list else t('none_label')}**")
    with col_edit2:
        if st.button(t("edit_btn"), key="rev_edit2"):
            st.session_state["intake_step"] = 2
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Symptoms review card
    st.markdown('<div class="glass-card-info">', unsafe_allow_html=True)
    col_title3, col_edit3 = st.columns([5, 1])
    with col_title3:
        st.markdown(f"**{t('review_symptoms_title')}**")
        sym = s.get("f_symptom_text", "").strip()
        st.markdown(f"_{sym if sym else t('none_described')}_")
    with col_edit3:
        if st.button(t("edit_btn"), key="rev_edit3"):
            st.session_state["intake_step"] = 3
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if s.get("api_error"):
        _show_error(s["api_error"])

    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_gen = st.columns(2)
    with col_back:
        if st.button(t("back_btn"), key="rev_back"):
            st.session_state["intake_step"] = 3
            st.rerun()
    with col_gen:
        if st.button(t("generate_plan_btn"), key="rev_generate"):
            st.session_state["api_error"] = ""
            payload = _build_intake_payload()
            with st.spinner(t("generating_plan_spinner")):
                result, err = api_post_intake(payload)
            if err:
                st.session_state["api_error"] = err
                st.rerun()
            else:
                st.session_state["current_plan"] = result
                _goto("plan")

# ===========================================================================
# SCREEN 3: PLAN DISPLAY
# ===========================================================================
def screen_plan() -> None:
    st.markdown(f"## {t('plan_heading')}")

    plan = st.session_state.get("current_plan")

    if not plan:
        with _card():
            _show_error(t("plan_empty_error"))
            if st.button(t("plan_go_back_btn"), key="plan_no_plan_back"):
                _goto("login")
        return

    content_mode = plan.get("content_mode", "full_plan")
    raw_closing = plan.get("closing_line") or plan.get("disclaimer", "")
    closing_line = translate_dynamic(raw_closing)

    if content_mode == "safety_override":
        with _card(variant="alert"):
            st.markdown(
                f"<h2 style='color:#DC2626;'>"
                f"<span>⚠️</span> {t('safety_alert_heading').replace('⚠️ ', '')}"
                f"</h2>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='color:#7F1D1D;font-weight:600;font-size:1.1rem;margin-bottom:1rem;'>"
                f"{t('safety_alert_seek_care')}</p>",
                unsafe_allow_html=True,
            )
            raw_safety_note = plan.get("safety_note") or plan.get("note", "")
            if raw_safety_note:
                safety_note = translate_dynamic(raw_safety_note)
                st.markdown(
                    f"<p style='font-size:1.05rem;color:#450A0A;line-height:1.7;'>{safety_note}</p>",
                    unsafe_allow_html=True,
                )

    else:
        slot_config = {
            "morning":           (t("slot_morning"),           "meal-slot-morning"),
            "afternoon_evening": (t("slot_afternoon_evening"), "meal-slot-afternoon"),
            "night":             (t("slot_night"),             "meal-slot-night"),
        }
        # Build all meal HTML in one st.markdown call — avoids empty-box issue
        all_sections = ""
        for slot_key, (slot_label, slot_css_class) in slot_config.items():
            items = plan.get(slot_key) or []
            if not items:
                continue
            inner = ""
            for item in items:
                if isinstance(item, dict):
                    raw_name = item.get("name") or item.get("food") or str(item)
                    name = translate_dynamic(raw_name)
                    enhancers = item.get("enhancers") or item.get("iron_enhancers", [])
                    inhibitors = item.get("inhibitors") or item.get("iron_inhibitors", [])
                    inner += f'<div class="meal-item">{name}'
                    if enhancers:
                        enh_list = enhancers if isinstance(enhancers, list) else [str(enhancers)]
                        enh_translated = ", ".join([translate_dynamic(e) for e in enh_list])
                        inner += f'<div class="meal-sub">{t("meal_have_with")} {enh_translated}</div>'
                    if inhibitors:
                        inh_list = inhibitors if isinstance(inhibitors, list) else [str(inhibitors)]
                        inh_translated = ", ".join([translate_dynamic(i) for i in inh_list])
                        inner += f'<div class="meal-sub">{t("meal_avoid_with")} {inh_translated}</div>'
                    inner += "</div>"
                else:
                    inner += f'<div class="meal-item">{translate_dynamic(str(item))}</div>'
            all_sections += (
                f'<div class="meal-slot-section {slot_css_class}">'
                f'<div class="meal-slot-label">{slot_label}</div>'
                f'{inner}</div>'
            )
        # Render everything inside a single glass-card div (pure HTML, no widgets)
        st.markdown(f'<div class="glass-card">{all_sections}</div>', unsafe_allow_html=True)

    if closing_line:
        st.markdown(f'<div class="disclaimer">{closing_line}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button(t("plan_continue_btn"), key="plan_to_home"):
        _goto("home")

# ===========================================================================
# SCREEN 4: DAILY HOME
# ===========================================================================
def screen_home() -> None:
    name = st.session_state.get("patient_name", "")

    greeting = t("home_welcome")
    name_part = f", {name}" if name else ""
    st.markdown(
        f"<h1 style='color:#0F766E;'>{greeting}{name_part}!</h1>",
        unsafe_allow_html=True,
    )

    with _card():
        st.markdown(
            f"<p style='color:#475569;font-size:1.15rem;margin-bottom:1rem;'>{t('home_subtitle')}</p>",
            unsafe_allow_html=True,
        )
        if st.button(t("view_plan_btn"), key="home_view_plan"):
            plan, err = api_get_plan(st.session_state["patient_id"])
            if err:
                _show_error(err)
            else:
                st.session_state["current_plan"] = plan
                _goto("plan")

    st.markdown("<br>", unsafe_allow_html=True)
    col_sym, col_feed = st.columns(2, gap="medium")

    # Symptom panel
    with col_sym:
        with _card():
            st.markdown(f"### {t('log_symptom_heading')}")
            st.markdown(
                f"<p style='color:#475569;margin-bottom:1rem;'>{t('log_symptom_desc')}</p>",
                unsafe_allow_html=True,
            )

            toggle_key = "show_symptom_panel"
            if not st.session_state[toggle_key]:
                if st.button(t("log_symptom_btn"), key="home_sym_open"):
                    st.session_state[toggle_key] = True
                    st.session_state["symptom_confirm_msg"] = ""
                    st.rerun()
            else:
                sym_input = st.text_area(
                    t("symptom_input_label"),
                    value=st.session_state.get("sym_draft", ""),
                    height=100,
                    placeholder=t("symptom_input_placeholder"),
                    key="home_sym_input",
                )
                st.session_state["sym_draft"] = sym_input
                if st.session_state.get("symptom_confirm_msg"):
                    _show_success(translate_dynamic(st.session_state["symptom_confirm_msg"]))

                c1, c2 = st.columns(2)
                with c1:
                    if st.button(t("submit_btn"), key="home_sym_submit"):
                        if sym_input.strip():
                            with st.spinner(t("evaluating_spinner")):
                                result, err = api_log_symptom(
                                    st.session_state["patient_id"],
                                    sym_input.strip(),
                                )
                            if err:
                                _show_error(err)
                            else:
                                if isinstance(result, dict) and "content_mode" in result:
                                    st.session_state["current_plan"] = result
                                    _goto("plan")
                                else:
                                    msg = t("symptom_logged_msg")
                                    st.session_state["symptom_confirm_msg"] = msg
                                    st.rerun()
                with c2:
                    if st.button(t("cancel_btn"), key="home_sym_cancel"):
                        st.session_state[toggle_key] = False
                        st.session_state["symptom_confirm_msg"] = ""
                        st.rerun()

    # Feedback panel
    with col_feed:
        with _card():
            st.markdown(f"### {t('feedback_heading')}")
            st.markdown(
                f"<p style='color:#475569;margin-bottom:1rem;'>{t('feedback_desc')}</p>",
                unsafe_allow_html=True,
            )

            toggle_key2 = "show_feedback_panel"
            if not st.session_state[toggle_key2]:
                if st.button(t("feedback_btn"), key="home_feed_open"):
                    st.session_state[toggle_key2] = True
                    st.session_state["feedback_confirm_msg"] = ""
                    st.rerun()
            else:
                feed_input = st.text_area(
                    t("feedback_input_label"),
                    value=st.session_state.get("feed_draft", ""),
                    height=100,
                    placeholder=t("feedback_input_placeholder"),
                    key="home_feed_input",
                )
                st.session_state["feed_draft"] = feed_input

                if st.session_state.get("feedback_confirm_msg"):
                    translated_fb_response = translate_dynamic(st.session_state["feedback_confirm_msg"])
                    st.markdown(
                        f'<div class="glass-card-info" style="margin-top:0.5rem;">'
                        f'<strong>{t("feedback_response_label")}</strong><br>'
                        f'{translated_fb_response}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                c1, c2 = st.columns(2)
                with c1:
                    if st.button(t("submit_btn"), key="home_feed_submit"):
                        if feed_input.strip():
                            with st.spinner(t("processing_feedback_spinner")):
                                result, err = api_give_feedback(
                                    st.session_state["patient_id"],
                                    feed_input.strip(),
                                )
                            if err:
                                _show_error(err)
                            else:
                                if isinstance(result, dict) and "content_mode" in result:
                                    st.session_state["current_plan"] = result
                                    _goto("plan")
                                else:
                                    note = ""
                                    if isinstance(result, dict):
                                        note = result.get("note") or result.get("message", "")
                                    st.session_state["feedback_confirm_msg"] = (
                                        note if note else t("feedback_thankyou_msg")
                                    )
                                    st.rerun()
                with c2:
                    if st.button(t("cancel_btn"), key="home_feed_cancel"):
                        st.session_state[toggle_key2] = False
                        st.session_state["feedback_confirm_msg"] = ""
                        st.rerun()

# ---------------------------------------------------------------------------
# Card context-manager helper — THE single root-cause fix
# ---------------------------------------------------------------------------
@contextmanager
def _card(variant: str = "card"):
    """Wrap content in a styled Streamlit container.

    Streamlit mangles manually-injected <div> tags, closing them immediately
    and leaving an empty styled box before the actual content. This helper
    uses st.container() (which Streamlit natively understands), then applies
    glass-card styling via CSS targeting the container's data-testid wrapper.
    Variant: 'card' | 'alert' | 'info'
    """
    css_class = {
        "card": "glass-card",
        "alert": "glass-card-alert",
        "info": "glass-card-info",
    }.get(variant, "glass-card")
    uid = uuid.uuid4().hex[:8]
    # Invisible anchor div so JS can locate this specific container
    st.markdown(
        f'<style>div[data-card-id="{uid}"]{{display:none}}</style>'
        f'<div data-card-id="{uid}"></div>',
        unsafe_allow_html=True,
    )
    container = st.container(border=False)
    # JS walks the DOM from the anchor up to the stVerticalBlock wrapper
    # and applies the glass-card class to it
    st.markdown(
        f"""<script>
        (function(){{
          var a=document.querySelector('div[data-card-id="{uid}"]');
          if(a){{var p=a.closest('[data-testid="stVerticalBlock"]');
            if(p&&p.parentElement)p.parentElement.classList.add('{css_class}');}}
        }})();</script>""",
        unsafe_allow_html=True,
    )
    with container:
        yield


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
def main() -> None:
    _render_header_bar()
    screen = st.session_state.get("current_screen", "login")

    if screen == "login":
        screen_login()
    elif screen == "intake":
        screen_intake()
    elif screen == "plan":
        screen_plan()
    elif screen == "home":
        screen_home()
    else:
        st.error(f"{t('err_unknown_screen')} {screen!r}")
        if st.button(t("return_to_login_btn")):
            _goto("login")

    st.markdown(f'<div class="disclaimer">{t("disclaimer")}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
