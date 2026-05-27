from __future__ import annotations

import asyncio
import os
import secrets

from db import connect_db, disconnect_db, execute, fetchrow


async def seed() -> None:
    await connect_db()
    try:
        api_key = f"test_{secrets.token_hex(12)}"
        api_key_label = "local-seed"
        api_key_row = await fetchrow(
            "INSERT INTO api_keys (api_key, label) VALUES ($1, $2) RETURNING id, api_key, label, created_at",
            api_key,
            api_key_label,
        )
        print("Created API key:", dict(api_key_row) if api_key_row else None)

        job_row = await fetchrow(
            "INSERT INTO transcription_jobs (source_type, source_url, filename, model, callback_url, api_key_id) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
            "URL",
            "https://example.com/audio.mp4",
            None,
            "gemini-2.5-flash",
            None,
            api_key_row["id"] if api_key_row else None,
        )
        print("Created transcription job:", dict(job_row) if job_row else None)
    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(seed())
