"""Configuration, API client singletons, and shared helpers."""

from __future__ import annotations

import datetime
import functools
import json
import os
import pathlib
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Data / cache directories
# ---------------------------------------------------------------------------

CACHE_DIR = pathlib.Path(os.getenv("CACHE_DIR", "cache"))
TRANSCRIPTS = CACHE_DIR / "transcripts"

UPLOADS_DIR = pathlib.Path(os.getenv("UPLOADS_DIR", "uploads"))
for _p in (CACHE_DIR, TRANSCRIPTS, UPLOADS_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Model constants (overridable via env)
# ---------------------------------------------------------------------------

GEMINI_TRANSCRIBE_MODEL_STRONG = os.getenv("GEMINI_TRANSCRIBE_MODEL_STRONG", "gemini-2.5-flash")
GEMINI_TRANSCRIBE_MODEL_PRO = os.getenv("GEMINI_TRANSCRIBE_MODEL_PRO", "gemini-2.5-pro")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(*a):
    print(datetime.datetime.utcnow().strftime("%H:%M:%S"), *a,
          file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Usage tracker
# ---------------------------------------------------------------------------

_PRICING = {
    "gemini-2.5-flash":      {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro":        {"input": 1.25, "output": 10.00},
    "gemini-3.1-flash-lite": {"input": 0.075, "output": 0.30},
}


class UsageTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self._calls = []
            self._by_provider = {}
            self._chirp3_minutes = 0.0
            self._chirp3_cost = 0.0

    def record(self, provider, model, purpose, input_tokens=0, output_tokens=0, latency_ms=0):
        pricing = _PRICING.get(model, {"input": 0, "output": 0})
        cost = input_tokens / 1e6 * pricing["input"] + output_tokens / 1e6 * pricing["output"]
        with self._lock:
            self._calls.append({
                "provider": provider, "model": model, "purpose": purpose,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "cost_usd": round(cost, 6), "latency_ms": round(latency_ms, 1),
            })
            key = f"{provider}/{model}"
            agg = self._by_provider.setdefault(key, {
                "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
            })
            agg["calls"] += 1
            agg["input_tokens"] += input_tokens
            agg["output_tokens"] += output_tokens
            agg["cost_usd"] += cost

    def record_gemini(self, purpose, response=None, model="gemini-2.5-flash", latency_ms=0):
        inp, out = 0, 0
        if response is not None:
            um = getattr(response, "usage_metadata", None)
            if um:
                inp = getattr(um, "prompt_token_count", 0) or 0
                out = getattr(um, "candidates_token_count", 0) or 0
        self.record("google", model, purpose, inp, out, latency_ms)

    def record_chirp3(self, audio_seconds: float):
        """Track Chirp 3 sync usage at $0.016/min."""
        minutes = audio_seconds / 60.0
        cost = minutes * 0.016
        with self._lock:
            self._chirp3_minutes += minutes
            self._chirp3_cost += cost

    def summary(self):
        with self._lock:
            total_cost = sum(a["cost_usd"] for a in self._by_provider.values()) + self._chirp3_cost
            total_calls = sum(a["calls"] for a in self._by_provider.values())
            result = {
                "total_calls": total_calls,
                "total_cost_usd": round(total_cost, 4),
                "by_provider": {
                    k: {**v, "cost_usd": round(v["cost_usd"], 4)}
                    for k, v in self._by_provider.items()
                },
            }
            if self._chirp3_minutes > 0:
                result["chirp3"] = {
                    "minutes": round(self._chirp3_minutes, 1),
                    "cost_usd": round(self._chirp3_cost, 4),
                }
            return result

    def print_summary(self):
        s = self.summary()
        log(f"\n{'=' * 50}")
        log(f"USAGE: {s['total_calls']} API calls, ${s['total_cost_usd']:.4f} total")
        for key, agg in s["by_provider"].items():
            log(f"  {key}: {agg['calls']} calls, "
                f"{agg['input_tokens']:,} in / {agg['output_tokens']:,} out, "
                f"${agg['cost_usd']:.4f}")
        if "chirp3" in s:
            c3 = s["chirp3"]
            log(f"  chirp3-sync: {c3['minutes']:.1f} min, ${c3['cost_usd']:.4f}")
        log(f"{'=' * 50}")


usage_tracker = UsageTracker()


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable: tuple[type[Exception], ...] | None = None,
):
    """Retry on transient API errors with exponential backoff."""
    _RETRYABLE_STATUS_CODES = ("429", "500", "503")

    def _is_retryable(exc: Exception) -> bool:
        if retryable and isinstance(exc, retryable):
            return True
        msg = str(exc).lower()
        if any(code in msg for code in _RETRYABLE_STATUS_CODES):
            return True
        if "rate" in msg or "overloaded" in msg or "timeout" in msg:
            return True
        return False

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if not _is_retryable(exc) or attempt == max_retries - 1:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    log(f"  [retry] {fn.__name__} attempt {attempt + 1}: "
                        f"{exc} — sleeping {delay:.1f}s")
                    time.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Lazy API client singletons
# ---------------------------------------------------------------------------

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

_gemini = None


def get_gemini():
    """Get Gemini client using Vertex AI with Application Default Credentials.

    Uses the same GOOGLE_APPLICATION_CREDENTIALS as Chirp 3.
    """
    global _gemini
    if _gemini is None:
        from google import genai as google_genai
        if not GCP_PROJECT_ID:
            raise RuntimeError("GCP_PROJECT_ID not set")
        _gemini = google_genai.Client(
            vertexai=True,
            project=GCP_PROJECT_ID,
            location=GCP_LOCATION,
        )
    return _gemini


# ---------------------------------------------------------------------------
# Media part helper
# ---------------------------------------------------------------------------

# Gemini Vertex AI caps inline bytes at ~20 MB. Above this threshold we stage
# the file via the Gemini Files API and pass a URI reference instead, which
# avoids loading large files into RAM and hitting the inline size limit.
GEMINI_INLINE_MAX_BYTES: int = int(os.getenv("GEMINI_INLINE_MAX_BYTES", 20 * 1024 * 1024))  # 20 MB


def prepare_media_part(media: pathlib.Path) -> object:
    """Return a Gemini Part for `media`, choosing the right strategy by size.

    - Files < GEMINI_INLINE_MAX_BYTES (default 20 MB): sent inline as bytes.
      Fast, no extra network round-trip.
    - Files >= GEMINI_INLINE_MAX_BYTES: uploaded to Gemini File API first,
      then referenced by URI. This handles files up to 2 GB and prevents
      loading the entire file into server RAM.
    """
    import mimetypes
    from google.genai import types as _types

    mime, _ = mimetypes.guess_type(str(media))
    if not mime:
        mime = "video/mp4"

    file_size = media.stat().st_size

    if file_size < GEMINI_INLINE_MAX_BYTES:
        # Small file: inline bytes path (fast, no API round-trip)
        log(f"  media: inline upload {media.name} ({file_size / 1024:.0f} KB)")
        return _types.Part.from_bytes(data=media.read_bytes(), mime_type=mime)

    # Large file: use Gemini File API staging
    log(f"  media: large file ({file_size / 1024 / 1024:.1f} MB), uploading via File API...")
    try:
        gemini = get_gemini()
        uploaded = gemini.files.upload(
            file=str(media),
            config={"mime_type": mime, "display_name": media.name},
        )
        log(f"  media: File API upload complete → {uploaded.uri}")
        return _types.Part.from_uri(file_uri=uploaded.uri, mime_type=mime)
    except Exception as e:
        # Fallback: try inline anyway (may fail for very large files, but
        # this gives a clearer downstream error than a silent empty result)
        log(f"  media: File API upload failed ({e}), falling back to inline bytes")
        return _types.Part.from_bytes(data=media.read_bytes(), mime_type=mime)
