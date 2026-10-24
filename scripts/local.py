"""Project-scoped Windows development services; no system service installation."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
VAR = ROOT / "var"
PYTHON = ROOT / ".venv/Scripts/python.exe"
PG = ROOT / ".runtime/pgsql/bin"
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, creationflags=FLAGS, **kwargs)


def pg_data():
    file = VAR / "local.json"
    config = json.loads(file.read_text()) if file.exists() else {}
    path = Path(config.get("postgres_data_directory", str(VAR / "postgres"))).resolve()
    if not path.is_relative_to(VAR.resolve()) or not path.name.startswith("postgres"):
        raise SystemExit("The project PostgreSQL data directory must remain inside var/postgres*.")
    return path


def setup():
    VAR.mkdir(exist_ok=True)
    (VAR / "logs").mkdir(exist_ok=True)
    (VAR / "tmp").mkdir(exist_ok=True)
    file = VAR / "local.json"
    if not file.exists():
        password = secrets.token_hex(24)
        file.write_text(json.dumps({
            "secret_key": secrets.token_urlsafe(64),
            "database_password": password,
            "database_url": f"postgresql://pastpaper:{password}@127.0.0.1:54329/pastpaper",
            "local_access": True,
        }, indent=2))
    config = json.loads(file.read_text())
    port = str(urlparse(config["database_url"]).port or 54329)
    if not (PG / "initdb.exe").exists():
        raise SystemExit("PostgreSQL archive missing. Run scripts/fetch_postgres.py first.")
    data = pg_data()
    if not (data / "PG_VERSION").exists():
        password_file = VAR / "postgres-password.tmp"
        password_file.write_text(config["database_password"])
        try:
            run([PG / "initdb.exe", "-D", data, "-U", "pastpaper", "--encoding=UTF8",
                 "--locale=C", "--auth=scram-sha-256", f"--pwfile={password_file}"])
        finally:
            password_file.unlink(missing_ok=True)
        with (data / "postgresql.conf").open("a") as stream:
            stream.write(f"\nlisten_addresses='127.0.0.1'\nport={port}\nmax_connections=30\n")
    pg_start()
    env = dict(os.environ, PGPASSWORD=config["database_password"])
    exists = subprocess.run([str(PG / "psql.exe"), "-h", "127.0.0.1", "-p", port,
                             "-U", "pastpaper", "-d", "postgres", "-tAc",
                             "SELECT 1 FROM pg_database WHERE datname='pastpaper'"],
                            capture_output=True, text=True, env=env, creationflags=FLAGS, check=True)
    if exists.stdout.strip() != "1":
        run([PG / "createdb.exe", "-h", "127.0.0.1", "-p", port, "-U", "pastpaper", "pastpaper"], env=env)
    print(f"Local PostgreSQL ready on 127.0.0.1:{port}. Private settings: var/local.json")


def pg_start():
    result = subprocess.run([str(PG / "pg_ctl.exe"), "-D", str(pg_data()), "status"],
                            capture_output=True, creationflags=FLAGS)
    if result.returncode:
        # A previous Windows/OneDrive log handle can remain locked after shutdown.
        # Preserve it and open a distinct log for each start.
        log_path = VAR / "logs" / f"postgres-{time.time_ns()}.log"
        run([PG / "pg_ctl.exe", "-D", pg_data(), "-l", log_path, "-w", "start"])


def services():
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js is required on PATH.")
    return {
        "api": [str(PYTHON), str(ROOT / "backend/manage.py"), "runserver", "127.0.0.1:8000", "--noreload"],
        "worker": [str(PYTHON), str(ROOT / "backend/manage.py"), "procrastinate", "worker"],
        "dispatcher": [str(PYTHON), str(ROOT / "backend/manage.py"), "dispatch_outbox"],
        "web": [node, str(ROOT / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
    }


def process_is_ours(pid, started):
    import psutil
    try:
        p = psutil.Process(pid)
        command = " ".join(p.cmdline()).replace("\\", "/").lower()
        return abs(p.create_time() - started) < 1 and str(ROOT).replace("\\", "/").lower() in command
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def start():
    import psutil
    pg_start()
    pidfile = VAR / "services.json"
    saved = json.loads(pidfile.read_text()) if pidfile.exists() else {}
    for name, command in services().items():
        existing = saved.get(name)
        if existing and process_is_ours(existing["pid"], existing["started"]):
            continue
        log = (VAR / f"logs/{name}.log").open("ab")
        env = dict(os.environ, PYTHONUTF8="1", HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
        p = subprocess.Popen(command, cwd=ROOT / ("frontend" if name == "web" else "backend"),
                             env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                             creationflags=FLAGS)
        saved[name] = {"pid": p.pid, "started": psutil.Process(p.pid).create_time()}
    pidfile.write_text(json.dumps(saved, indent=2))
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:5173/api/v1/session", timeout=2) as response:
                if json.load(response).get("batch") in (1, 2, 3, 4):
                    break
        except (OSError, ValueError):
            time.sleep(0.5)
    else:
        raise SystemExit("Services did not become ready. Inspect var/logs before using the workspace.")
    if any(not process_is_ours(item["pid"], item["started"]) for item in saved.values()):
        raise SystemExit("A service exited during startup. Inspect var/logs.")
    print("Workspace: http://127.0.0.1:5173")
    print("Logs: var/logs; course analysis requires explicit consent for the displayed input scope.")


def restart_api():
    import psutil
    pidfile = VAR / "services.json"
    saved = json.loads(pidfile.read_text()) if pidfile.exists() else {}
    item = saved.get("api")
    if item and process_is_ours(item["pid"], item["started"]):
        process = psutil.Process(item["pid"])
        process.terminate()
        process.wait(timeout=10)
    saved.pop("api", None)
    pidfile.write_text(json.dumps(saved, indent=2))
    start()


def restart_workers():
    """Only replace this project's worker processes while business tasks are idle."""
    import psutil
    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from app.core.models import Task
    if Task.objects.filter(state__in=["queued", "processing"]).exists():
        raise SystemExit("Wait for active tasks to finish or cancel them before restarting workers.")
    pidfile = VAR / "services.json"
    saved = json.loads(pidfile.read_text()) if pidfile.exists() else {}
    for name in ("worker", "dispatcher"):
        item = saved.get(name)
        if item and process_is_ours(item["pid"], item["started"]):
            process = psutil.Process(item["pid"])
            process.terminate()
            process.wait(timeout=10)
        saved.pop(name, None)
    pidfile.write_text(json.dumps(saved, indent=2))
    start()


def stop():
    import psutil
    pidfile = VAR / "services.json"
    if pidfile.exists():
        for item in json.loads(pidfile.read_text()).values():
            if process_is_ours(item["pid"], item["started"]):
                p = psutil.Process(item["pid"])
                for child in p.children(recursive=True):
                    child.terminate()
                p.terminate()
        pidfile.unlink()
    run([PG / "pg_ctl.exe", "-D", pg_data(), "-m", "fast", "-w", "stop"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup", "start", "stop", "restart-api", "restart-workers"])
    command = parser.parse_args().command
    {"setup": setup, "start": start, "stop": stop, "restart-api": restart_api, "restart-workers": restart_workers}[command]()
