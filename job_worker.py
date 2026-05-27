from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import requests

from config import UPLOADS_DIR, log
from job_store import (
    complete_job,
    fail_job,
    get_transcription_job,
    increment_attempts,
    update_job_stage,
)
from transcribe import transcribe


def _notify_callback(callback_url: str, payload: dict[str, Any]) -> None:
    try:
        response = requests.post(callback_url, json=payload, timeout=10)
        response.raise_for_status()
        log(f"callback succeeded for {payload.get('job_id')} -> {callback_url}")
    except Exception as exc:
        log(f"callback failed for {payload.get('job_id')} -> {callback_url}: {exc}")


async def process_transcription_job(job_id: str) -> None:
    job = await get_transcription_job(job_id)
    if job is None:
        log(f"process_transcription_job: job not found {job_id}")
        return

    if job["status"] != "PENDING":
        log(f"process_transcription_job: skipping job {job_id} with status {job['status']}")
        return

    await increment_attempts(job_id)

    source_type = job["source_type"]
    source_url = job.get("source_url")
    filename = job.get("filename")
    model = job.get("model")
    callback_url = job.get("callback_url")

    if source_type == "UPLOAD":
        if not filename:
            await fail_job(
                job_id,
                error_code="INVALID_UPLOAD",
                error_message="Uploaded job is missing a filename.",
                suggested_action="Re-upload the file and try again.",
            )
            return
        source_path = UPLOADS_DIR / filename
        await update_job_stage(job_id, "CONVERTING")
        input_path = str(source_path)
        media_url = None
    else:
        await update_job_stage(job_id, "DOWNLOADING")
        input_path = None
        media_url = source_url

    await update_job_stage(job_id, "TRANSCRIBING")

    try:
        result = await asyncio.to_thread(
            transcribe,
            input_path,
            media_url,
            model,
        )

        if not result or not isinstance(result, dict):
            raise RuntimeError("Transcription pipeline returned an invalid result.")

        await complete_job(job_id, result)

        if callback_url:
            payload = {
                "job_id": job_id,
                "status": "COMPLETED",
                "result_url": f"/transcriptions/{job_id}/result",
            }
            await asyncio.to_thread(_notify_callback, callback_url, payload)

    except Exception as exc:
        await fail_job(
            job_id,
            error_code="TRANSCRIPTION_ERROR",
            error_message=str(exc),
            suggested_action="Verify the source input and AI pipeline configuration.",
        )
        if callback_url:
            payload = {
                "job_id": job_id,
                "status": "FAILED",
                "error_message": str(exc),
            }
            await asyncio.to_thread(_notify_callback, callback_url, payload)
