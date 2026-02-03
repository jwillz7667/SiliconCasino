"""
Prediction Market API routes.

Endpoints for trading on binary outcome prediction markets.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.core.security import get_current_agent
from backend.db.models.agent import Agent
from backend.game_engine.predictions import (
    MarketStatus,
    prediction_engine,
)
from backend.game_engine.predictions.market import Outcome
from backend.services.oracle import oracle_service

router = APIRouter()


# Request/Response models

class CreateMarketRequest(BaseModel):
    """Request to create a new prediction market (admin only for now)."""

    question: str = Field(..., min_length=10, max_length=500)
    description: str = Field("", max_length=2000)
    category: str = Field(..., min_length=1, max_length=50)
    resolution_time: datetime
    oracle_source: str = Field(default="manual")
    oracle_data: dict[str, Any] = Field(default_factory=dict)
    initial_liquidity: int = Field(default=1000, ge=100, le=100000)


class MarketResponse(BaseModel):
    """Response containing market information."""

    id: UUID
    question: str
    description: str
    category: str
    status: str
    resolution_time: datetime
    yes_price: float
    no_price: float
    total_volume: int
    created_at: datetime
    resolved_outcome: str | None = None


class BuySharesRequest(BaseModel):
    """Request to buy shares in a market."""

    outcome: str = Field(..., pattern="^(yes|no)$")
    max_cost: int = Field(..., ge=1, le=1000000)


class SellSharesRequest(BaseModel):
    """Request to sell shares."""

    shares: int = Field(..., ge=1)


class TradeResponse(BaseModel):
    """Response after executing a trade."""

    success: bool
    shares_bought: int = 0
    shares_sold: int = 0
    price_paid: int = 0
    price_received: int = 0
    new_yes_price: float
    new_no_price: float
    error: str | None = None


class PositionResponse(BaseModel):
    """Response containing position information."""

    market_id: str
    question: str
    status: str
    outcome: str
    shares: int
    avg_price: float
    cost_basis: int
    current_value: int


# Routes

@router.get("/markets", response_model=list[MarketResponse])
async def list_markets(
    status: str | None = None,
    category: str | None = None,
) -> list[MarketResponse]:
    """
    List all prediction markets.

    Filter by status (OPEN, CLOSED, RESOLVED) or category.
    """
    market_status = None
    if status:
        try:
            market_status = MarketStatus[status.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.name for s in MarketStatus]}",
            )

    markets = prediction_engine.list_markets(status=market_status, category=category)

    return [
        MarketResponse(
            id=m.id,
            question=m.question,
            description=m.description,
            category=m.category,
            status=m.status.name,
            resolution_time=m.resolution_time,
            yes_price=float(m.yes_price),
            no_price=float(m.no_price),
            total_volume=m.total_volume,
            created_at=m.created_at,
            resolved_outcome=m.resolved_outcome.value if m.resolved_outcome else None,
        )
        for m in markets
    ]


@router.get("/markets/{market_id}", response_model=MarketResponse)
async def get_market(market_id: UUID) -> MarketResponse:
    """Get details for a specific market."""
    market = prediction_engine.get_market(market_id)

    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market not found",
        )

    return MarketResponse(
        id=market.id,
        question=market.question,
        description=market.description,
        category=market.category,
        status=market.status.name,
        resolution_time=market.resolution_time,
        yes_price=float(market.yes_price),
        no_price=float(market.no_price),
        total_volume=market.total_volume,
        created_at=market.created_at,
        resolved_outcome=market.resolved_outcome.value if market.resolved_outcome else None,
    )


@router.post("/markets", response_model=MarketResponse, status_code=status.HTTP_201_CREATED)
async def create_market(
    request: CreateMarketRequest,
    agent: Agent = Depends(get_current_agent),
) -> MarketResponse:
    """
    Create a new prediction market.

    Currently any authenticated agent can create markets.
    In production, this would be admin-only or require stake.
    """
    market = prediction_engine.create_market(
        question=request.question,
        description=request.description,
        category=request.category,
        resolution_time=request.resolution_time,
        oracle_source=request.oracle_source,
        oracle_data=request.oracle_data,
        initial_liquidity=request.initial_liquidity,
    )

    return MarketResponse(
        id=market.id,
        question=market.question,
        description=market.description,
        category=market.category,
        status=market.status.name,
        resolution_time=market.resolution_time,
        yes_price=float(market.yes_price),
        no_price=float(market.no_price),
        total_volume=market.total_volume,
        created_at=market.created_at,
    )


@router.post("/markets/{market_id}/buy", response_model=TradeResponse)
async def buy_shares(
    market_id: UUID,
    request: BuySharesRequest,
    agent: Agent = Depends(get_current_agent),
) -> TradeResponse:
    """
    Buy shares in a prediction market.

    Specify outcome (yes/no) and maximum chips to spend.
    Actual cost depends on current market prices.
    """
    outcome = Outcome.YES if request.outcome == "yes" else Outcome.NO

    result = prediction_engine.buy_shares(
        market_id=market_id,
        agent_id=agent.id,
        outcome=outcome,
        max_cost=request.max_cost,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return TradeResponse(
        success=result.success,
        shares_bought=result.shares_bought,
        price_paid=result.price_paid,
        new_yes_price=float(result.new_yes_price),
        new_no_price=float(result.new_no_price),
    )


@router.post("/markets/{market_id}/sell", response_model=TradeResponse)
async def sell_shares(
    market_id: UUID,
    request: SellSharesRequest,
    agent: Agent = Depends(get_current_agent),
) -> TradeResponse:
    """
    Sell shares back to the market.

    Payout depends on current market prices.
    """
    result = prediction_engine.sell_shares(
        market_id=market_id,
        agent_id=agent.id,
        shares=request.shares,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return TradeResponse(
        success=result.success,
        shares_sold=result.shares_sold,
        price_received=result.price_received,
        new_yes_price=float(result.new_yes_price),
        new_no_price=float(result.new_no_price),
    )


@router.get("/positions", response_model=list[PositionResponse])
async def get_my_positions(
    agent: Agent = Depends(get_current_agent),
) -> list[PositionResponse]:
    """Get all prediction market positions for the authenticated agent."""
    positions = prediction_engine.get_agent_positions(agent.id)

    return [
        PositionResponse(
            market_id=p["market_id"],
            question=p["question"],
            status=p["status"],
            outcome=p["position"]["outcome"],
            shares=p["position"]["shares"],
            avg_price=p["position"]["avg_price"],
            cost_basis=p["position"]["cost_basis"],
            current_value=p["current_value"],
        )
        for p in positions
    ]


@router.get("/markets/{market_id}/quote")
async def get_quote(
    market_id: UUID,
    outcome: str,
    amount: int,
) -> dict[str, Any]:
    """
    Get a price quote for buying shares.

    Shows how many shares you'd get for a given chip amount.
    """
    market = prediction_engine.get_market(market_id)

    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market not found",
        )

    try:
        outcome_enum = Outcome.YES if outcome.lower() == "yes" else Outcome.NO
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outcome must be 'yes' or 'no'",
        )

    # Calculate shares for this cost
    shares = prediction_engine._calculate_shares_for_cost(market, outcome_enum, amount)
    actual_cost = market.get_buy_price(outcome_enum, shares) if shares > 0 else 0

    return {
        "market_id": str(market_id),
        "outcome": outcome,
        "max_spend": amount,
        "shares_received": shares,
        "actual_cost": actual_cost,
        "price_per_share": actual_cost / shares if shares > 0 else 0,
        "current_price": float(market.yes_price if outcome_enum == Outcome.YES else market.no_price),
    }


@router.get("/oracle/crypto/{coin_id}")
async def get_crypto_price(
    coin_id: str,
    vs_currency: str = "usd",
) -> dict[str, Any]:
    """
    Get current cryptocurrency price from oracle.

    Used to check prices before/after market resolution.
    """
    result = await oracle_service.get_crypto_price(coin_id, vs_currency)
    return {
        "coin_id": coin_id,
        "vs_currency": vs_currency,
        "price": float(result.value) if result.value else None,
        "source": result.source.value,
        "timestamp": result.timestamp.isoformat(),
        "raw_data": result.raw_data,
    }


@router.post("/markets/{market_id}/resolve")
async def resolve_market(
    market_id: UUID,
    outcome: str | None = None,
    agent: Agent = Depends(get_current_agent),
) -> dict[str, Any]:
    """
    Resolve a prediction market.

    For oracle-based markets, outcome is determined automatically.
    For manual markets, admin must provide outcome ("yes" or "no").

    Returns payout information.
    """
    market = prediction_engine.get_market(market_id)

    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market not found",
        )

    if market.status != MarketStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Market is not open for resolution",
        )

    # Try oracle resolution first
    if market.oracle_source != "manual":
        oracle_outcome, oracle_result = await oracle_service.resolve_market(
            market.oracle_source,
            market.oracle_data,
        )

        if oracle_outcome is not None:
            resolved_outcome = Outcome.YES if oracle_outcome else Outcome.NO
            payouts = prediction_engine.resolve_market(market_id, resolved_outcome)

            return {
                "market_id": str(market_id),
                "resolved_outcome": resolved_outcome.value,
                "resolution_source": "oracle",
                "oracle_data": oracle_result.to_dict(),
                "payouts": {str(k): v for k, v in payouts.items()},
                "total_payout": sum(payouts.values()),
            }

    # Manual resolution
    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual markets require outcome parameter ('yes' or 'no')",
        )

    try:
        resolved_outcome = Outcome.YES if outcome.lower() == "yes" else Outcome.NO
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outcome must be 'yes' or 'no'",
        )

    payouts = prediction_engine.resolve_market(market_id, resolved_outcome)

    return {
        "market_id": str(market_id),
        "resolved_outcome": resolved_outcome.value,
        "resolution_source": "manual",
        "payouts": {str(k): v for k, v in payouts.items()},
        "total_payout": sum(payouts.values()),
    }
