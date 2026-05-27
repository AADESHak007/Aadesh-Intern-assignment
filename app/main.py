from fastapi import FastAPI

from app.routers.transcriptions import router as transcriptions_router
from db import connect_db, disconnect_db

app = FastAPI(
    title="Agent-First Transcription API",
    description="Asynchronous transcription service for video/audio inputs.",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
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
