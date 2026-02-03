from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import auth, wallet, poker
from backend.api.websocket.handlers import websocket_endpoint
from backend.config import settings
from backend.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    yield


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

# WebSocket endpoint
app.add_api_websocket_route("/api/ws", websocket_endpoint)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "Silicon Casino",
        "version": "0.1.0",
        "docs": "/docs",
    }
