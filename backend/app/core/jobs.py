"""Background job dispatch with explicit inline and Redis/RQ backends."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import BackgroundTasks
from redis import Redis
from rq import Queue
from rq.job import Job

from app.core.config import settings


class QueueUnavailableError(RuntimeError):
    pass


def _redis() -> Redis:
    return Redis.from_url(
        settings.redis_url, socket_connect_timeout=1.5, socket_timeout=1.5,
        health_check_interval=30,
    )


def dispatch_recon_job(
    background_tasks: BackgroundTasks,
    function: Callable[..., Any],
    project_id: int,
    recon_job_id: int,
) -> str:
    backend = settings.job_queue_backend.lower()
    if backend == "inline":
        background_tasks.add_task(function, project_id, recon_job_id)
        return f"inline:{recon_job_id}"
    if backend != "rq":
        raise QueueUnavailableError(f"Unknown job queue backend '{settings.job_queue_backend}'.")
    try:
        connection = _redis()
        connection.ping()
        queue = Queue(settings.recon_queue_name, connection=connection)
        rq_job = queue.enqueue(
            function,
            project_id,
            recon_job_id,
            job_id=f"vajra-recon-{recon_job_id}",
            job_timeout=settings.recon_job_timeout_seconds,
            result_ttl=3600,
            failure_ttl=7 * 24 * 3600,
        )
        return rq_job.id
    except Exception as exc:
        raise QueueUnavailableError(f"Redis/RQ queue is unavailable: {exc}") from exc


def cancel_recon_job(queue_job_id: str | None) -> bool:
    if not queue_job_id or settings.job_queue_backend.lower() != "rq":
        return False
    try:
        job = Job.fetch(queue_job_id, connection=_redis())
        job.cancel()
        return True
    except Exception as exc:
        raise QueueUnavailableError(f"Could not cancel queued job: {exc}") from exc


def queue_health() -> dict[str, Any]:
    backend = settings.job_queue_backend.lower()
    if backend == "inline":
        return {"backend": "inline", "available": True, "queued": None, "workers": None}
    if backend != "rq":
        return {"backend": backend, "available": False, "error": "Unknown queue backend."}
    try:
        connection = _redis()
        connection.ping()
        queue = Queue(settings.recon_queue_name, connection=connection)
        return {"backend": "rq", "available": True, "queued": len(queue), "queue": queue.name}
    except Exception as exc:
        return {"backend": "rq", "available": False, "error": str(exc) or type(exc).__name__}
