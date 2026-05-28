import asyncio
from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP
from job_store import create_transcription_job, get_transcription_job, list_recent_jobs
from job_worker import process_transcription_job

mcp = FastMCP("Transcription Server")

@mcp.tool()
async def submit_transcription_job(source_url: str, model: str = "gemini-2.5-flash") -> str:
    """
    Submits a video or audio file URL for transcription processing.
    Note: This bypasses the API key authentication requirement of the main API.
    Returns a string containing the job_id, which must be used with get_job_status to check progress.
    """
    job = await create_transcription_job(
        source_type="URL",
        source_url=source_url,
        filename=None,
        model=model,
        callback_url=None,
    )
    if not job:
        return "Failed to create transcription job."
    
    # Fire and forget the background job
    job_id = str(job["id"])
    asyncio.create_task(process_transcription_job(job_id))
    return f"Job submitted successfully. Job ID: {job_id}"

@mcp.tool()
async def get_job_status(job_id: str) -> str:
    """
    Checks the current status of a transcription job.
    Returns the status (e.g. PENDING, PROCESSING, COMPLETED, FAILED) and the current stage.
    """
    job = await get_transcription_job(job_id)
    if not job:
        return f"Job not found for ID: {job_id}"
    
    return f"Status: {job['status']}, Stage: {job['stage']}"

@mcp.tool()
async def get_job_result(job_id: str) -> str:
    """
    Fetches the final structured transcription result for a completed job.
    Returns the result as a stringified object. For the raw dictionary, use get_raw_job_result.
    """
    job = await get_transcription_job(job_id)
    if not job:
        return f"Job not found for ID: {job_id}"
    
    if job["status"] == "COMPLETED":
        return f"Job completed. Result: {job.get('result')}"
    elif job["status"] == "FAILED":
        return f"Job failed. Error: {job.get('error_message')}"
    else:
        return f"Job is still processing. Current status: {job['status']}"

@mcp.tool()
async def get_raw_job_result(job_id: str) -> Any:
    """
    Fetches the raw structured transcription result object for a completed job.
    Returns the exact JSON dictionary containing the transcribed text and diarization.
    """
    job = await get_transcription_job(job_id)
    if not job:
        return f"Job not found for ID: {job_id}"
    
    if job["status"] == "COMPLETED":
        return job.get("result", {})
    elif job["status"] == "FAILED":
        return f"Job failed. Error: {job.get('error_message')}"
    else:
        return f"Job is still processing. Current status: {job['status']}"

@mcp.tool()
async def list_recent_jobs_tool(limit: int = 10) -> str:
    """
    Returns a list of the most recent transcription jobs and their status.
    """
    jobs = await list_recent_jobs(limit)
    if not jobs:
        return "No recent jobs found."
    
    result = []
    for job in jobs:
        result.append(f"ID: {job['id']}, Status: {job['status']}, Created: {job['created_at']}")
    return "\n".join(result)

@mcp.tool()
async def health_check() -> str:
    """
    Health check endpoint to verify the service is alive.
    """
    return "Service is alive and healthy."
@mcp.tool()
async def get_api_usage(api_key: str) -> str:
    """
    Fetches the current API key usage, remaining quota, and available rate limit tokens.
    Requires the raw API key as input.
    """
    from db import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, label, usage_count, quota, tokens, last_used_at FROM api_keys WHERE api_key = $1",
            api_key
        )
        if not row:
            return "API Key not found or invalid."
        
        remaining = "Unlimited"
        if row["quota"] is not None:
            remaining = str(max(0, row["quota"] - row["usage_count"]))
            
        return (
            f"Label: {row['label']}\n"
            f"Usage: {row['usage_count']} / {row['quota'] if row['quota'] else 'Unlimited'}\n"
            f"Remaining Quota: {remaining}\n"
            f"Rate Limit Tokens Available: {row['tokens']:.2f}\n"
            f"Last Used: {row['last_used_at']}"
        )
