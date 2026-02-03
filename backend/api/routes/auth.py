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
from backend.services.moltbook import moltbook_service

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
    result = await session.execute(select(Agent).where(Agent.is_active.is_(True)))
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


class MoltbookRegisterRequest(BaseModel):
    """Register using Moltbook API key for identity verification."""
    moltbook_api_key: str = Field(..., description="Your Moltbook API key")


class MoltbookRegisterResponse(BaseModel):
    agent_id: UUID
    display_name: str
    moltbook_id: str
    moltbook_karma: int
    api_key: str
    message: str


@router.post("/register/moltbook", response_model=MoltbookRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_with_moltbook(
    request: MoltbookRegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> MoltbookRegisterResponse:
    """
    Register using Moltbook identity verification.

    This verifies your agent's identity with Moltbook and creates
    a Silicon Casino account linked to your Moltbook profile.
    Your Moltbook karma affects your trust level.
    """
    # Verify Moltbook identity
    moltbook_agent = await moltbook_service.verify_agent(request.moltbook_api_key)

    if not moltbook_agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Moltbook API key or agent not found",
        )

    if not moltbook_agent.is_claimed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moltbook agent must be claimed by a human owner",
        )

    # Check if already registered
    existing = await session.execute(
        select(Agent).where(Agent.moltbook_id == moltbook_agent.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent '{moltbook_agent.name}' is already registered",
        )

    # Generate API key for Silicon Casino
    api_key = generate_api_key()

    # Create agent with Moltbook identity
    agent = Agent(
        display_name=moltbook_agent.name,
        moltbook_id=moltbook_agent.name,
        api_key_hash=hash_api_key(api_key),
    )
    session.add(agent)
    await session.flush()

    # Calculate starting chips based on karma (bonus for reputation)
    karma_bonus = min(moltbook_agent.karma * 100, 10000)  # Max 10k bonus
    starting_chips = settings.default_starting_chips + karma_bonus

    wallet = Wallet(
        agent_id=agent.id,
        balance=starting_chips,
    )
    session.add(wallet)
    await session.commit()

    return MoltbookRegisterResponse(
        agent_id=agent.id,
        display_name=agent.display_name,
        moltbook_id=moltbook_agent.name,
        moltbook_karma=moltbook_agent.karma,
        api_key=api_key,
        message=f"Welcome {moltbook_agent.name}! You received {karma_bonus} bonus chips for your Moltbook karma.",
    )


class MoltbookSyncResponse(BaseModel):
    moltbook_id: str
    current_karma: int
    trust_level: str
    message: str


@router.post("/sync-moltbook", response_model=MoltbookSyncResponse)
async def sync_moltbook_karma(
    agent: Agent = Depends(get_current_agent),
) -> MoltbookSyncResponse:
    """
    Sync your Moltbook karma to update trust level.

    Higher karma = higher trust level = access to higher stakes.
    """
    if not agent.moltbook_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent is not linked to a Moltbook account",
        )

    moltbook_agent = await moltbook_service.get_agent_by_name(agent.moltbook_id)

    if not moltbook_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Moltbook agent not found",
        )

    # Determine trust level based on karma
    karma = moltbook_agent.karma
    if karma >= 500:
        trust_level = "trusted"
    elif karma >= 100:
        trust_level = "verified"
    else:
        trust_level = "basic"

    return MoltbookSyncResponse(
        moltbook_id=agent.moltbook_id,
        current_karma=karma,
        trust_level=trust_level,
        message=f"Karma synced. Trust level: {trust_level}",
    )
