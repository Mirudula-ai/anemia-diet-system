import os
import sys

os.environ["DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DISABLE_PROMPT_CACHING"] = "True"
os.environ["LITELLM_DROP_PARAMS"] = "True"

import litellm

def clean_dict(obj):
    if isinstance(obj, dict):
        obj.pop("cache_control", None)
        obj.pop("cache_breakpoint", None)
        for k, v in list(obj.items()):
            clean_dict(v)
    elif isinstance(obj, list):
        for item in obj:
            clean_dict(item)

_orig_completion = litellm.completion

def _patched_completion(*args, **kwargs):
    clean_dict(kwargs)
    try:
        return _orig_completion(*args, **kwargs)
    except Exception as e:
        with open("err2.txt", "w", encoding="utf-8") as f:
            f.write(f"EXC: {type(e)} {e}\n")
            if hasattr(e, "response") and hasattr(e.response, "text"):
                f.write(f"RESP: {e.response.text}\n")
            if hasattr(e, "message"):
                f.write(f"MSG: {e.message}\n")
        raise e

litellm.completion = _patched_completion
litellm.drop_params = True

from dotenv import load_dotenv
load_dotenv(override=True)

from pathlib import Path
project_root = Path(__file__).resolve().parents[0]
sys.path.append(str(project_root / "src"))

from anemia_diet_system.crews.research_crew.research_crew import ResearchCrew

print("Testing TC-R02...")
try:
    c = ResearchCrew()
    res = c.crew().kickoff(inputs={'research_query': 'asdkjfh qwerty nonsense medical term xyz123'})
    print("SUCCESS RESULT RAW:", res.raw if hasattr(res, 'raw') else str(res))
except Exception as e:
    print("EXC:", type(e), e)
