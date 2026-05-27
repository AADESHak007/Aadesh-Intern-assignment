from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from db import get_pool
from uuid import UUID

# The API key header that agents must send
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)

# 60 requests per minute configuration
RPM_LIMIT = 60.0
REFILL_RATE = RPM_LIMIT / 60.0 # tokens per second
MAX_TOKENS = 60.0

async def verify_and_rate_limit(api_key: str = Security(API_KEY_HEADER)) -> UUID:
    """
    Verifies the API key and applies Postgres-backed token bucket rate limiting.
    Returns the api_key_id if successful.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # We need to lock the row for update to prevent race conditions in rate limiting
        query = """
            SELECT id, revoked, usage_count, quota, tokens, last_refill 
            FROM api_keys 
            WHERE api_key = $1 
            FOR UPDATE
        """
        record = await conn.fetchrow(query, api_key)
        
        if not record:
            raise HTTPException(status_code=401, detail="Invalid API Key")
            
        if record["revoked"]:
            raise HTTPException(status_code=401, detail="API Key has been revoked")
            
        if record["quota"] is not None and record["usage_count"] >= record["quota"]:
            raise HTTPException(status_code=402, detail="API Key quota exceeded")

        # Rate limiting logic (Token Bucket)
        now_query = "SELECT now() AT TIME ZONE 'UTC'"
        now_record = await conn.fetchrow(now_query)
        now = now_record[0].replace(tzinfo=None)
        
        last_refill = record["last_refill"].replace(tzinfo=None)
        elapsed_seconds = (now - last_refill).total_seconds()
        
        tokens = record["tokens"]
        
        # Refill tokens
        tokens = min(MAX_TOKENS, tokens + elapsed_seconds * REFILL_RATE)
        
        if tokens < 1.0:
            # Not enough tokens, update only the refill calculations without consuming
            await conn.execute(
                "UPDATE api_keys SET tokens = $1, last_refill = now() WHERE id = $2",
                tokens, record["id"]
            )
            raise HTTPException(status_code=429, detail="Too Many Requests. Rate limit exceeded.")
            
        # Consume 1 token, update last_used_at, and increment usage_count
        tokens -= 1.0
        await conn.execute(
            "UPDATE api_keys SET tokens = $1, last_refill = now(), last_used_at = now(), usage_count = usage_count + 1 WHERE id = $2",
            tokens, record["id"]
        )
        
        return record["id"]
