from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import os

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, Depends

from config import UPLOADS_DIR
from job_store import create_transcription_job, get_transcription_job, list_recent_jobs
from job_worker import process_transcription_job
from app.auth import verify_and_rate_limit
from uuid import UUID
from app.schemas import (
    CreateTranscriptionResponse,
    ErrorResponse,
    TranscriptionJobStatus,
    TranscriptionResult,
    TranscriptionResultEnvelope,
    UsageResponse,
)

router = APIRouter()


async def save_upload_file(file: UploadFile) -> str:
    suffix = Path(file.filename).suffix or ".bin"
    stored_name = f"{uuid4().hex}{suffix}"
    destination = UPLOADS_DIR / stored_name
    destination.parent.mkdir(parents=True, exist_ok=True)

    max_size = int(os.getenv("MAX_UPLOAD_SIZE", 100 * 1024 * 1024))
    total = 0
    with destination.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_size:
                f.close()
                try:
                    destination.unlink(missing_ok=True)
                except Exception:
                    pass
                raise HTTPException(status_code=413, detail="Uploaded file too large")
            f.write(chunk)
    return stored_name


@router.post(
    "/transcriptions",
    status_code=202,
    response_model=CreateTranscriptionResponse,
    summary="Submit transcription job",
    description="Create a new asynchronous transcription job from a local file upload or a public media URL.",
    responses={
        202: {"description": "Job accepted for processing."},
        400: {"model": ErrorResponse, "description": "Invalid request payload."},
        413: {"model": ErrorResponse, "description": "Uploaded file is too large."},
        500: {"model": ErrorResponse, "description": "Internal server error."},
    },
)
async def create_transcription(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(
        None,
        description="A video or audio file upload. Required if source_url is not provided.",
    ),
    source_url: str | None = Form(
        None,
        description="Public URL to a video/audio file. Required if file is not provided.",
        example="https://example.com/video.mp4",
    ),
    model: str = Form(
        "gemini-2.5-flash",
        description="Gemini model to use for transcription. If omitted, uses gemini-2.5-flash.",
        example="gemini-2.5-flash",
    ),
    callback_url: str | None = Form(
        None,
        description="Optional webhook URL to receive job completion notifications.",
        example="https://example.com/webhook",
    ),
    api_key_id: UUID = Depends(verify_and_rate_limit),
) -> CreateTranscriptionResponse:
    if file is None and not source_url:
        raise HTTPException(status_code=400, detail="Please provide either a file upload or a source_url.")

    if file is not None and source_url:
        raise HTTPException(status_code=400, detail="Provide either file or source_url, not both.")

    if file is not None:
        filename = await save_upload_file(file)
        source_type = "UPLOAD"
        source_value = None
    else:
        filename = None
        source_type = "URL"
        source_value = source_url

    job = await create_transcription_job(
        source_type=source_type,
        source_url=source_value,
        filename=filename,
        model=model,
        callback_url=callback_url,
        api_key_id=str(api_key_id),
    )
    if job is None:
        raise HTTPException(status_code=500, detail="Failed to create transcription job.")

    background_tasks.add_task(process_transcription_job, job["id"])
    location = f"/transcriptions/{job['id']}"
    return CreateTranscriptionResponse(
        job_id=str(job["id"]),
        status=job["status"],
        location=location,
    )


@router.get(
    "/transcriptions",
    response_model=list[TranscriptionJobStatus],
    summary="List recent transcription jobs",
    description="Return a paginated list of recent transcription jobs and their current status.",
    responses={
        200: {"description": "A list of transcription jobs."},
        400: {"model": ErrorResponse, "description": "Invalid query parameters."},
    },
)
async def list_transcriptions(limit: int = 20, api_key_id: UUID = Depends(verify_and_rate_limit)) -> list[TranscriptionJobStatus]:
    jobs = await list_recent_jobs(limit)
    results: list[TranscriptionJobStatus] = []
    for job in jobs:
        result_url = None
        if job["status"] == "COMPLETED":
            result_url = f"/transcriptions/{job['id']}/result"
        results.append(
            TranscriptionJobStatus(
                job_id=str(job["id"]),
                status=job["status"],
                stage=job["stage"],
                created_at=job["created_at"],
                updated_at=job["updated_at"],
                result_url=result_url,
                error_code=job.get("error_code"),
                error_message=job.get("error_message"),
                suggested_action=job.get("suggested_action"),
            )
        )
    return results


@router.get(
    "/transcriptions/{job_id}",
    response_model=TranscriptionJobStatus,
    summary="Get transcription job status",
    description="Return the current processing state of a transcription job.",
    responses={
        200: {"description": "Job status returned."},
        404: {"model": ErrorResponse, "description": "Job not found."},
    },
)
async def get_transcription_status(job_id: str, api_key_id: UUID = Depends(verify_and_rate_limit)) -> TranscriptionJobStatus:
    job = await get_transcription_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result_url = None
    if job["status"] == "COMPLETED":
        result_url = f"/transcriptions/{job_id}/result"

    return TranscriptionJobStatus(
        job_id=str(job["id"]),
        status=job["status"],
        stage=job["stage"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        result_url=result_url,
        error_code=job.get("error_code"),
        error_message=job.get("error_message"),
        suggested_action=job.get("suggested_action"),
    )


@router.get(
    "/transcriptions/{job_id}/result",
    response_model=TranscriptionResultEnvelope,
    summary="Fetch transcription result",
    description="Return the structured transcription output for a completed job, including diarized transcript segments.",
    responses={
        200: {"description": "Transcription result returned."},
        202: {"description": "Job is still processing."},
        404: {"model": ErrorResponse, "description": "Job not found."},
    },
)
async def get_transcription_result(job_id: str, api_key_id: UUID = Depends(verify_and_rate_limit)) -> TranscriptionResultEnvelope:
    job = await get_transcription_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "FAILED":
        return TranscriptionResultEnvelope(
            job_id=str(job["id"]),
            status=job["status"],
            stage=job["stage"],
            result=None,
            error_code=job.get("error_code"),
            error_message=job.get("error_message"),
            suggested_action=job.get("suggested_action"),
        )

    if job["status"] != "COMPLETED":
        raise HTTPException(status_code=202, detail="Job is still processing")

    result_obj = None
    raw = job.get("result")
    if raw is not None:
        try:
            if isinstance(raw, dict):
                result_obj = TranscriptionResult.model_validate(raw)
            else:
                import json as _json

                result_obj = TranscriptionResult.model_validate(_json.loads(raw))
        except Exception:
            return TranscriptionResultEnvelope(
                job_id=str(job["id"]),
                status=job["status"],
                stage=job["stage"],
                result=None,
                error_code="RESULT_PARSE_ERROR",
                error_message="Stored transcription result could not be parsed into TranscriptionResult schema.",
                suggested_action="Inspect raw result payload in the database.",
            )

    return TranscriptionResultEnvelope(
        job_id=str(job["id"]),
        status=job["status"],
        stage=job["stage"],
        result=result_obj,
        error_code=job.get("error_code"),
        error_message=job.get("error_message"),
        suggested_action=job.get("suggested_action"),
    )


@router.get(
    "/transcriptions/{job_id}/result/raw",
    response_model=TranscriptionResult,
    summary="Fetch raw transcription result",
    description="Return the exact structured transcription output without the status envelope.",
    responses={
        200: {"description": "Transcription result returned."},
        202: {"description": "Job is still processing."},
        404: {"model": ErrorResponse, "description": "Job not found."},
        409: {"model": ErrorResponse, "description": "Job failed."},
    },
)
async def get_raw_transcription_result(job_id: str, api_key_id: UUID = Depends(verify_and_rate_limit)) -> TranscriptionResult:
    job = await get_transcription_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "FAILED":
        raise HTTPException(status_code=409, detail=f"Job failed: {job.get('error_message')}")

    if job["status"] != "COMPLETED":
        raise HTTPException(status_code=202, detail="Job is still processing")

    raw = job.get("result")
    if raw is None:
        raise HTTPException(status_code=404, detail="Result not found in completed job")

    try:
        if isinstance(raw, dict):
            return TranscriptionResult.model_validate(raw)
        else:
            import json as _json
            return TranscriptionResult.model_validate(_json.loads(raw))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse result: {e}")


@router.get(
    "/schemas/transcription-result",
    summary="Get TranscriptionResult JSON Schema",
    description="Return the JSON schema for the TranscriptionResult object, useful for programmatic clients.",
)
async def get_transcription_result_schema() -> dict:
    return TranscriptionResult.model_json_schema()


@router.get(
    "/usage",
    response_model=UsageResponse,
    summary="Get API Key Usage",
    description="Fetch your current API key usage, remaining quota, and available rate limit tokens.",
)
async def get_api_usage(api_key_id: UUID = Depends(verify_and_rate_limit)) -> UsageResponse:
    from db import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, label, usage_count, quota, tokens, last_used_at FROM api_keys WHERE id = $1",
            api_key_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="API Key not found")
        
        remaining = None
        if row["quota"] is not None:
            remaining = max(0, row["quota"] - row["usage_count"])
            
        return UsageResponse(
            api_key_id=str(row["id"]),
            label=row["label"],
            usage_count=row["usage_count"],
            quota=row["quota"],
            remaining_quota=remaining,
            tokens=row["tokens"],
            last_used_at=row["last_used_at"],
        )


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
