import io
import sys
import time
import json
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tests.test_flow import TEST_CASES, TeeStream
from anemia_diet_system.flow import AnemiaFlow

def run_single(tc_id):
    print(f"\n==================== RUNNING {tc_id} ====================")
    tc = [t for t in TEST_CASES if t['id'] == tc_id][0]
    tee = TeeStream(sys.stdout)
    sys.stdout = tee
    
    flow = AnemiaFlow()
    try:
        out = tc['runner'](flow, tee)
        err = None
    except Exception as e:
        out = {}
        err = str(e)
        
    sys.stdout = tee.original
    log_text = tee.getvalue()
    
    if err:
        passed = False
        detail = f"Exception raised: {err}"
    else:
        passed, detail = tc['check'](out, log_text)
        
    res_data = {
        'tc_id': tc_id,
        'description': tc['description'],
        'passed': passed,
        'detail': detail,
        'log_text': log_text,
        'output': out,
        'error': err
    }
    
    file_path = f"EXEC_{tc_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(res_data, f, indent=2, default=str)
    print(f"==================== {tc_id} DONE | PASSED: {passed} ====================\n")
    return passed

if __name__ == "__main__":
    if len(sys.argv) > 1:
        tcs = [sys.argv[1].upper()]
    else:
        tcs = ["FT02", "FT03", "FT04", "FT05", "FT06", "FT07"]
        
    for i, tc_id in enumerate(tcs):
        if i > 0:
            print("Sleeping 20 seconds to prevent rate limits...")
            time.sleep(20)
        run_single(tc_id)
