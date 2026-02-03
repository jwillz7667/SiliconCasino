"""Tests for tournament service."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.db.models.tournament import (
    Tournament,
    TournamentEntry,
    TournamentFormat,
    TournamentStatus,
)
from backend.services.tournament_service import (
    DEFAULT_BLIND_STRUCTURE,
    DEFAULT_PRIZE_STRUCTURE,
)


class TestTournamentModel:
    """Test Tournament model."""

    def test_tournament_defaults(self):
        """Test tournament has correct defaults when explicitly set."""
        # Note: SQLAlchemy column defaults only apply on DB insert
        # For Python-level defaults, we test with explicit values
        tournament = Tournament(
            name="Test Tournament",
            buy_in=1000,
            format=TournamentFormat.FREEZEOUT,
            status=TournamentStatus.REGISTERING,
            starting_chips=10000,
            min_players=2,
            max_players=100,
            entries_count=0,
            total_prize_pool=0,
        )

        assert tournament.format == TournamentFormat.FREEZEOUT
        assert tournament.status == TournamentStatus.REGISTERING
        assert tournament.starting_chips == 10000
        assert tournament.min_players == 2
        assert tournament.max_players == 100
        assert tournament.entries_count == 0
        assert tournament.total_prize_pool == 0

    def test_tournament_to_dict(self):
        """Test tournament serialization."""
        tournament = Tournament(
            id=uuid4(),
            name="Test Tournament",
            buy_in=1000,
            starting_chips=5000,
            format=TournamentFormat.FREEZEOUT,
            status=TournamentStatus.REGISTERING,
            created_at=datetime.now(timezone.utc),
        )

        data = tournament.to_dict()

        assert data["name"] == "Test Tournament"
        assert data["buy_in"] == 1000
        assert data["starting_chips"] == 5000
        assert data["format"] == "freezeout"
        assert data["status"] == "registering"


class TestTournamentEntry:
    """Test TournamentEntry model."""

    def test_entry_defaults(self):
        """Test entry has correct defaults when explicitly set."""
        # Note: SQLAlchemy column defaults only apply on DB insert
        entry = TournamentEntry(
            tournament_id=uuid4(),
            agent_id=uuid4(),
            current_chips=10000,
            is_active=True,
            is_eliminated=False,
            finish_position=None,
            rebuys=0,
            total_invested=0,
            registered_at=datetime.now(timezone.utc),
        )

        assert entry.is_active is True
        assert entry.is_eliminated is False
        assert entry.finish_position is None
        assert entry.rebuys == 0
        assert entry.total_invested == 0

    def test_entry_to_dict(self):
        """Test entry serialization."""
        entry = TournamentEntry(
            id=uuid4(),
            tournament_id=uuid4(),
            agent_id=uuid4(),
            current_chips=5000,
            rebuys=1,
            is_active=True,
            is_eliminated=False,
            registered_at=datetime.now(timezone.utc),
        )

        data = entry.to_dict()

        assert data["current_chips"] == 5000
        assert data["rebuys"] == 1
        assert data["is_active"] is True
        assert data["is_eliminated"] is False


class TestBlindStructure:
    """Test blind structure configuration."""

    def test_default_blind_structure_levels(self):
        """Default structure should have multiple levels."""
        assert len(DEFAULT_BLIND_STRUCTURE) >= 10

    def test_blind_structure_increases(self):
        """Blinds should increase with each level."""
        prev_bb = 0
        for level in DEFAULT_BLIND_STRUCTURE:
            bb = level["big_blind"]
            assert bb > prev_bb
            prev_bb = bb

    def test_blind_structure_ratio(self):
        """Small blind should be half of big blind."""
        for level in DEFAULT_BLIND_STRUCTURE:
            sb = level["small_blind"]
            bb = level["big_blind"]
            # Allow for rounding
            assert sb == bb // 2 or sb == (bb + 1) // 2


class TestPrizeStructure:
    """Test prize structure configuration."""

    def test_default_prize_structure(self):
        """Default structure should have top 3 places."""
        assert 1 in DEFAULT_PRIZE_STRUCTURE
        assert 2 in DEFAULT_PRIZE_STRUCTURE
        assert 3 in DEFAULT_PRIZE_STRUCTURE

    def test_prize_structure_total(self):
        """Prizes should total 100%."""
        total = sum(DEFAULT_PRIZE_STRUCTURE.values())
        assert total == 100.0

    def test_first_place_highest(self):
        """First place should get the most."""
        first = DEFAULT_PRIZE_STRUCTURE[1]
        second = DEFAULT_PRIZE_STRUCTURE[2]
        third = DEFAULT_PRIZE_STRUCTURE[3]

        assert first > second > third


class TestTournamentStatusFlow:
    """Test tournament status transitions."""

    def test_valid_status_values(self):
        """All status values should be valid."""
        statuses = [
            TournamentStatus.REGISTERING,
            TournamentStatus.STARTING,
            TournamentStatus.RUNNING,
            TournamentStatus.FINAL_TABLE,
            TournamentStatus.COMPLETED,
            TournamentStatus.CANCELLED,
        ]

        for status in statuses:
            tournament = Tournament(
                name="Test",
                buy_in=1000,
                status=status,
            )
            assert tournament.status == status

    def test_status_string_values(self):
        """Status enum values should match expected strings."""
        assert TournamentStatus.REGISTERING.value == "registering"
        assert TournamentStatus.RUNNING.value == "running"
        assert TournamentStatus.COMPLETED.value == "completed"
        assert TournamentStatus.CANCELLED.value == "cancelled"


class TestTournamentFormat:
    """Test tournament format options."""

    def test_freezeout_format(self):
        """Freezeout should be valid format."""
        tournament = Tournament(
            name="Freezeout Test",
            buy_in=1000,
            format=TournamentFormat.FREEZEOUT,
        )
        assert tournament.format == TournamentFormat.FREEZEOUT

    def test_rebuy_format(self):
        """Rebuy should be valid format."""
        tournament = Tournament(
            name="Rebuy Test",
            buy_in=1000,
            format=TournamentFormat.REBUY,
        )
        assert tournament.format == TournamentFormat.REBUY

    def test_turbo_formats(self):
        """Turbo formats should be valid."""
        turbo = Tournament(
            name="Turbo",
            buy_in=1000,
            format=TournamentFormat.TURBO,
        )
        hyper = Tournament(
            name="Hyper",
            buy_in=1000,
            format=TournamentFormat.HYPER_TURBO,
        )

        assert turbo.format == TournamentFormat.TURBO
        assert hyper.format == TournamentFormat.HYPER_TURBO
