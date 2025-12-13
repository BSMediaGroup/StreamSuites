import json
from pathlib import Path
from threading import Lock

STATE_DIR = Path("shared/state")
JOBS_FILE = STATE_DIR / "jobs.json"

_lock = Lock()


def load_jobs():
    if not JOBS_FILE.exists():
        return {"jobs": []}
    return json.loads(JOBS_FILE.read_text(encoding="utf-8"))


def save_jobs(data: dict):
    with _lock:
        JOBS_FILE.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8"
        )


def append_job(job_record: dict):
    data = load_jobs()
    data["jobs"].append(job_record)
    save_jobs(data)


def update_job(job_id: str, updates: dict):
    data = load_jobs()
    for job in data["jobs"]:
        if job["id"] == job_id:
            job.update(updates)
            break
    save_jobs(data)
