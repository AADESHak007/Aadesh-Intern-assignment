from __future__ import annotations

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from db import get_pool
from uuid import UUID

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)

# Token bucket: max 60 tokens, refilling at 1 token/second (= 60 RPM ceiling)
MAX_TOKENS: float = 60.0
REFILL_RATE: float = 1.0  # tokens per second

# ---------------------------------------------------------------------------
# Request weight classes
# ---------------------------------------------------------------------------
# Each endpoint is assigned a cost that reflects its true upstream impact.
#
#   READ        0.0  — free reads (health checks, schema discovery)
#   LIGHTWEIGHT 0.5  — cheap reads (poll status, list jobs, fetch usage)
#   STANDARD    1.0  — normal ops (fetch completed result)
#   HEAVY       5.0  — triggers Gemini + Chirp 3 pipeline (submit job)
#
# With a 60-token bucket:
#   HEAVY:       max 12 submissions/min at full burst
#   STANDARD:    max 60 result fetches/min
#   LIGHTWEIGHT: max 120 polls/min
#   READ:        unlimited

TOKEN_COST_READ: float = 0.0
TOKEN_COST_LIGHTWEIGHT: float = 0.5
TOKEN_COST_STANDARD: float = 1.0
TOKEN_COST_HEAVY: float = 5.0


# ---------------------------------------------------------------------------
# Dependency factory
# ---------------------------------------------------------------------------

def require_tokens(cost: float = TOKEN_COST_STANDARD):
    """
    Dependency factory that creates a FastAPI `Depends`-compatible callable
    consuming `cost` tokens from the API key's token bucket.

    Usage:
        api_key_id: UUID = Depends(require_tokens(TOKEN_COST_HEAVY))

    A cost of 0.0 still validates and authenticates the key but does not
    deduct any tokens — useful for health checks and schema endpoints.
    """
    async def _verify(api_key: str = Security(API_KEY_HEADER)) -> UUID:
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                record = await conn.fetchrow(
                    """
                    SELECT id, revoked, usage_count, quota, tokens, last_refill
                    FROM api_keys
                    WHERE api_key = $1
                    FOR UPDATE
                    """,
                    api_key,
                )

                if not record:
                    raise HTTPException(status_code=401, detail="Invalid API Key")

                if record["revoked"]:
                    raise HTTPException(status_code=401, detail="API Key has been revoked")

                if record["quota"] is not None and record["usage_count"] >= record["quota"]:
                    raise HTTPException(status_code=402, detail="API Key quota exceeded")

                # Free-cost endpoints: only authenticate, no token deduction
                if cost == 0.0:
                    return record["id"]

                # Refill token bucket based on elapsed time
                now_row = await conn.fetchrow("SELECT now() AT TIME ZONE 'UTC'")
                now = now_row[0].replace(tzinfo=None)
                last_refill = record["last_refill"].replace(tzinfo=None)
                elapsed = (now - last_refill).total_seconds()

                tokens = min(MAX_TOKENS, record["tokens"] + elapsed * REFILL_RATE)

                if tokens < cost:
                    # Persist refill progress even on rejection
                    await conn.execute(
                        "UPDATE api_keys SET tokens = $1, last_refill = now() WHERE id = $2",
                        tokens,
                        record["id"],
                    )
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            f"Rate limit exceeded. This endpoint costs {cost} token(s); "
                            f"you have {tokens:.2f} available. "
                            f"Tokens refill at {REFILL_RATE} per second."
                        ),
                    )

                # Consume tokens and record usage
                tokens -= cost
                await conn.execute(
                    """
                    UPDATE api_keys
                    SET tokens = $1, last_refill = now(), last_used_at = now(),
                        usage_count = usage_count + 1
                    WHERE id = $2
                    """,
                    tokens,
                    record["id"],
                )

                return record["id"]

    return _verify


# ---------------------------------------------------------------------------
# Backwards-compatible alias (used by any code that still imports this directly)
# ---------------------------------------------------------------------------
verify_and_rate_limit = require_tokens(TOKEN_COST_STANDARD)
