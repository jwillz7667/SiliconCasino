import pytest
from uuid import uuid4

from backend.game_engine.poker.betting import ActionType
from backend.game_engine.poker.engine import HandPhase, PokerEngine
from backend.game_engine.poker.table import TableConfig


@pytest.fixture
def table_config():
    return TableConfig(
        table_id=uuid4(),
        name="Test Table",
        small_blind=5,
        big_blind=10,
        min_buy_in=100,
        max_buy_in=1000,
        max_players=6,
    )


@pytest.fixture
def engine(table_config):
    return PokerEngine(table_config, seed=42)


@pytest.fixture
def engine_with_players(engine):
    agent1 = uuid4()
    agent2 = uuid4()
    engine.seat_player(agent1, 0, 500)
    engine.seat_player(agent2, 1, 500)
    return engine, agent1, agent2


class TestPokerEngine:
    def test_seat_player(self, engine):
        agent_id = uuid4()
        engine.seat_player(agent_id, 0, 500)

        seat = engine.table.seats[0]
        assert seat.agent_id == agent_id
        assert seat.stack == 500
        assert seat.status == "seated"

    def test_seat_player_invalid_seat(self, engine):
        with pytest.raises(ValueError):
            engine.seat_player(uuid4(), 10, 500)

    def test_seat_player_seat_occupied(self, engine):
        engine.seat_player(uuid4(), 0, 500)
        with pytest.raises(ValueError):
            engine.seat_player(uuid4(), 0, 500)

    def test_seat_player_buy_in_too_low(self, engine):
        with pytest.raises(ValueError):
            engine.seat_player(uuid4(), 0, 50)

    def test_seat_player_buy_in_too_high(self, engine):
        with pytest.raises(ValueError):
            engine.seat_player(uuid4(), 0, 2000)

    def test_remove_player(self, engine):
        agent_id = uuid4()
        engine.seat_player(agent_id, 0, 500)

        remaining = engine.remove_player(agent_id)
        assert remaining == 500
        assert engine.table.seats[0].agent_id is None

    def test_can_start_hand_not_enough_players(self, engine):
        engine.seat_player(uuid4(), 0, 500)
        assert not engine.can_start_hand()

    def test_can_start_hand_with_players(self, engine_with_players):
        engine, _, _ = engine_with_players
        assert engine.can_start_hand()

    def test_start_hand(self, engine_with_players):
        engine, _, _ = engine_with_players
        hand = engine.start_hand()

        assert hand is not None
        assert hand.phase == HandPhase.PREFLOP
        assert hand.hand_number == 1
        assert len(hand.hole_cards) == 2

    def test_start_hand_posts_blinds(self, engine_with_players):
        engine, _, _ = engine_with_players
        hand = engine.start_hand()

        assert hand.pot == 15
        total_in_stacks = sum(s.stack for s in engine.table.seats.values() if s.agent_id)
        assert total_in_stacks == 1000 - 15

    def test_process_action_fold(self, engine_with_players):
        engine, agent1, agent2 = engine_with_players
        engine.start_hand()

        action_agent = None
        for seat_num, cards in engine.current_hand.hole_cards.items():
            if engine.current_hand.betting.action_on == seat_num:
                action_agent = engine.table.seats[seat_num].agent_id
                break

        engine.process_action(action_agent, ActionType.FOLD)

        assert engine.current_hand is None

    def test_process_action_call(self, engine_with_players):
        engine, agent1, agent2 = engine_with_players
        engine.start_hand()

        action_agent = None
        for seat_num in engine.current_hand.hole_cards:
            if engine.current_hand.betting.action_on == seat_num:
                action_agent = engine.table.seats[seat_num].agent_id
                break

        engine.process_action(action_agent, ActionType.CALL)

        assert engine.current_hand.betting.pot == 20

    def test_hand_progresses_to_flop(self, engine_with_players):
        engine, agent1, agent2 = engine_with_players
        hand = engine.start_hand()

        action_seat = hand.betting.action_on
        action_agent = engine.table.seats[action_seat].agent_id
        engine.process_action(action_agent, ActionType.CALL)

        other_seat = 1 if action_seat == 0 else 0
        other_agent = engine.table.seats[other_seat].agent_id
        engine.process_action(other_agent, ActionType.CHECK)

        assert engine.current_hand.phase == HandPhase.FLOP
        assert len(engine.current_hand.community_cards) == 3

    def test_get_state(self, engine_with_players):
        engine, agent1, _ = engine_with_players
        engine.start_hand()

        state = engine.get_state(for_agent=agent1)

        assert "table" in state
        assert "hand" in state
        assert state["hand"]["pot"] > 0

    def test_get_state_includes_hole_cards_for_agent(self, engine_with_players):
        engine, agent1, _ = engine_with_players
        engine.start_hand()

        state = engine.get_state(for_agent=agent1)

        assert "your_cards" in state["hand"]
        assert len(state["hand"]["your_cards"]) == 2


class TestFullHand:
    def test_play_hand_to_showdown(self, engine_with_players):
        engine, agent1, agent2 = engine_with_players
        engine.start_hand()

        def get_action_agent():
            seat = engine.current_hand.betting.action_on
            return engine.table.seats[seat].agent_id

        engine.process_action(get_action_agent(), ActionType.CALL)
        engine.process_action(get_action_agent(), ActionType.CHECK)

        assert engine.current_hand.phase == HandPhase.FLOP

        engine.process_action(get_action_agent(), ActionType.CHECK)
        engine.process_action(get_action_agent(), ActionType.CHECK)

        assert engine.current_hand.phase == HandPhase.TURN

        engine.process_action(get_action_agent(), ActionType.CHECK)
        engine.process_action(get_action_agent(), ActionType.CHECK)

        assert engine.current_hand.phase == HandPhase.RIVER

        engine.process_action(get_action_agent(), ActionType.CHECK)
        engine.process_action(get_action_agent(), ActionType.CHECK)

        assert engine.current_hand is None

        total_stacks = sum(s.stack for s in engine.table.seats.values() if s.agent_id)
        assert total_stacks == 1000

    def test_play_hand_all_in(self, table_config):
        # Use RakeConfig with 0 rake to test without rake interference
        from backend.game_engine.poker.engine import RakeConfig
        engine = PokerEngine(table_config, seed=42, rake_config=RakeConfig(percentage=0))
        agent1 = uuid4()
        agent2 = uuid4()
        engine.seat_player(agent1, 0, 100)
        engine.seat_player(agent2, 1, 100)

        engine.start_hand()

        action_seat = engine.current_hand.betting.action_on
        action_agent = engine.table.seats[action_seat].agent_id
        engine.process_action(action_agent, ActionType.ALL_IN)

        other_seat = 1 if action_seat == 0 else 0
        other_agent = engine.table.seats[other_seat].agent_id
        engine.process_action(other_agent, ActionType.CALL)

        assert engine.current_hand is None

        total_stacks = sum(s.stack for s in engine.table.seats.values() if s.agent_id)
        assert total_stacks == 200  # All chips conserved (no rake)
