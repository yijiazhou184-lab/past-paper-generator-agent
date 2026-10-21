"""Deliberate local worker interruption. Retains failed/cancelled/recovered task history."""
import json
from pathlib import Path
import time
import uuid
import httpx
import psutil
import local

root = Path(__file__).resolve().parents[1]
client = httpx.Client(base_url="http://127.0.0.1:5173/api/v1", timeout=15)
def get(path):
    for attempt in range(20):
        try:
            r = client.get(path)
            if r.status_code < 500:
                r.raise_for_status()
                return r.json()
        except httpx.TransportError:
            pass
        time.sleep(1)
    raise RuntimeError("Local API did not recover within 20 seconds")
def post(path):
    r = client.post(path, headers={"Idempotency-Key": str(uuid.uuid4())}); r.raise_for_status(); return r.json()
client.headers["X-CSRFToken"] = get("/session")["csrf_token"]
client.headers["X-CSRFToken"] = post("/session")["csrf_token"]
course = get("/courses")["courses"][0]
materials = get(f"/courses/{course['id']}/materials")["materials"]
seminar = next(m for m in materials if "Topic 2 - seminar" in m["filename"])
if seminar["state"] != "failed":
    raise SystemExit("Run only when the recorded seminar failure is the current task.")
first = post(f"/tasks/{seminar['task_id']}/retries")
cancelled = post(f"/tasks/{first['id']}/cancel")
assert cancelled["state"] == "cancelled"
task = post(f"/tasks/{first['id']}/retries")
task_id = task["id"]
report = {"mode": "real_local_no_models", "original_failure": seminar["task_id"],
          "cancelled_task": first["id"], "recovered_task": task_id}
print("Cancelled queued retry; new task:", task_id, flush=True)
deadline = time.monotonic() + 240
while time.monotonic() < deadline:
    task = get(f"/tasks/{task_id}")
    if task["state"] == "processing" and task["stage"] == "Parsing page structure":
        break
    time.sleep(1)
else:
    raise RuntimeError("Parser did not start")
report["epoch_before"] = task["epoch"]
(root / "var/recovery-check-in-progress.json").write_text(json.dumps(report, indent=2))
saved = json.loads((root / "var/services.json").read_text())["worker"]
assert local.process_is_ours(saved["pid"], saved["started"])
worker = psutil.Process(saved["pid"])
for child in worker.children(recursive=True):
    child.terminate()
worker.terminate()
worker.wait(timeout=10)
print("Stopped the verified project worker during local parsing; restarting services.", flush=True)
local.start()
deadline = time.monotonic() + 300
while time.monotonic() < deadline:
    task = get(f"/tasks/{task_id}")
    if task["state"] in ("succeeded", "failed", "cancelled"):
        break
    time.sleep(2)
report["final_state"] = task["state"]
report["epoch_after"] = task["epoch"]
report["events"] = task["events"]
assert task["state"] == "succeeded", task
assert task["epoch"] > report["epoch_before"]
assert get(f"/tasks/{task_id}")["id"] == task_id
assert get(f"/tasks/{first['id']}")["state"] == "cancelled"
assert get(f"/tasks/{seminar['task_id']}")["state"] == "failed"
(root / "var/recovery-check.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2), flush=True)
