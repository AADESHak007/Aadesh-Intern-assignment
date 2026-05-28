# Pricing Model

## Overview

This service wraps an AI transcription pipeline (Google Gemini + Chirp 3 + Whisper) that has real, non-trivial upstream costs per job. The pricing model must:
1. Cover upstream API costs with a healthy margin.
2. Protect the service from abuse and upstream quota exhaustion.
3. Remain competitive with industry peers while being transparent to agents and developers.

---

## Upstream Cost Breakdown (per transcription job)

| Component | Purpose | Estimated Cost |
|---|---|---|
| **Gemini 2.5 Flash** | Structured transcription (audio/video → JSON) | ~$0.01–0.04 per video |
| **Gemini 2.5 Pro** (fallback) | Used when diarization context is sparse | ~$0.03–0.08 per video |
| **Chirp 3** (Google Speech v2) | Speaker diarization (who said what) | ~$0.004–0.016 per minute of audio |
| **Whisper tiny** | Language detection only, runs locally | ~$0.00 (compute only) |
| **Infrastructure** | DB, storage, worker compute | ~$0.002–0.005 per job (amortized) |

**Total upstream cost estimate: $0.02 – $0.08 per job** depending on audio length, model used, and diarization complexity.

---

## Competitor Benchmarking

| Provider | Pricing Model | Price |
|---|---|---|
| **Deepgram** | Per-minute (Nova-3 model) | ~$0.0043/min |
| **AssemblyAI** | Per-hour (Best model) | ~$0.37/hr ($0.006/min) |
| **Google STT v1** | Per-15-second block | ~$0.016/min (standard), $0.024/min (with diarization) |
| **OpenAI Whisper API** | Per-minute | ~$0.006/min |
| **Rev.ai** | Per-minute (async) | ~$0.02/min |



This service bundles **language detection + diarization + structured transcription** in one call — a feature set that typically costs $0.024+/min on Google STT alone. Our all-in cost target is **~$0.03–0.10 per job** for typical 3–10 minute videos.

---

## Suggested Pricing Tiers

| Tier | Price per Job | Target User |
|---|---|---|
| **Free** | $0.00 (up to 10 jobs/month) | Developers evaluating the service |
| **Pay-as-you-go** | $0.10 per job | Individuals, low-volume agents |
| **Pro** (100 jobs/month) | $8.00/month (~$0.08/job) | Startups, regular agents |
| **Scale** (1,000 jobs/month) | $60.00/month (~$0.06/job) | High-volume agents, businesses |

This is priced at ~2–3× the upstream cost to maintain a sustainable margin while undercutting assembled equivalent solutions (Google STT + Diarization + Gemini separately).

---

## Rate Limiting Model (Token Bucket)

To protect upstream quotas, the service uses a **cost-weighted token bucket**. Each API key starts with 60 tokens that refill at 1 token/second (= 60 tokens/minute ceiling).

Endpoints are priced by their actual compute and upstream impact:

| Endpoint | Weight Class | Token Cost | Effective Limit at Full Burst |
|---|---|---|---|
| `POST /transcriptions` | HEAVY | **5.0** | 12 submissions/min |
| `GET /transcriptions/{id}/result` | STANDARD | **1.0** | 60 fetches/min |
| `GET /transcriptions/{id}` (poll) | LIGHTWEIGHT | **0.5** | 120 polls/min |
| `GET /transcriptions` (list) | LIGHTWEIGHT | **0.5** | 120 list calls/min |
| `GET /usage` | LIGHTWEIGHT | **0.5** | 120 calls/min |
| `GET /health`, `GET /schemas/...` | READ | **0.0** | Unlimited |

### Rationale
- **Submissions are the expensive call.** Each one triggers Gemini + Chirp 3. Charging 5 tokens caps burst at 12 calls/min, which is well within Gemini's ~15,000 RPM quota while still protecting against a single client monopolizing it.
- **Polling is deliberately cheap (0.5).** Agents need to poll many times per job. Penalizing polling would encourage worse behaviour (e.g., long sleep intervals leading to missed completions or excess retries).
- **Health checks are free.** Uptime monitors and service discovery should never compete for tokens.

---

## Future Considerations

- **Per-minute audio pricing:** As usage scales, switching to a per-minute audio pricing model (like Deepgram/AssemblyAI) is more predictable and fair for long-form content.
- **Model tier surcharges:** Charging a small premium for Pro model fallback (Gemini 2.5 Pro) vs. Flash gives cost transparency to callers.
- **Prepaid credits:** Offering prepaid credit packs instead of subscription tiers reduces churn risk and simplifies billing for agent-first integrations.
