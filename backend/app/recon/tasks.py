"""Synchronous worker entry points for recon jobs."""
import asyncio

from app.recon.service import run_recon


def run_recon_job(project_id: int, job_id: int) -> None:
    asyncio.run(run_recon(project_id, job_id))
