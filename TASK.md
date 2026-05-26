# Intern Assessment: Agent-First Transcription API

## Overview

You are given a working Python transcription pipeline that processes video through multiple stages to produce structured, speaker-diarized transcripts with language detection and translation. Your task is to turn this into a **production-ready, publicly accessible API service designed for AI agent consumption**.

The primary consumers of this API are **AI agents** — LLMs, coding assistants, autonomous workflows, and agentic systems. Human developers will also use it, but agent-friendliness is the priority.

Read `README.md` first to understand the pipeline, then come back here.

---

## What you're building

### Part 1 — API Design

Design and implement API endpoints around the existing pipeline:

- **Submit** a video/audio for transcription (file upload and URL-based)
- **Check status** of a transcription job
- **Retrieve results** once complete

Things to think about:
- The pipeline takes 10–60 seconds per video. A synchronous HTTP request won't scale. What pattern works best for agents calling your API? (polling, webhooks, SSE, long-polling?)
- How do you handle files up to 100MB?
- What error codes and messages make sense when upstream services (Gemini, Chirp 3) fail? Agents need to programmatically understand failures and decide whether to retry.
- How do you expose the full `TranscriptionResult` schema (see `schemas.py`) cleanly?

### Part 2 — Agent Discoverability & Integration

**This is the core of the task.** AI agents should be able to discover your API, understand what it does, and use it — all without human guidance.

Research and implement:

- **OpenAPI specification** at a well-known path (e.g. `/openapi.json`). Every endpoint must have detailed descriptions, typed request/response schemas, and realistic examples. An agent reading only the OpenAPI spec should be able to make a successful API call.
- **`llms.txt`** — research the emerging standard for helping AI agents understand what a website/API offers. Implement it.
- **MCP server** — Model Context Protocol server that exposes the transcription as a tool. Research what MCP is, how agents consume MCP tools, and build one. This is not optional.
- **`/.well-known/` conventions** — what other well-known paths or metadata help agents discover API capabilities?
- **Agent-optimized error responses** — errors should include machine-readable codes, suggested actions (retry, reduce file size, check auth), and links to relevant documentation.
- **SDK / code examples** — can you auto-generate a Python client from your OpenAPI spec? Can agents use it directly?

### Part 3 — Authentication & API Key Management

- **API key issuance** — build a simple way to create and manage API keys. A basic web form or CLI tool is fine.
- **Rate limiting** — per-key limits, global limits, burst handling. The upstream Gemini API has ~15k RPM. Chirp 3 has project-based quotas. How do you protect the service?
- **Pricing model** — the pipeline costs ~$0.02–0.08 per video. How do you price sustainably? Research how competitors charge (Deepgram, AssemblyAI, Google STT). Document your pricing logic.
- **Usage tracking** — callers should be able to query their usage and remaining quota programmatically (not just via a dashboard).

### Part 4 — Deployment

Deploy it somewhere publicly accessible. The pipeline needs `ffmpeg` and PyTorch/Whisper (~2GB) — pick whatever hosting makes this easiest (Railway, Render, a VM, etc.).

Your service must have a `/health` or `/status` endpoint that agents can hit to verify the service is alive before sending work.

---

## What you receive

| File | What it does |
|------|-------------|
| `transcribe.py` | Full pipeline: language detection → diarization → structured transcription. CLI included. |
| `schemas.py` | Pydantic models (`TranscriptionResult`, `DiarizedSegment`) and the Gemini prompt |
| `config.py` | API client factories, usage tracker, retry logic, caching |
| `rate_limiter.py` | Thread-safe token-bucket rate limiter (internal, not API-facing) |
| `.env` | GCP credentials and project config |
| `README.md` | Pipeline documentation |

---

## Evaluation criteria

| Area | Weight | What we're looking for |
|------|--------|----------------------|
| **Agent discoverability** | 35% | Can an AI agent find your API, understand it, and use it without human help? OpenAPI quality, MCP server, llms.txt, error design |
| **API & technical quality** | 30% | Clean REST design, async handling, error responses, code quality |
| **Auth & pricing** | 20% | API key management, rate limiting, pricing model, usage tracking |
| **Deployment** | 15% | Actually deployed and accessible, health check endpoint |

---

## Rules

- You can modify any of the provided files.
- You can use any framework (FastAPI, Flask, etc.) for the API.
- A minimal frontend for API key management is fine, but a fancy UI is not the point — agent integration is.
- Document your decisions — a short `DECISIONS.md` explaining your choices is appreciated.
- Ask questions if something is unclear.

Good luck.
