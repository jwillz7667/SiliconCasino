"""
Prediction Market Engine.

Implements binary outcome prediction markets using a simple
automated market maker (AMM) model.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum, auto
from typing import Any
from uuid import UUID, uuid4


class MarketStatus(Enum):
    """Status of a prediction market."""

    OPEN = auto()       # Accepting trades
    CLOSED = auto()     # No more trades, awaiting resolution
    RESOLVED = auto()   # Outcome determined, payouts available
    CANCELLED = auto()  # Market cancelled, refunds issued


class Outcome(Enum):
    """Possible outcomes for binary markets."""

    YES = "yes"
    NO = "no"


@dataclass
class Position:
    """A position held by an agent in a market."""

    agent_id: UUID
    outcome: Outcome
    shares: int
    avg_price: Decimal
    cost_basis: int  # Total chips spent

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": str(self.agent_id),
            "outcome": self.outcome.value,
            "shares": self.shares,
            "avg_price": float(self.avg_price),
            "cost_basis": self.cost_basis,
        }


@dataclass
class TradeResult:
    """Result of a trade execution."""

    success: bool
    shares_bought: int = 0
    shares_sold: int = 0
    price_paid: int = 0
    price_received: int = 0
    new_yes_price: Decimal = Decimal("0.5")
    new_no_price: Decimal = Decimal("0.5")
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "shares_bought": self.shares_bought,
            "shares_sold": self.shares_sold,
            "price_paid": self.price_paid,
            "price_received": self.price_received,
            "new_yes_price": float(self.new_yes_price),
            "new_no_price": float(self.new_no_price),
            "error": self.error,
        }


@dataclass
class Market:
    """A binary prediction market."""

    id: UUID
    question: str
    description: str
    category: str
    status: MarketStatus
    resolution_time: datetime
    oracle_source: str  # e.g., "coingecko", "manual"
    oracle_data: dict[str, Any]  # Data needed for resolution

    # AMM state (using constant product formula variant)
    yes_pool: int = 1000  # Virtual liquidity
    no_pool: int = 1000

    # Tracking
    total_volume: int = 0
    positions: dict[UUID, Position] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    resolved_outcome: Outcome | None = None

    @property
    def yes_price(self) -> Decimal:
        """Current price of YES shares (0.0 to 1.0)."""
        total = self.yes_pool + self.no_pool
        return Decimal(self.no_pool) / Decimal(total)

    @property
    def no_price(self) -> Decimal:
        """Current price of NO shares (0.0 to 1.0)."""
        return Decimal(1) - self.yes_price

    def get_buy_price(self, outcome: Outcome, shares: int) -> int:
        """
        Calculate cost to buy shares using constant product AMM.

        Uses formula: cost = pool_out - (k / (pool_in + shares))
        where k = yes_pool * no_pool
        """
        if shares <= 0:
            return 0

        k = self.yes_pool * self.no_pool

        if outcome == Outcome.YES:
            # Buying YES = adding to NO pool, removing from YES pool
            new_no_pool = self.no_pool + shares
            new_yes_pool = k // new_no_pool
            cost = shares + (self.yes_pool - new_yes_pool)
        else:
            # Buying NO = adding to YES pool, removing from NO pool
            new_yes_pool = self.yes_pool + shares
            new_no_pool = k // new_yes_pool
            cost = shares + (self.no_pool - new_no_pool)

        return max(1, cost)  # Minimum 1 chip

    def get_sell_price(self, outcome: Outcome, shares: int) -> int:
        """Calculate chips received for selling shares."""
        if shares <= 0:
            return 0

        k = self.yes_pool * self.no_pool

        if outcome == Outcome.YES:
            # Selling YES = removing from NO pool, adding to YES pool
            new_yes_pool = self.yes_pool + shares
            new_no_pool = k // new_yes_pool
            payout = (self.no_pool - new_no_pool)
        else:
            # Selling NO = removing from YES pool, adding to NO pool
            new_no_pool = self.no_pool + shares
            new_yes_pool = k // new_no_pool
            payout = (self.yes_pool - new_yes_pool)

        return max(0, payout)

    def to_dict(self, include_positions: bool = False) -> dict[str, Any]:
        data = {
            "id": str(self.id),
            "question": self.question,
            "description": self.description,
            "category": self.category,
            "status": self.status.name,
            "resolution_time": self.resolution_time.isoformat(),
            "yes_price": float(self.yes_price),
            "no_price": float(self.no_price),
            "total_volume": self.total_volume,
            "created_at": self.created_at.isoformat(),
        }

        if self.resolved_outcome:
            data["resolved_outcome"] = self.resolved_outcome.value
            data["resolved_at"] = self.resolved_at.isoformat() if self.resolved_at else None

        if include_positions:
            data["positions"] = {
                str(agent_id): pos.to_dict()
                for agent_id, pos in self.positions.items()
            }

        return data


class PredictionEngine:
    """Engine for managing prediction markets."""

    # Platform fee on winnings (2%)
    FEE_RATE = Decimal("0.02")

    def __init__(self):
        self._markets: dict[UUID, Market] = {}

    def create_market(
        self,
        question: str,
        description: str,
        category: str,
        resolution_time: datetime,
        oracle_source: str,
        oracle_data: dict[str, Any],
        initial_liquidity: int = 1000,
    ) -> Market:
        """Create a new prediction market."""
        market = Market(
            id=uuid4(),
            question=question,
            description=description,
            category=category,
            status=MarketStatus.OPEN,
            resolution_time=resolution_time,
            oracle_source=oracle_source,
            oracle_data=oracle_data,
            yes_pool=initial_liquidity,
            no_pool=initial_liquidity,
        )

        self._markets[market.id] = market
        return market

    def get_market(self, market_id: UUID) -> Market | None:
        """Get a market by ID."""
        return self._markets.get(market_id)

    def list_markets(
        self,
        status: MarketStatus | None = None,
        category: str | None = None,
    ) -> list[Market]:
        """List markets with optional filters."""
        markets = list(self._markets.values())

        if status:
            markets = [m for m in markets if m.status == status]

        if category:
            markets = [m for m in markets if m.category == category]

        return sorted(markets, key=lambda m: m.created_at, reverse=True)

    def buy_shares(
        self,
        market_id: UUID,
        agent_id: UUID,
        outcome: Outcome,
        max_cost: int,
    ) -> TradeResult:
        """
        Buy shares in a market outcome.

        Args:
            market_id: Market to trade in
            agent_id: Agent making the trade
            outcome: YES or NO
            max_cost: Maximum chips to spend

        Returns:
            TradeResult with execution details
        """
        market = self._markets.get(market_id)

        if not market:
            return TradeResult(success=False, error="Market not found")

        if market.status != MarketStatus.OPEN:
            return TradeResult(success=False, error="Market is not open for trading")

        if datetime.now(timezone.utc) >= market.resolution_time:
            return TradeResult(success=False, error="Market has expired")

        if max_cost <= 0:
            return TradeResult(success=False, error="Must spend at least 1 chip")

        # Calculate how many shares we can buy
        shares = self._calculate_shares_for_cost(market, outcome, max_cost)

        if shares <= 0:
            return TradeResult(success=False, error="Insufficient funds for any shares")

        actual_cost = market.get_buy_price(outcome, shares)

        # Execute trade
        k = market.yes_pool * market.no_pool

        if outcome == Outcome.YES:
            market.no_pool += actual_cost
            market.yes_pool = k // market.no_pool
        else:
            market.yes_pool += actual_cost
            market.no_pool = k // market.yes_pool

        market.total_volume += actual_cost

        # Update position
        if agent_id not in market.positions:
            market.positions[agent_id] = Position(
                agent_id=agent_id,
                outcome=outcome,
                shares=0,
                avg_price=Decimal("0"),
                cost_basis=0,
            )

        pos = market.positions[agent_id]

        if pos.outcome != outcome:
            # Agent switching sides - close old position first
            # For simplicity, just replace
            pos.outcome = outcome
            pos.shares = shares
            pos.cost_basis = actual_cost
            pos.avg_price = Decimal(actual_cost) / Decimal(shares)
        else:
            # Adding to position
            total_shares = pos.shares + shares
            total_cost = pos.cost_basis + actual_cost
            pos.shares = total_shares
            pos.cost_basis = total_cost
            pos.avg_price = Decimal(total_cost) / Decimal(total_shares) if total_shares > 0 else Decimal("0")

        return TradeResult(
            success=True,
            shares_bought=shares,
            price_paid=actual_cost,
            new_yes_price=market.yes_price,
            new_no_price=market.no_price,
        )

    def sell_shares(
        self,
        market_id: UUID,
        agent_id: UUID,
        shares: int,
    ) -> TradeResult:
        """Sell shares back to the market."""
        market = self._markets.get(market_id)

        if not market:
            return TradeResult(success=False, error="Market not found")

        if market.status != MarketStatus.OPEN:
            return TradeResult(success=False, error="Market is not open for trading")

        if agent_id not in market.positions:
            return TradeResult(success=False, error="No position to sell")

        pos = market.positions[agent_id]

        if shares > pos.shares:
            return TradeResult(success=False, error="Not enough shares to sell")

        payout = market.get_sell_price(pos.outcome, shares)

        # Execute trade
        k = market.yes_pool * market.no_pool

        if pos.outcome == Outcome.YES:
            market.yes_pool += shares
            market.no_pool = k // market.yes_pool
        else:
            market.no_pool += shares
            market.yes_pool = k // market.no_pool

        # Update position
        pos.shares -= shares
        if pos.shares == 0:
            del market.positions[agent_id]

        return TradeResult(
            success=True,
            shares_sold=shares,
            price_received=payout,
            new_yes_price=market.yes_price,
            new_no_price=market.no_price,
        )

    def resolve_market(
        self,
        market_id: UUID,
        outcome: Outcome,
    ) -> dict[UUID, int]:
        """
        Resolve a market and calculate payouts.

        Returns dict of agent_id -> payout amount.
        """
        market = self._markets.get(market_id)

        if not market:
            return {}

        if market.status != MarketStatus.OPEN and market.status != MarketStatus.CLOSED:
            return {}

        market.status = MarketStatus.RESOLVED
        market.resolved_outcome = outcome
        market.resolved_at = datetime.now(timezone.utc)

        payouts: dict[UUID, int] = {}

        for agent_id, pos in market.positions.items():
            if pos.outcome == outcome:
                # Winner! Each share pays out 100 chips (minus fee)
                gross_payout = pos.shares * 100
                fee = int(gross_payout * self.FEE_RATE)
                net_payout = gross_payout - fee
                payouts[agent_id] = net_payout
            else:
                # Loser - shares are worthless
                payouts[agent_id] = 0

        return payouts

    def _calculate_shares_for_cost(
        self,
        market: Market,
        outcome: Outcome,
        max_cost: int,
    ) -> int:
        """Binary search to find max shares purchasable for a given cost."""
        low, high = 1, max_cost * 2
        best = 0

        while low <= high:
            mid = (low + high) // 2
            cost = market.get_buy_price(outcome, mid)

            if cost <= max_cost:
                best = mid
                low = mid + 1
            else:
                high = mid - 1

        return best

    def get_agent_positions(self, agent_id: UUID) -> list[dict[str, Any]]:
        """Get all positions for an agent across all markets."""
        positions = []

        for market in self._markets.values():
            if agent_id in market.positions:
                pos = market.positions[agent_id]
                positions.append({
                    "market_id": str(market.id),
                    "question": market.question,
                    "status": market.status.name,
                    "position": pos.to_dict(),
                    "current_value": market.get_sell_price(pos.outcome, pos.shares),
                })

        return positions


# Global prediction engine instance
prediction_engine = PredictionEngine()
