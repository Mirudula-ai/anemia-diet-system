"""Run only TC-R02 (nonsense query) in isolation. Writes result to tc_r02_result.json."""
import json, os, re, sys, time, traceback
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

os.environ["LLM_MODEL"] = "groq/llama-3.1-8b-instant"
os.environ["DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DROP_PARAMS"] = "True"

import litellm

def _clean(obj):
    if isinstance(obj, dict):
        obj.pop("cache_control", None)
        obj.pop("cache_breakpoint", None)
        for v in list(obj.values()): _clean(v)
    elif isinstance(obj, list):
        for i in obj: _clean(i)

_orig = litellm.completion
def _patched(*a, **kw):
    _clean(kw)
    return _orig(*a, **kw)
litellm.completion = _patched
litellm.drop_params = True

from dotenv import load_dotenv
load_dotenv(override=False)
os.environ["LLM_MODEL"] = "groq/llama-3.1-8b-instant"

sys.path.insert(0, str(Path(__file__).resolve().parents[0] / "src"))
from anemia_diet_system.crews.research_crew.research_crew import ResearchCrew

RESULT_FILE = Path(__file__).resolve().parent / "tc_r02_result.json"

def parse_output(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(l for l in raw.splitlines() if not l.strip().startswith("```"))
    try: return json.loads(raw)
    except json.JSONDecodeError: pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try: return json.loads(m.group(0))
        except json.JSONDecodeError: pass
    return {}

QUERY = "asdkjfh qwerty nonsense medical term xyz123"
MAX_ATTEMPTS = 5
RETRY_SLEEP  = 65

print(f"\nTC-R02: meaningless query -> no reliable information\n")

raw = ""
error_msg = None
for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        print(f"  Attempt {attempt}/{MAX_ATTEMPTS}...")
        crew = ResearchCrew()
        result = crew.crew().kickoff(inputs={"research_query": QUERY})
        raw = result.raw if hasattr(result, "raw") else str(result)
        error_msg = None
        break
    except Exception as exc:
        err = str(exc).lower()
        if ("rate_limit" in err or "429" in err) and attempt < MAX_ATTEMPTS:
            print(f"  Rate-limit hit. Sleeping {RETRY_SLEEP}s...")
            time.sleep(RETRY_SLEEP)
        else:
            error_msg = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            break

if error_msg:
    output = {"tc_id": "TC-R02", "status": "ERROR", "error": error_msg, "raw": "", "parsed": {}}
else:
    out = parse_output(raw)
    passed = (
        out.get("sources_found") is False
        and isinstance(out.get("summary"), str)
        and any(
            p in out["summary"].lower()
            for p in ["no reliable", "no information", "not found", "no evidence",
                      "no authoritative", "nonsense", "unable to find",
                      "could not find", "cannot find", "no relevant"]
        )
    )
    output = {
        "tc_id": "TC-R02",
        "status": "PASS" if passed else "FAIL",
        "raw": raw,
        "parsed": out,
    }

# Always write result to JSON file
RESULT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n  Result: {output['status']}")
print(f"  Written to: {RESULT_FILE}")
