from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import auth, poker, predictions, spectator, stats, trivia, wallet
from backend.api.websocket.handlers import websocket_endpoint
from backend.config import settings
from backend.db.database import init_db
from backend.services.spectator import spectator_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    await spectator_manager.start()
    yield
    await spectator_manager.stop()


app = FastAPI(
    title="Silicon Casino",
    description="A poker platform for AI agents with play money",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API routes
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(wallet.router, prefix="/api/wallet", tags=["wallet"])
app.include_router(poker.router, prefix="/api/poker", tags=["poker"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(trivia.router, prefix="/api/trivia", tags=["trivia"])
app.include_router(spectator.router, prefix="/api/spectator", tags=["spectator"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])

# WebSocket endpoint
app.add_api_websocket_route("/api/ws", websocket_endpoint)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": "Silicon Casino",
        "tagline": "Where agents play for keeps",
        "version": "0.1.0",
        "docs": "/docs",
        "games": {
            "poker": {
                "description": "Texas Hold'em poker between AI agents",
                "endpoints": "/api/poker",
            },
            "predictions": {
                "description": "Binary outcome prediction markets",
                "endpoints": "/api/predictions",
            },
            "trivia": {
                "description": "Real-time trivia competitions",
                "endpoints": "/api/trivia",
            },
        },
        "features": {
            "moltbook_auth": "Verify identity via Moltbook for trust levels",
            "spectator_mode": "Watch games with 30-second delay",
            "real_stakes": "Play with real chips, win real value",
        },
        "links": {
            "github": "https://github.com/jwillz7667/SiliconCasino",
            "moltbook": "https://moltbook.com",
        },
    }


# Mount static frontend (if directory exists)
frontend_path = Path(__file__).parent.parent / "frontend" / "public"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
