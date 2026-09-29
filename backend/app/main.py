import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logger import broadcaster, logger
from app.api.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    broadcaster.set_loop(loop)
    logger.info(f"Starting AutoApplyJobs backend server... (Event Loop: {type(loop).__name__})")
    logger.info(f"Ollama Target: {settings.OLLAMA_BASE_URL} (Model: {settings.OLLAMA_MODEL})")
    logger.info(f"Excel Tracker File: {settings.EXCEL_FILE_PATH}")

    # Initialize relational persistence in PostgreSQL
    try:
        from app.services.persistence_service import persistence_service
        persistence_service.initialize()
    except Exception as e:
        logger.error(f"[Main] Database persistence initialization failed: {e}")

    yield
    logger.info("Shutting down AutoApplyJobs backend server...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Real-time WebSocket Log Broadcaster
@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await broadcaster.connect(websocket)
    try:
        while True:
            # Keep connection alive; accept any incoming ping from client
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
    except Exception:
        await broadcaster.disconnect(websocket)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "endpoints": {
            "resume": f"{settings.API_V1_STR}/resume",
            "bot": f"{settings.API_V1_STR}/bot",
            "jobs": f"{settings.API_V1_STR}/jobs",
            "settings": f"{settings.API_V1_STR}/settings",
            "ws_logs": "/ws/logs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
