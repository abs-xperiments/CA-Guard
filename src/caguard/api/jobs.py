"""Analysing a ledger in the background, with stages a reviewer can watch.

A full year's ledger takes ten seconds or more to analyse. A request that
simply hangs for that long reads as broken, and a reverse proxy may give up on
it. So an upload returns a job straight away and the workspace polls it,
showing which stage the work has reached.

Jobs live in memory and run on a small fixed pool. Two workers is deliberate:
analysis is CPU- and memory-heavy, and three large ledgers at once should
queue rather than exhaust the machine. A restart forgets unfinished jobs; the
reviewer simply uploads again, and nothing half-done was ever stored.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeVar

from fastapi import HTTPException

from caguard.observability import event

logger = logging.getLogger("caguard.jobs")

#: The stages an upload passes through, in order, as a reviewer reads them.
STAGES: tuple[tuple[str, str], ...] = (
    ("reading", "Reading the file"),
    ("mapping", "Recognising the columns"),
    ("analysing", "Analysing every voucher"),
    ("keeping", "Keeping the original"),
)
STAGE_KEYS = tuple(key for key, _ in STAGES)

#: Finished jobs are forgotten after this long; the engagement itself remains.
KEEP_FINISHED_SECONDS = 60 * 60

#: Analyses one account may have queued or running at once. Each holds an
#: upload of up to 200 MB on disk and, once running, the ledger in memory.
MAX_IN_FLIGHT_PER_ACCOUNT = 2


class TooBusyError(RuntimeError):
    """This account already has as many analyses in progress as it may."""


Progress = Callable[[str], None]
T = TypeVar("T")


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    owner_id: str
    state: JobState = JobState.QUEUED
    stage: str | None = None
    engagement_id: str | None = None
    #: A message written for the reviewer. Never an internal exception.
    error: str | None = None
    created: float = field(default_factory=time.monotonic)
    finished: float | None = None

    @property
    def elapsed(self) -> float:
        return (self.finished or time.monotonic()) - self.created


class JobRunner:
    """A bounded pool of background analyses, and their status."""

    def __init__(self, workers: int = 2) -> None:
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="caguard-job")
        self._jobs: dict[str, Job] = {}
        self._in_flight: dict[str, int] = {}
        self._lock = threading.Lock()

    def submit(self, owner_id: str, work: Callable[[Progress], str]) -> Job:
        """Start ``work``, which reports stages and returns an engagement id."""
        job = Job(id=secrets.token_hex(8), owner_id=owner_id)
        with self._lock:
            self._prune()
            self._claim(owner_id)
            self._jobs[job.id] = job
        self._pool.submit(self._run, job, work)
        return job

    def run(self, owner_id: str, work: Callable[[], T]) -> T:
        """Run ``work`` on the same bounded pool and wait for it.

        For the one-request upload kept for scripts: it shares the pool and the
        per-account limit, so it cannot be used to sidestep either.
        """
        with self._lock:
            self._claim(owner_id)
        try:
            return self._pool.submit(work).result()
        finally:
            with self._lock:
                self._in_flight[owner_id] -= 1

    def _claim(self, owner_id: str) -> None:
        """Count one more analysis for this account, or refuse. Caller holds the lock."""
        if self._in_flight.get(owner_id, 0) >= MAX_IN_FLIGHT_PER_ACCOUNT:
            raise TooBusyError(
                "Two ledgers are already being analysed for this account. Wait for one to "
                "finish, then upload again."
            )
        self._in_flight[owner_id] = self._in_flight.get(owner_id, 0) + 1

    def get(self, job_id: str, owner_id: str) -> Job | None:
        """A job, but only for the account that started it."""
        with self._lock:
            job = self._jobs.get(job_id)
        return job if job is not None and job.owner_id == owner_id else None

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _run(self, job: Job, work: Callable[[Progress], str]) -> None:
        job.state = JobState.RUNNING

        def progress(stage: str) -> None:
            job.stage = stage

        try:
            job.engagement_id = work(progress)
            job.state = JobState.DONE
        except HTTPException as exc:
            # Already written for the reviewer: an unreadable file, a missing column.
            job.error = str(exc.detail)
            job.state = JobState.FAILED
        except Exception as exc:
            error_id = secrets.token_hex(4)
            event(
                logger,
                "job.failed",
                logging.ERROR,
                job=job.id,
                error_id=error_id,
                error_type=type(exc).__name__,
            )
            job.error = (
                "The analysis could not be completed. Nothing was saved. "
                f"Error reference: {error_id}."
            )
            job.state = JobState.FAILED
        finally:
            job.finished = time.monotonic()
            with self._lock:
                self._in_flight[job.owner_id] -= 1

    def _prune(self) -> None:
        now = time.monotonic()
        stale = [
            key
            for key, job in self._jobs.items()
            if job.finished is not None and now - job.finished > KEEP_FINISHED_SECONDS
        ]
        for key in stale:
            del self._jobs[key]
