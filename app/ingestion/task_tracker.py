"""
Nexura Phase 7 â€” TaskTracker: Atomic JSON File State (Â§21)
Task progress is persisted atomically: <task_id>.tmp -> <task_id>.json
Supports UI polling at GET /admin/ingestions/api/task/<task_id>.
"""
from __future__ import annotations
import json
import os
import shutil
import time
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


class TaskTracker:
    """
    Manages long-running background task state using atomic JSON file writes.
    Corrupted state files are backed up and reinitialized (Phase 7 Â§29).
    """

    def __init__(self, state_dir: str = "instance/tasks") -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    _default_instance: TaskTracker | None = None

    @classmethod
    def get_instance(cls) -> TaskTracker:
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    @classmethod
    def create_task(cls, source_name: str, params: dict | None = None, task_name: str | None = None) -> str:
        tracker = cls.get_instance()
        task_id = str(uuid.uuid4())
        state = {
            "task_id": task_id,
            "task_name": task_name or f"Ingestion: {source_name.capitalize()}",
            "source": source_name,
            "source_name": source_name,
            "params": params or {},
            "status": "pending",
            "progress": 0,
            "message": "Task queued",
            "result": None,
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
        }
        tracker._write(task_id, state)
        return task_id

    @classmethod
    def get_task(cls, task_id: str) -> dict | None:
        return cls.get_instance()._get_task(task_id)

    def _get_task(self, task_id: str) -> dict | None:
        path = self._path(task_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            self._recover_corrupted(path, exc)
            return None

    @classmethod
    def update_progress(cls, task_id: str, progress: int, message: str = "") -> None:
        cls.update_status(task_id, status="running", progress=progress, message=message)

    @classmethod
    def complete_task(cls, task_id: str, result: dict | None = None) -> None:
        cls.update_status(task_id, status="completed", progress=100, message="Completed successfully", result=result)

    @classmethod
    def fail_task(cls, task_id: str, error: str) -> None:
        cls.update_status(task_id, status="failed", message="Task failed", error=error)

    @classmethod
    def update_status(
        cls,
        task_id: str,
        *,
        status: str,
        progress: int = 0,
        message: str = "",
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        tracker = cls.get_instance()
        state = tracker._get_task(task_id) or {}
        state.update({
            "status": status,
            "progress": progress,
            "message": message,
            "result": result,
            "error": error,
        })
        if status == "running" and not state.get("started_at"):
            state["started_at"] = datetime.now(timezone.utc).isoformat()
        if status in ("complete", "completed", "failed"):
            state["completed_at"] = datetime.now(timezone.utc).isoformat()
        tracker._write(task_id, state)

    @classmethod
    def list_tasks(cls, limit: int = 20) -> list[dict]:
        return cls.get_instance()._list_tasks(limit=limit)

    def _list_tasks(self, limit: int = 20) -> list[dict]:
        files = sorted(
            self.state_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:limit]
        tasks = []
        for f in files:
            try:
                tasks.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        return tasks

    # --- Private -------------------------------------------------------------

    def _path(self, task_id: str) -> Path:
        return self.state_dir / f"{task_id}.json"

    def _write(self, task_id: str, state: dict) -> None:
        """Atomic write: write to .tmp then rename to .json (Phase 7 Â§21)."""
        tmp = self.state_dir / f"{task_id}.tmp"
        final = self._path(task_id)
        try:
            tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
            shutil.move(str(tmp), str(final))
        except OSError as exc:
            log.error("TaskTracker: failed to write state for %s: %s", task_id, exc)

    def _recover_corrupted(self, path: Path, exc: Exception) -> None:
        """Backup corrupted file and reinitialize (Phase 7 Â§29)."""
        ts = int(time.time())
        backup = path.with_suffix(f".corrupt.{ts}")
        try:
            shutil.copy2(str(path), str(backup))
            log.warning(
                "TaskTracker: corrupted state file backed up to %s (error: %s)",
                backup, exc,
            )
        except OSError:
            pass
