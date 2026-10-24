"""Reuse an isolated symbolic process; bound startup and each calculation separately."""
import json
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
import sys
from threading import Thread


class MathWorker:
    def __init__(self, timeout_seconds=8, startup_seconds=20):
        self.timeout_seconds = timeout_seconds
        self.startup_seconds = startup_seconds
        self.process = None
        self.reader = None
        self.messages = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        if self.reader:
            self.reader.join(timeout=1)
        for pipe in (process.stdin, process.stdout):
            if pipe:
                pipe.close()
        self.process = None

    def start(self):
        self.messages = Queue()
        self.process = subprocess.Popen(
            [sys.executable, "-m", "app.generation.math_worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1,
            cwd=Path(__file__).resolve().parents[2],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        process, messages = self.process, self.messages

        def read():
            try:
                for line in process.stdout:
                    messages.put(line)
            finally:
                messages.put(None)

        self.reader = Thread(target=read, daemon=True)
        self.reader.start()
        ready = self.messages.get(timeout=self.startup_seconds)
        if ready is None or json.loads(ready) != {"ready": True}:
            raise ValueError("Worker did not become ready.")

    def check(self, spec):
        starting = self.process is None
        try:
            if starting:
                self.start()
            starting = False
            self.process.stdin.write(json.dumps(spec) + "\n")
            self.process.stdin.flush()
            line = self.messages.get(timeout=self.timeout_seconds)
            if line is None:
                raise ValueError("Worker stopped.")
            result = json.loads(line)
            if result.get("result") not in ("pass", "fail", "not_checked", "inconclusive") or not isinstance(result.get("rationale"), str):
                raise ValueError("Invalid worker response.")
            return result
        except Empty:
            self.close()
            return {"result": "not_checked", "rationale":
                    "The symbolic worker exceeded its startup limit." if starting else
                    "The symbolic check exceeded its calculation time limit."}
        except (ValueError, OSError):
            self.close()
            return {"result": "inconclusive", "rationale": "The isolated symbolic checker returned no usable result."}


def check_math(spec, timeout_seconds=8):
    with MathWorker(timeout_seconds=timeout_seconds) as worker:
        return worker.check(spec)
