"""Run the Redis/RQ recon worker: python -m app.worker"""
from redis import Redis
from rq import Worker

from app.core.config import settings
from app.core.database import migrate_database


def main() -> None:
    if settings.job_queue_backend.lower() != "rq":
        raise SystemExit("Set VAJRA_JOB_QUEUE_BACKEND=rq before starting a worker.")
    migrate_database()
    connection = Redis.from_url(settings.redis_url)
    worker = Worker([settings.recon_queue_name], connection=connection)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
