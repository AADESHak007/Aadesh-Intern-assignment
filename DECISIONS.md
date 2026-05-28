# Decisions

## 1) API pattern for 10–60s jobs
- We chose an async job pattern: `POST /transcriptions` -> poll `GET /transcriptions/{job_id}` -> fetch `GET /transcriptions/{job_id}/result/raw`.
- Why: simple for agents, resilient to timeouts, and easy to retry.
- We also support optional `callback_url` for webhook-style completion.

## 2) Framework and overall stack
- **FastAPI** for typed schemas, automatic OpenAPI, and clean async support.
- **PostgreSQL + asyncpg** for durable jobs, key management, quota, and usage tracking.
- **Background worker flow** in-app for processing pipeline stages.
- Why this stack: fast to ship, production-proven, and very agent-friendly via schema-first design.

## 3) File handling up to 100MB
- We stream uploads in chunks and enforce max size during write.
- We support URL-based ingestion to avoid forcing file upload from every client.
- Why: prevents memory spikes and gives agents two reliable ingestion options.

## 4) Error design for agents
- We standardized errors as: `code`, `message`, `suggested_action`, optional `details`.
- We return meaningful status codes (`400`, `401`, `402`, `404`, `409`, `413`, `429`, `500`).
- Why: agents need machine-readable failure types plus next-step hints for retry logic.

## 5) OpenAPI quality
- OpenAPI is exposed at `/openapi.json` with typed models and examples.
- Security is documented via `X-API-Key` apiKey scheme.
- Why: an agent should be able to integrate from the spec alone.

## 6) llms.txt and discoverability
- We added `llms.txt` with exact workflow, auth model, rate-limit expectations, and key bootstrap.
- Why: gives LLM agents a short, practical “how to use this API” playbook.

## 7) MCP support
- We integrated an MCP server mount (`/mcp`) in the app.
- Why: direct tool-style integration for agent ecosystems that consume MCP.

## 8) Well-known metadata
- Implemented `/.well-known/openapi.json` and `/.well-known/ai-plugin.json`.
- Why: improves automated discovery by clients and agent tooling.

## 9) API key issuance
- Added `POST /api-keys` for self-serve key creation (no manual intervention needed).
- Default quota is **25** if not provided.
- Why: aligns with “agent-first” onboarding while staying controlled.

## 10) Rate limiting model
- Token bucket per key: 60-token cap, refill 1 token/sec.
- Endpoint cost weights: heavy submit > result fetch > polling.
- Why: protects expensive upstream calls while keeping polling affordable for agents.

## 11) Usage + quota visibility
- Added `GET /usage` for programmatic quota and token visibility.
- Why: agents can adapt behavior (backoff, throttle, stop) without human dashboards.

## 12) Pricing approach
- We used cost-informed tiers from `PRICING_MODEL.md` based on Gemini + Chirp + infra costs.
- Why: sustainable margin, predictable limits, and realistic free-tier onboarding.

## 13) Deployment choice
- Deployed publicly on Render with a health endpoint (`GET /health`).
- Why: quick operational path for Python + ffmpeg workloads and easy evaluator access.

