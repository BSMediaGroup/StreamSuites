import json
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from shared.logging.logger import get_logger
from shared.storage.state_publisher import DashboardStatePublisher

_STATE_DIR = Path("shared/state")
_STATE_PATH = _STATE_DIR / "jobs.json"
_LOCK = Lock()
_PUBLISHER = DashboardStatePublisher(base_dir=_STATE_DIR)
_log = get_logger("shared.state_store")


def _load_state() -> Dict[str, Any]:
    if not _STATE_PATH.exists():
        return {"jobs": [], "triggers": {}}
    try:
        state = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        jobs = state.get("jobs", [])
        for job in jobs:
            job.setdefault("created_at", None)
            job.setdefault("started_at", None)
            job.setdefault("completed_at", None)
            job.setdefault("finished_at", None)
            job.setdefault("updated_at", None)
        return state
    except Exception as e:
        _log.warning(f"Failed to load job state, returning defaults: {e}")
        return {"jobs": [], "triggers": {}}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        _PUBLISHER.publish("jobs.json", state)
    except Exception as e:
        _log.error(f"Failed to persist job state: {e}")


# ------------------------------------------------------------
# EXISTING FUNCTIONS (UNCHANGED)
# ------------------------------------------------------------

def append_job(job: Dict[str, Any]) -> None:
    job.setdefault("updated_at", int(time.time()))
    job.setdefault("started_at", None)
    job.setdefault("completed_at", None)
    job.setdefault("finished_at", None)

    with _LOCK:
        state = _load_state()
        state.setdefault("jobs", []).append(job)
        _save_state(state)


def update_job(job_id: str, updates: Dict[str, Any]) -> None:
    updates = dict(updates)
    updates.setdefault("updated_at", int(time.time()))

    with _LOCK:
        state = _load_state()
        for job in state.get("jobs", []):
            if job.get("id") == job_id:
                job.update(updates)
                break
        _save_state(state)


# ------------------------------------------------------------
# ADDITIVE — READ-ONLY METRICS (SAFE)
# ------------------------------------------------------------

def get_all_jobs() -> List[Dict[str, Any]]:
    with _LOCK:
        return list(_load_state().get("jobs", []))


def get_jobs_for_creator(creator_id: str) -> List[Dict[str, Any]]:
    return [
        job for job in get_all_jobs()
        if job.get("creator_id") == creator_id
    ]


def get_job_metrics() -> Dict[str, Any]:
    jobs = get_all_jobs()

    metrics = {
        "total": len(jobs),
        "by_status": {},
        "by_creator": {},
        "by_type": {},
    }

    for job in jobs:
        status = job.get("status", "unknown")
        creator = job.get("creator_id", "unknown")
        jtype = job.get("type", "unknown")

        metrics["by_status"][status] = metrics["by_status"].get(status, 0) + 1
        metrics["by_type"][jtype] = metrics["by_type"].get(jtype, 0) + 1

        if creator not in metrics["by_creator"]:
            metrics["by_creator"][creator] = {
                "total": 0,
                "by_status": {}
            }

        metrics["by_creator"][creator]["total"] += 1
        metrics["by_creator"][creator]["by_status"][status] = (
            metrics["by_creator"][creator]["by_status"].get(status, 0) + 1
        )

    return metrics


# ------------------------------------------------------------
# ADDITIVE — TRIGGER COOLDOWN STATE (AUTHORITATIVE)
# ------------------------------------------------------------

def get_last_trigger_time(
    creator_id: str,
    trigger_key: str,
) -> float | None:
    """
    Returns epoch seconds of last trigger fire, or None.
    """
    with _LOCK:
        state = _load_state()
        return (
            state
            .get("triggers", {})
            .get(creator_id, {})
            .get(trigger_key)
        )


def record_trigger_fire(
    creator_id: str,
    trigger_key: str,
    now: Optional[float] = None,
) -> None:
    """
    Records the current time as last trigger fire.
    If 'now' is provided, it is used (for deterministic callers).
    """
    ts = now if now is not None else time.time()

    with _LOCK:
        state = _load_state()
        state.setdefault("triggers", {})
        state["triggers"].setdefault(creator_id, {})
        state["triggers"][creator_id][trigger_key] = ts
        _save_state(state)
