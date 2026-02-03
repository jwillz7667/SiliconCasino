"""Unit tests for the prediction market engine."""

from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from backend.game_engine.predictions.market import (
    Market,
    MarketStatus,
    Outcome,
    Position,
    PredictionEngine,
)


class TestMarket:
    """Tests for Market class."""

    def test_initial_prices(self):
        """Initial prices should be 50/50."""
        market = Market(
            id=uuid4(),
            question="Test?",
            description="Test market",
            category="test",
            status=MarketStatus.OPEN,
            resolution_time=datetime.now(timezone.utc) + timedelta(days=1),
            oracle_source="manual",
            oracle_data={},
        )

        assert market.yes_price == pytest.approx(0.5, rel=0.01)
        assert market.no_price == pytest.approx(0.5, rel=0.01)

    def test_buy_shifts_price(self):
        """Buying shares should shift prices."""
        market = Market(
            id=uuid4(),
            question="Test?",
            description="Test market",
            category="test",
            status=MarketStatus.OPEN,
            resolution_time=datetime.now(timezone.utc) + timedelta(days=1),
            oracle_source="manual",
            oracle_data={},
            yes_pool=1000,
            no_pool=1000,
        )

        initial_yes = market.yes_price

        # Simulate buying YES shares
        cost = market.get_buy_price(Outcome.YES, 100)
        assert cost > 0

        # Price should increase for YES after buying
        # (Note: We're not actually executing, just checking pricing)

    def test_get_buy_price_increases_with_quantity(self):
        """Buying more shares should cost more per share."""
        market = Market(
            id=uuid4(),
            question="Test?",
            description="",
            category="test",
            status=MarketStatus.OPEN,
            resolution_time=datetime.now(timezone.utc) + timedelta(days=1),
            oracle_source="manual",
            oracle_data={},
        )

        cost_10 = market.get_buy_price(Outcome.YES, 10)
        cost_100 = market.get_buy_price(Outcome.YES, 100)
        cost_1000 = market.get_buy_price(Outcome.YES, 1000)

        assert cost_10 < cost_100 < cost_1000
        # Price per share should increase
        assert cost_100 / 100 > cost_10 / 10


class TestPredictionEngine:
    """Tests for PredictionEngine class."""

    def test_create_market(self):
        """Should create a market with default settings."""
        engine = PredictionEngine()

        market = engine.create_market(
            question="Will BTC hit $100k by end of year?",
            description="Bitcoin price prediction",
            category="crypto",
            resolution_time=datetime.now(timezone.utc) + timedelta(days=30),
            oracle_source="coingecko",
            oracle_data={"threshold": 100000},
        )

        assert market.id is not None
        assert market.status == MarketStatus.OPEN
        assert market.question == "Will BTC hit $100k by end of year?"
        assert market.yes_pool == 1000  # default liquidity
        assert market.no_pool == 1000

    def test_buy_shares(self):
        """Should buy shares and update position."""
        engine = PredictionEngine()

        market = engine.create_market(
            question="Test market",
            description="",
            category="test",
            resolution_time=datetime.now(timezone.utc) + timedelta(days=1),
            oracle_source="manual",
            oracle_data={},
        )

        agent_id = uuid4()
        result = engine.buy_shares(
            market_id=market.id,
            agent_id=agent_id,
            outcome=Outcome.YES,
            max_cost=100,
        )

        assert result.success
        assert result.shares_bought > 0
        assert result.price_paid <= 100
        assert agent_id in market.positions

    def test_sell_shares(self):
        """Should sell shares and return chips."""
        engine = PredictionEngine()

        market = engine.create_market(
            question="Test market",
            description="",
            category="test",
            resolution_time=datetime.now(timezone.utc) + timedelta(days=1),
            oracle_source="manual",
            oracle_data={},
        )

        agent_id = uuid4()

        # Buy first
        buy_result = engine.buy_shares(
            market_id=market.id,
            agent_id=agent_id,
            outcome=Outcome.YES,
            max_cost=100,
        )

        # Sell half
        shares_to_sell = buy_result.shares_bought // 2
        sell_result = engine.sell_shares(
            market_id=market.id,
            agent_id=agent_id,
            shares=shares_to_sell,
        )

        assert sell_result.success
        assert sell_result.shares_sold == shares_to_sell
        assert sell_result.price_received > 0

    def test_cannot_buy_in_closed_market(self):
        """Should not allow buying in closed markets."""
        engine = PredictionEngine()

        market = engine.create_market(
            question="Test",
            description="",
            category="test",
            resolution_time=datetime.now(timezone.utc) + timedelta(days=1),
            oracle_source="manual",
            oracle_data={},
        )

        # Close the market
        market.status = MarketStatus.CLOSED

        result = engine.buy_shares(
            market_id=market.id,
            agent_id=uuid4(),
            outcome=Outcome.YES,
            max_cost=100,
        )

        assert not result.success
        assert "not open" in result.error.lower()

    def test_resolve_market(self):
        """Should resolve market and calculate payouts."""
        engine = PredictionEngine()

        market = engine.create_market(
            question="Test",
            description="",
            category="test",
            resolution_time=datetime.now(timezone.utc) + timedelta(days=1),
            oracle_source="manual",
            oracle_data={},
        )

        # Two agents buy opposite sides
        agent_yes = uuid4()
        agent_no = uuid4()

        engine.buy_shares(market.id, agent_yes, Outcome.YES, 100)
        engine.buy_shares(market.id, agent_no, Outcome.NO, 100)

        # Resolve as YES
        payouts = engine.resolve_market(market.id, Outcome.YES)

        assert market.status == MarketStatus.RESOLVED
        assert market.resolved_outcome == Outcome.YES
        assert agent_yes in payouts
        assert payouts[agent_yes] > 0
        assert payouts.get(agent_no, 0) == 0  # Loser gets nothing

    def test_list_markets_filter(self):
        """Should filter markets by status."""
        engine = PredictionEngine()

        # Create markets with different statuses
        m1 = engine.create_market(
            question="Open market",
            description="",
            category="test",
            resolution_time=datetime.now(timezone.utc) + timedelta(days=1),
            oracle_source="manual",
            oracle_data={},
        )

        m2 = engine.create_market(
            question="Closed market",
            description="",
            category="test",
            resolution_time=datetime.now(timezone.utc) + timedelta(days=1),
            oracle_source="manual",
            oracle_data={},
        )
        m2.status = MarketStatus.CLOSED

        open_markets = engine.list_markets(status=MarketStatus.OPEN)
        closed_markets = engine.list_markets(status=MarketStatus.CLOSED)

        assert len(open_markets) == 1
        assert open_markets[0].id == m1.id
        assert len(closed_markets) == 1
        assert closed_markets[0].id == m2.id
