from __future__ import annotations

import json
from typing import Any

from asyncpg import Record

from db import execute, fetch, fetchrow, get_pool


def _record_to_job(record: Record | None) -> dict[str, Any] | None:
    if record is None:
        return None
    job = dict(record)
    if job.get("result") is not None and isinstance(job["result"], str):
        try:
            job["result"] = json.loads(job["result"])
        except json.JSONDecodeError:
            pass
    return job


async def create_transcription_job(
    source_type: str,
    source_url: str | None,
    filename: str | None,
    model: str,
    callback_url: str | None = None,
    api_key_id: str | None = None,
) -> dict[str, Any]:
    query = """
INSERT INTO transcription_jobs
  (source_type, source_url, filename, model, callback_url, api_key_id)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING *
"""
    row = await fetchrow(query, source_type, source_url, filename, model, callback_url, api_key_id)
    return _record_to_job(row)  # type: ignore[return-value]


async def get_transcription_job(job_id: str) -> dict[str, Any] | None:
    query = "SELECT * FROM transcription_jobs WHERE id = $1"
    row = await fetchrow(query, job_id)
    return _record_to_job(row)


async def list_pending_jobs(limit: int = 5) -> list[dict[str, Any]]:
    query = "SELECT * FROM transcription_jobs WHERE status = 'PENDING' ORDER BY created_at LIMIT $1"
    rows = await fetch(query, limit)
    return [dict(row) for row in rows]


async def claim_next_job() -> dict[str, Any] | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
UPDATE transcription_jobs
SET status = 'RUNNING', stage = 'DOWNLOADING', started_at = now(), updated_at = now()
WHERE id = (
  SELECT id FROM transcription_jobs
  WHERE status = 'PENDING'
  ORDER BY created_at
  LIMIT 1
  FOR UPDATE SKIP LOCKED
)
RETURNING *
"""
            )
            return _record_to_job(row)


async def update_job_stage(job_id: str, stage: str) -> None:
    query = "UPDATE transcription_jobs SET stage = $2, updated_at = now() WHERE id = $1"
    await execute(query, job_id, stage)


async def complete_job(job_id: str, result: dict[str, Any]) -> None:
    query = """
UPDATE transcription_jobs
SET status = 'COMPLETED', stage = 'FINALIZING', result = $2, completed_at = now(), updated_at = now()
WHERE id = $1
"""
    await execute(query, job_id, result)


async def fail_job(
    job_id: str,
    error_code: str,
    error_message: str,
    suggested_action: str | None = None,
) -> None:
    query = """
UPDATE transcription_jobs
SET status = 'FAILED', error_code = $2, error_message = $3,
    suggested_action = $4, completed_at = now(), updated_at = now()
WHERE id = $1
"""
    await execute(query, job_id, error_code, error_message, suggested_action)


async def increment_attempts(job_id: str) -> None:
    query = """
UPDATE transcription_jobs
SET attempts = attempts + 1, updated_at = now()
WHERE id = $1
"""
    await execute(query, job_id)
