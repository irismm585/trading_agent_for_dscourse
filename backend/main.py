"""A-Share Trading Agents — FastAPI entry point.

Simplified multi-agent LLM financial analysis web app for A-shares.
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load .env before anything else
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from backend.api.routes import router as api_router  # noqa: E402
from backend.api.websocket import router as ws_router  # noqa: E402

app = FastAPI(
    title="A-Share Trading Agents",
    description="Simplified multi-agent LLM financial analysis for A-shares",
    version="0.1.0",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

# Serve static frontend in production
frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
