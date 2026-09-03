from fastapi import BackgroundTasks

from app.core import jobs


def _job(project_id: int, job_id: int) -> None:
    pass


def test_inline_dispatch_schedules_background_task(monkeypatch):
    monkeypatch.setattr(jobs.settings, "job_queue_backend", "inline")
    background = BackgroundTasks()
    queue_id = jobs.dispatch_recon_job(background, _job, 4, 9)
    assert queue_id == "inline:9"
    assert len(background.tasks) == 1


def test_unknown_queue_backend_fails_explicitly(monkeypatch):
    monkeypatch.setattr(jobs.settings, "job_queue_backend", "mystery")
    background = BackgroundTasks()
    try:
        jobs.dispatch_recon_job(background, _job, 1, 2)
        assert False, "Expected queue configuration failure"
    except jobs.QueueUnavailableError as exc:
        assert "Unknown job queue backend" in str(exc)


def test_queue_health_reports_redis_failure(monkeypatch):
    class BrokenRedis:
        def ping(self):
            raise ConnectionError("redis unavailable")
    monkeypatch.setattr(jobs.settings, "job_queue_backend", "rq")
    monkeypatch.setattr(jobs, "_redis", lambda: BrokenRedis())
    health = jobs.queue_health()
    assert health["backend"] == "rq"
    assert health["available"] is False
    assert "redis unavailable" in health["error"]
