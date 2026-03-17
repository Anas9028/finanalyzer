"""
job_manager.py
--------------
In-memory background job tracker for async file upload processing.
No Redis, no Celery — pure Python threading.

Usage in app.py:
    from job_manager import job_manager
    job_id = job_manager.create_job()
    job_manager.start(job_id, target_fn, args=(…,))
    # GET /api/upload/status/<job_id>  → poll from frontend
"""

import threading
import uuid
import time
from datetime import datetime, timezone
from typing import Callable, Any


class Job:
    PENDING   = 'pending'
    RUNNING   = 'running'
    SUCCESS   = 'success'
    FAILED    = 'failed'

    def __init__(self, job_id: str):
        self.job_id     = job_id
        self.status     = self.PENDING
        self.progress   = 0          # 0–100
        self.step       = 'Waiting…'
        self.result     = None       # dict with analysis_id on success
        self.error      = None       # error message on failure
        self.created_at = datetime.now(timezone.utc)

    def update(self, progress: int, step: str):
        self.progress = progress
        self.step     = step

    def to_dict(self) -> dict:
        return {
            'job_id':   self.job_id,
            'status':   self.status,
            'progress': self.progress,
            'step':     self.step,
            'result':   self.result,
            'error':    self.error,
        }


class JobManager:
    """Thread-safe in-memory job registry."""

    def __init__(self, max_jobs: int = 200):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max  = max_jobs

    # ── Public API ────────────────────────────────────────

    def create_job(self) -> str:
        """Register a new job and return its ID."""
        job_id = str(uuid.uuid4())
        with self._lock:
            self._evict_old_jobs()
            self._jobs[job_id] = Job(job_id)
        return job_id

    def start(self, job_id: str, target: Callable, args: tuple = (), kwargs: dict = None):
        """Run *target* in a daemon thread; passes the Job object as first arg."""
        job = self._get(job_id)
        if not job:
            raise ValueError(f'Unknown job: {job_id}')
        job.status = Job.RUNNING
        job.step   = 'Starting…'

        def _run():
            try:
                target(job, *args, **(kwargs or {}))
                # target is responsible for setting job.status = SUCCESS/FAILED
            except Exception as exc:
                job.status = Job.FAILED
                job.error  = str(exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def get_status(self, job_id: str) -> dict | None:
        job = self._get(job_id)
        return job.to_dict() if job else None

    # ── Internal ──────────────────────────────────────────

    def _get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _evict_old_jobs(self):
        """Remove jobs older than 2 hours when pool is full."""
        if len(self._jobs) < self._max:
            return
        cutoff = time.time() - 7200
        to_del = [
            jid for jid, j in self._jobs.items()
            if j.created_at.timestamp() < cutoff
        ]
        for jid in to_del:
            del self._jobs[jid]


# Singleton — import this everywhere
job_manager = JobManager()