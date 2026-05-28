from fastapi import FastAPI

from app.routers.transcriptions import router as transcriptions_router
from db import connect_db, disconnect_db
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import Request

tags_metadata = [
    {
        "name": "Transcriptions",
        "description": "Operations to submit and retrieve asynchronous transcription jobs.",
    },
    {
        "name": "System",
        "description": "System health and usage information.",
    },
]

app = FastAPI(
    title="Agent-First Transcription API",
    description="Asynchronous transcription service for video/audio inputs.",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
)

app.include_router(transcriptions_router)

import os
from fastapi.responses import FileResponse

@app.get("/llms.txt", include_in_schema=False)
async def get_llms_txt():
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "llms.txt")
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/plain")
    return {"detail": "llms.txt not found"}

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        402: "QUOTA_EXCEEDED",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
    }
    code_str = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code_str,
            "message": exc.detail,
            "suggested_action": "Check the API documentation for proper usage."
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": "INVALID_REQUEST",
            "message": "Request validation failed.",
            "suggested_action": "Check the OpenAPI schema for required fields.",
            "details": exc.errors()
        }
    )

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def get_ai_plugin():
    return {
        "schema_version": "v1",
        "name_for_human": "Transcription API",
        "name_for_model": "transcription_api",
        "description_for_human": "Transcription API for converting audio and video to text.",
        "description_for_model": "Agent-optimized API for video/audio transcription, language detection, and speaker diarization.",
        "auth": {
            "type": "user_http",
            "authorization_type": "bearer"
        },
        "api": {
            "type": "openapi",
            "url": "http://localhost:8000/openapi.json",
            "has_user_authentication": True
        },
        "logo_url": "http://localhost:8000/logo.png",
        "contact_email": "support@example.com",
        "legal_info_url": "http://example.com/legal"
    }

@app.get("/.well-known/openapi.json", include_in_schema=False)
async def get_well_known_openapi():
    return app.openapi()

@app.on_event("startup")
async def startup_event() -> None:
    await connect_db()

# Mount the MCP server for SSE
try:
    from app.mcp_server import mcp
    # The official FastMCP exposes an SSE app via get_sse_app() or sse_app()
    # If using mcp.server.fastmcp, it usually returns an ASGI app.
    # Check the exact method or just use the standard attribute:
    app.mount("/mcp", mcp.get_sse_app() if hasattr(mcp, "get_sse_app") else getattr(mcp, "sse_app", getattr(mcp, "_asgi_app", None)) or mcp)
except Exception as e:
    print(f"Warning: Could not mount MCP server: {e}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await disconnect_db()
