"""
tests/test_research_crew.py
Research Crew test suite – TC-R01 through TC-R04.

Rate-limit strategy:
  • 18 s gap between every test case (as required).
  • On a RateLimitError the test sleeps 65 s and retries, up to 5 times.
  • After all retries are exhausted the test is recorded as ERROR.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# ── Windows UTF-8 console ──────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ── LiteLLM / cache-control patches (must happen before crewai imports) ───
os.environ.setdefault("DISABLE_PROMPT_CACHING", "True")
os.environ.setdefault("LITELLM_DISABLE_PROMPT_CACHING", "True")
os.environ.setdefault("LITELLM_DROP_PARAMS", "True")

# Force a lightweight model during tests to stay inside rate limits
os.environ["LLM_MODEL"] = "groq/llama-3.1-8b-instant"

import litellm  # noqa: E402  (must be after env vars)

def _clean_dict(obj):
    if isinstance(obj, dict):
        obj.pop("cache_control", None)
        obj.pop("cache_breakpoint", None)
        for v in list(obj.values()):
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

# ── Load dotenv AFTER env overrides so LLM_MODEL isn't clobbered ──────────
from dotenv import load_dotenv  # noqa: E402

load_dotenv(override=False)  # override=False → our os.environ values win
os.environ["LLM_MODEL"] = "groq/llama-3.1-8b-instant"  # ensure it sticks

# ── Add src/ to path ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anemia_diet_system.crews.research_crew.research_crew import ResearchCrew  # noqa: E402


# ── JSON parser ──────────────────────────────────────────────────────────
def parse_output(raw: str) -> dict:
    raw = raw.strip()
    # Strip markdown fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(
            l for l in lines if not l.strip().startswith("```")
        )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}


# ── Test definitions ──────────────────────────────────────────────────────
TEST_CASES = [
    {
        "id": "TC-R01",
        "description": "iron absorption interactions – vegan + celiac",
        "query": "iron absorption interactions for a vegan patient with celiac disease",
        "check": lambda out: (
            out.get("sources_found") is True
            and isinstance(out.get("summary"), str)
            and len(out["summary"].strip()) > 0
            and bool(out.get("source_notes"))
        ),
    },
    {
        "id": "TC-R02",
        "description": "meaningless query → no reliable information",
        "query": "asdkjfh qwerty nonsense medical term xyz123",
        "check": lambda out: (
            out.get("sources_found") is False
            and isinstance(out.get("summary"), str)
            and any(
                phrase in out["summary"].lower()
                for phrase in [
                    "no reliable",
                    "no information",
                    "not found",
                    "no evidence",
                    "no authoritative",
                    "nonsense",
                    "unable to find",
                    "could not find",
                    "cannot find",
                ]
            )
        ),
    },
    {
        "id": "TC-R03",
        "description": "ICMR-NIN iron intake for pregnant women → specific number",
        "query": "ICMR-NIN recommended daily iron intake for pregnant women in India",
        "check": lambda out: (
            out.get("sources_found") is True
            and isinstance(out.get("summary"), str)
            and any(ch.isdigit() for ch in out["summary"])
        ),
    },
    {
        "id": "TC-R04",
        "description": "thalassemia contraindication → no 'you have' language",
        "query": "thalassemia and iron supplementation contraindication",
        "check": lambda out: (
            isinstance(out.get("summary"), str)
            and "you have" not in out["summary"].lower()
        ),
    },
]

# ── Runner ────────────────────────────────────────────────────────────────
MAX_ATTEMPTS   = 5
RETRY_SLEEP_S  = 65   # seconds to wait after a rate-limit error
BETWEEN_TC_S   = 18   # required gap between test cases


def run_single(query: str) -> str:
    """Kick off one crew run and return raw string output."""
    crew = ResearchCrew()
    result = crew.crew().kickoff(inputs={"research_query": query})
    return result.raw if hasattr(result, "raw") else str(result)


def run_tests():
    results = []

    for i, tc in enumerate(TEST_CASES):
        if i > 0:
            print(f"\n⏳  Waiting {BETWEEN_TC_S}s before next test case…")
            time.sleep(BETWEEN_TC_S)

        tc_id       = tc["id"]
        description = tc["description"]
        query       = tc["query"]

        print(f"\n{'='*62}")
        print(f"  {tc_id}: {description}")
        print(f"{'='*62}")

        raw    = ""
        status = "❌ FAIL"
        error  = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                raw = run_single(query)
                break  # success
            except Exception as exc:
                err_str = str(exc).lower()
                is_rate_limit = "rate_limit" in err_str or "429" in err_str
                if is_rate_limit and attempt < MAX_ATTEMPTS:
                    print(
                        f"  ⚠️  Rate-limit hit (attempt {attempt}/{MAX_ATTEMPTS}). "
                        f"Sleeping {RETRY_SLEEP_S}s…"
                    )
                    time.sleep(RETRY_SLEEP_S)
                else:
                    error = exc
                    break

        if error is not None:
            status = f"⚠️  ERROR: {error}"
            results.append({"id": tc_id, "description": description, "status": "ERROR", "label": status})
            print(f"\n  {status}\n")
            continue

        out = parse_output(raw)
        print(f"\nRAW OUTPUT (truncated):\n{raw[:600]}\n")
        print(f"PARSED:\n{json.dumps(out, indent=2)}\n")

        passed = tc["check"](out)
        status = "✅ PASS" if passed else "❌ FAIL"
        results.append({"id": tc_id, "description": description, "status": "PASS" if passed else "FAIL", "label": status})
        print(f"  Result: {status}")

    # ── Summary table ────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  RESEARCH CREW — TEST RESULTS SUMMARY")
    print("=" * 80)
    print(f"  {'ID':<8} {'Status':<8}  Description")
    print("  " + "-" * 76)
    passed_cnt = 0
    for r in results:
        print(f"  {r['id']:<8} {r['label']:<10}  {r['description']}")
        if r["status"] == "PASS":
            passed_cnt += 1
    print("  " + "-" * 76)
    print(f"  TOTAL: {passed_cnt}/{len(results)} passed\n")


if __name__ == "__main__":
    run_tests()
