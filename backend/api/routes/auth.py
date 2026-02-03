from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.core.security import (
    create_access_token,
    generate_api_key,
    get_current_agent,
    hash_api_key,
    verify_api_key,
)
from backend.db.database import get_session
from backend.db.models.agent import Agent
from backend.db.models.wallet import Wallet

router = APIRouter()


class RegisterRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    moltbook_id: str | None = Field(None, max_length=255)


class RegisterResponse(BaseModel):
    agent_id: UUID
    display_name: str
    api_key: str
    message: str


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AgentResponse(BaseModel):
    id: UUID
    display_name: str
    moltbook_id: str | None
    is_active: bool

    class Config:
        from_attributes = True


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    """Register a new agent and receive an API key."""
    if request.moltbook_id:
        existing = await session.execute(
            select(Agent).where(Agent.moltbook_id == request.moltbook_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent with this moltbook_id already exists",
            )

    api_key = generate_api_key()

    agent = Agent(
        display_name=request.display_name,
        moltbook_id=request.moltbook_id,
        api_key_hash=hash_api_key(api_key),
    )
    session.add(agent)
    await session.flush()

    wallet = Wallet(
        agent_id=agent.id,
        balance=settings.default_starting_chips,
    )
    session.add(wallet)
    await session.commit()

    return RegisterResponse(
        agent_id=agent.id,
        display_name=agent.display_name,
        api_key=api_key,
        message="Save this API key - it cannot be retrieved later",
    )


@router.post("/token", response_model=TokenResponse)
async def get_token(
    request: TokenRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Exchange an API key for a JWT access token."""
    result = await session.execute(select(Agent).where(Agent.is_active == True))
    agents = result.scalars().all()

    authenticated_agent = None
    for agent in agents:
        if verify_api_key(request.api_key, agent.api_key_hash):
            authenticated_agent = agent
            break

    if not authenticated_agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    access_token = create_access_token(data={"sub": str(authenticated_agent.id)})

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_expiration_hours * 3600,
    )


@router.get("/me", response_model=AgentResponse)
async def get_current_agent_info(
    agent: Agent = Depends(get_current_agent),
) -> AgentResponse:
    """Get information about the currently authenticated agent."""
    return AgentResponse.model_validate(agent)
