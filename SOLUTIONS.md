# Solutions: Ways To Use This Tool

## Way 01: Direct API Integration

### 1) Create API key
`POST /api-keys`

Request:
```json
{
  "label": "my-agent",
  "quota": 25
}
```

Response (`201`):
```json
{
  "id": "712b09b0-b748-4f3f-81cc-79d069a6a581",
  "api_key": "ak_xxxxxxxxxxxxxxxxx",
  "label": "my-agent",
  "quota": 25
}
```

### 2) Submit transcription job
`POST /transcriptions` (multipart form)

Option A: submit with `source_url`
```json
{
  "source_url": "https://www.w3schools.com/html/mov_bbb.mp4",
  "model": "gemini-2.5-flash"
}
```

Option B: submit with file upload (`file`)

Multipart fields:
- `file`: binary media file (`.mp4`, `.mp3`, `.wav`, etc.)
- `model`: optional, default `gemini-2.5-flash`
- `callback_url`: optional webhook URL

`curl` example:
```bash
curl -X POST "https://aadesh-intern-assignment.onrender.com/transcriptions" \
  -H "X-API-Key: ak_xxxxxxxxxxxxxxxxx" \
  -F "file=@./sample.mp4" \
  -F "model=gemini-2.5-flash"
```

Response (`202`):
```json
{
  "job_id": "b032e832-2c28-4d7c-bee9-2de649be499f",
  "status": "PENDING",
  "location": "/transcriptions/b032e832-2c28-4d7c-bee9-2de649be499f"
}
```

### 3) Check status
`GET /transcriptions/{job_id}`

Response (`200`):
```json
{
  "job_id": "b032e832-2c28-4d7c-bee9-2de649be499f",
  "status": "COMPLETED",
  "stage": "FINALIZING",
  "created_at": "2026-05-28T05:22:05.819628Z",
  "updated_at": "2026-05-28T05:22:12.484544Z",
  "result_url": "/transcriptions/b032e832-2c28-4d7c-bee9-2de649be499f/result",
  "error_code": null,
  "error_message": null,
  "suggested_action": null
}
```

### 4) Fetch final result
`GET /transcriptions/{job_id}/result/raw`

Response (`200`):
```json
{
  "text": "",
  "diarizedTranscript": [],
  "audioMode": "music-only",
  "detectedLanguage": "",
  "detectedLanguageName": "",
  "languagesUsed": [],
  "languagesUsedNames": [],
  "isTranslated": false
}
```

### 5) Useful support endpoints
- `GET /usage` -> usage count, quota left, token balance
- `GET /health` -> service liveness
- `GET /schemas/transcription-result` -> JSON schema for result object

---

## Way 02: Via MCP (Model Context Protocol)

- MCP server is mounted at `/mcp`.
- Agent connects to the MCP endpoint and invokes transcription as a tool instead of managing raw HTTP routes.
- Best for ecosystems already using MCP tool discovery/execution.

Typical MCP flow:
1. Connect to MCP server.
2. Discover available transcription tools.
3. Call tool with media URL or file input.
4. Receive structured transcription result.

---

## Way 03: Via Agent Workflow (Autonomous)

Recommended agent loop:
1. `POST /api-keys` once, store key.
2. `GET /health` before submitting heavy work.
3. `POST /transcriptions` with `source_url` or file.
4. Poll `GET /transcriptions/{job_id}` with exponential backoff.
5. On `COMPLETED`, fetch `GET /transcriptions/{job_id}/result/raw`.
6. On `FAILED`, read `error_code` + `suggested_action`, then retry/stop intelligently.

---

## Base URL
`https://aadesh-intern-assignment.onrender.com`
