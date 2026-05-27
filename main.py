from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from config import UPLOADS_DIR
from db import connect_db, disconnect_db
from job_store import create_transcription_job, get_transcription_job, list_recent_jobs
from job_worker import process_transcription_job


class CreateTranscriptionResponse(BaseModel):
    job_id: str = Field(..., description="Unique transcription job identifier")
    status: str = Field(..., description="Initial job status")
    location: str = Field(..., description="URL to fetch job status")


class TranscriptionJobStatus(BaseModel):
    job_id: str
    status: str
    stage: str
    created_at: datetime
    updated_at: datetime
    result_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    suggested_action: str | None = None


class TranscriptionResultResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    result: dict | None = None
    error_code: str | None = None
    error_message: str | None = None
    suggested_action: str | None = None


app = FastAPI(
    title="Agent-First Transcription API",
    description="Asynchronous transcription service for video/audio inputs.",
    version="0.1.0",
)


@app.on_event("startup")
async def startup_event() -> None:
    await connect_db()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await disconnect_db()


async def save_upload_file(file: UploadFile) -> str:
    suffix = Path(file.filename).suffix or ".bin"
    stored_name = f"{uuid4().hex}{suffix}"
    destination = UPLOADS_DIR / stored_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    contents = await file.read()
    destination.write_bytes(contents)
    return stored_name


@app.post("/transcriptions", status_code=202, response_model=CreateTranscriptionResponse)
async def create_transcription(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    source_url: str | None = Form(None),
    model: str = Form("gemini-2.5-flash"),
    callback_url: str | None = Form(None),
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


@app.get("/transcriptions", response_model=list[TranscriptionJobStatus])
async def list_transcriptions(limit: int = 20) -> list[TranscriptionJobStatus]:
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


@app.get("/transcriptions/{job_id}", response_model=TranscriptionJobStatus)
async def get_transcription_status(job_id: str) -> TranscriptionJobStatus:
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


@app.get("/transcriptions/{job_id}/result", response_model=TranscriptionResultResponse)
async def get_transcription_result(job_id: str) -> TranscriptionResultResponse:
    job = await get_transcription_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "FAILED":
        return TranscriptionResultResponse(
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

    return TranscriptionResultResponse(
        job_id=str(job["id"]),
        status=job["status"],
        stage=job["stage"],
        result=job.get("result"),
        error_code=job.get("error_code"),
        error_message=job.get("error_message"),
        suggested_action=job.get("suggested_action"),
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
