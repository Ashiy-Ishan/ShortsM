"""In-process job tracking for the local ShortsM desktop application."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import Any, Callable
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Job:
    id: str
    status: str = "queued"
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    message: str = "Queued"
    result: dict[str, Any] | None = None
    error: str | None = None
    cancel_event: Event = field(default_factory=Event)
    logs: deque[dict[str, str]] = field(default_factory=lambda: deque(maxlen=300))
    lock: Lock = field(default_factory=Lock)

    def log(self, message: str, level: str = "info") -> None:
        with self.lock:
            self.logs.append({"time": utc_now(), "level": level, "message": message})
            self.message = message

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "job_id": self.id,
                "status": self.status,
                "progress": round(self.progress, 1),
                "speed": self.speed,
                "eta": self.eta,
                "message": self.message,
                "result": self.result,
                "error": self.error,
                "logs": list(self.logs),
            }


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def create(
        self,
        task: Callable[[Job], dict[str, Any]],
    ) -> Job:
        job = Job(id=uuid4().hex)
        job.log("Job queued.")
        with self._lock:
            self._jobs[job.id] = job

        def runner() -> None:
            with job.lock:
                job.status = "running"
            job.log("Job started.")
            try:
                result = task(job)
                with job.lock:
                    if job.cancel_event.is_set():
                        job.status = "cancelled"
                        job.message = "Cancelled by user."
                    elif result.get("error"):
                        job.status = "failed"
                        job.error = result["error"]
                        job.message = result["error"]
                    else:
                        job.status = "completed"
                        job.progress = 100.0
                        job.result = result
                        job.message = "Completed successfully."
                job.log(job.message, "warning" if job.status == "cancelled" else "info")
            except Exception as exc:
                with job.lock:
                    job.status = "failed"
                    job.error = "The job failed unexpectedly."
                job.log(str(exc), "error")

        Thread(target=runner, name=f"shortsm-job-{job.id[:8]}", daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job:
            return False
        with job.lock:
            if job.status not in {"queued", "running"}:
                return False
            job.cancel_event.set()
        job.log("Cancellation requested by user.", "warning")
        return True
