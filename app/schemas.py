"""Pydantic schemas and prompts for the transcription pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DiarizedSegment(BaseModel):
    # Speaker label:
    #   creator        -- the primary on-camera person speaking
    #   ai             -- AI-generated / synthetic / TTS voice
    #   narrator       -- off-camera human voiceover
    #   on-screen-ocr  -- text shown on screen (not spoken aloud)
    #   person1..personN -- additional distinct on-camera people,
    #                       numbered in order of first appearance
    #   other          -- unattributable voice
    speaker: str
    text: str
    originalText: str
    language: str
    languageName: str


class TranscriptionResult(BaseModel):
    text: str
    diarizedTranscript: list[DiarizedSegment]
    audioMode: Literal[
        "spoken-narration", "music-only", "music-with-lyrics", "silent", "mixed",
    ]
    detectedLanguage: str
    detectedLanguageName: str
    languagesUsed: list[str]
    languagesUsedNames: list[str]
    isTranslated: bool


class CreateTranscriptionResponse(BaseModel):
    job_id: str = Field(..., description="Unique transcription job identifier", example="324fbb04-6a02-4a23-9f89-6ad2460d7ecb")
    status: str = Field(..., description="Initial job status", example="PENDING")
    location: str = Field(..., description="URL to fetch job status", example="/transcriptions/324fbb04-6a02-4a23-9f89-6ad2460d7ecb")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "324fbb04-6a02-4a23-9f89-6ad2460d7ecb",
                "status": "PENDING",
                "location": "/transcriptions/324fbb04-6a02-4a23-9f89-6ad2460d7ecb",
            }
        }
    }


class TranscriptionJobStatus(BaseModel):
    job_id: str = Field(..., description="Unique transcription job identifier", example="324fbb04-6a02-4a23-9f89-6ad2460d7ecb")
    status: str = Field(..., description="Current job status", example="RUNNING")
    stage: str = Field(..., description="Current pipeline stage", example="TRANSCRIBING")
    created_at: datetime = Field(..., description="Timestamp when the job was created")
    updated_at: datetime = Field(..., description="Timestamp when the job was last updated")
    result_url: str | None = Field(None, description="URL to fetch the transcription result when complete", example="/transcriptions/324fbb04-6a02-4a23-9f89-6ad2460d7ecb/result")
    error_code: str | None = Field(None, description="Machine-readable error code if job failed", example="TRANSCRIPTION_ERROR")
    error_message: str | None = Field(None, description="Human-readable error message if job failed")
    suggested_action: str | None = Field(None, description="Suggested next action for the caller")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "324fbb04-6a02-4a23-9f89-6ad2460d7ecb",
                "status": "RUNNING",
                "stage": "TRANSCRIBING",
                "created_at": "2026-05-27T10:15:13.112737Z",
                "updated_at": "2026-05-27T10:15:26.222793Z",
                "result_url": None,
                "error_code": None,
                "error_message": None,
                "suggested_action": None,
            }
        }
    }


class ErrorResponse(BaseModel):
    code: str = Field(..., description="Machine-readable error code", example="INVALID_INPUT")
    message: str = Field(..., description="Detailed human-readable error message", example="Please provide either a file upload or a source_url.")
    suggested_action: str | None = Field(None, description="Suggested next action for the caller", example="Send only one of file or source_url.")
    details: dict | None = Field(None, description="Optional structured error details")


class TranscriptionResultResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    result: dict | None = None
    error_code: str | None = None
    error_message: str | None = None
    suggested_action: str | None = None


class TranscriptionResultEnvelope(BaseModel):
    job_id: str = Field(..., description="Unique transcription job identifier", example="324fbb04-6a02-4a23-9f89-6ad2460d7ecb")
    status: str = Field(..., description="Current job status", example="COMPLETED")
    stage: str = Field(..., description="Current pipeline stage", example="FINALIZING")
    result: TranscriptionResult | None = Field(None, description="Structured transcription output according to the TranscriptionResult schema")
    error_code: str | None = Field(None, description="Machine-readable error code if job failed")
    error_message: str | None = Field(None, description="Human-readable error message if job failed")
    suggested_action: str | None = Field(None, description="Suggested next action for the caller")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "324fbb04-6a02-4a23-9f89-6ad2460d7ecb",
                "status": "COMPLETED",
                "stage": "FINALIZING",
                "result": {
                    "text": "Hello world",
                    "diarizedTranscript": [
                        {
                            "speaker": "creator",
                            "text": "Hello world",
                            "originalText": "Hello world",
                            "language": "en",
                            "languageName": "English",
                        }
                    ],
                    "audioMode": "spoken-narration",
                    "detectedLanguage": "en",
                    "detectedLanguageName": "English",
                    "languagesUsed": ["en"],
                    "languagesUsedNames": ["English"],
                    "isTranslated": False,
                },
                "error_code": None,
                "error_message": None,
                "suggested_action": None,
            }
        }
    }

class UsageResponse(BaseModel):
    api_key_id: str = Field(..., description="The unique ID of the API key")
    label: str | None = Field(None, description="The label given to the key")
    usage_count: int = Field(..., description="Total number of jobs submitted")
    quota: int | None = Field(None, description="Maximum number of jobs allowed (if any)")
    remaining_quota: int | None = Field(None, description="Number of jobs remaining before hitting quota")
    tokens: float = Field(..., description="Current rate limiting tokens available (max 60, refills at 1/sec)")
    last_used_at: datetime | None = Field(None, description="When the key was last used")

    # Token cost schedule — lets agents plan their call patterns programmatically
    token_cost_submit: float = Field(5.0, description="Token cost to submit a transcription job (POST /transcriptions)")
    token_cost_result: float = Field(1.0, description="Token cost to fetch a completed result (GET /transcriptions/{id}/result)")
    token_cost_poll: float = Field(0.5, description="Token cost to poll job status or list jobs")
    token_cost_health: float = Field(0.0, description="Token cost for health/schema endpoints (free)")
