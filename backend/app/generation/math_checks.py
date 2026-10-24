"""Isolate symbolic work in a bounded subprocess; timeout is never a pass."""
import json
import os
from pathlib import Path
import subprocess
import sys


def check_math(spec, timeout_seconds=8):
    try:
        completed=subprocess.run([sys.executable,"-m","app.generation.math_worker"],
            input=json.dumps(spec),capture_output=True,text=True,encoding="utf-8",timeout=timeout_seconds,
            cwd=Path(__file__).resolve().parents[2],creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        if completed.returncode:
            return {"result":"inconclusive","rationale":"The isolated symbolic checker could not finish."}
        return json.loads(completed.stdout)
    except subprocess.TimeoutExpired:
        return {"result":"not_checked","rationale":"The symbolic check exceeded its time limit."}
    except (ValueError,OSError):
        return {"result":"inconclusive","rationale":"The symbolic checker returned no usable result."}
