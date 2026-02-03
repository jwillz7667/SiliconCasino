import pytest
from uuid import uuid4

from backend.game_engine.poker.betting import (
    ActionType,
    BettingRound,
    BettingState,
    PlayerAction,
    PlayerBettingState,
)


@pytest.fixture
def two_player_betting():
    """Create a betting state with two players."""
    state = BettingState(
        round=BettingRound.PREFLOP,
        big_blind=10,
        min_raise=10,
        current_bet=10,
        action_on=0,
    )
    state.players[0] = PlayerBettingState(
        seat=0, agent_id=uuid4(), stack=1000, bet_this_round=10, has_acted=False
    )
    state.players[1] = PlayerBettingState(
        seat=1, agent_id=uuid4(), stack=990, bet_this_round=0, has_acted=False
    )
    state.pot = 10
    return state


class TestBettingState:
    def test_get_valid_actions_facing_bet(self, two_player_betting):
        actions = two_player_betting.get_valid_actions(1)
        assert ActionType.FOLD in actions
        assert ActionType.CALL in actions
        assert ActionType.RAISE in actions
        assert ActionType.ALL_IN in actions
        assert ActionType.CHECK not in actions

    def test_get_valid_actions_no_bet(self):
        state = BettingState(
            round=BettingRound.FLOP,
            big_blind=10,
            min_raise=10,
            current_bet=0,
            action_on=0,
        )
        state.players[0] = PlayerBettingState(
            seat=0, agent_id=uuid4(), stack=1000
        )

        actions = state.get_valid_actions(0)
        assert ActionType.CHECK in actions
        assert ActionType.BET in actions
        assert ActionType.FOLD in actions
        assert ActionType.CALL not in actions

    def test_process_fold(self, two_player_betting):
        action = PlayerAction(
            player_seat=1,
            agent_id=two_player_betting.players[1].agent_id,
            action_type=ActionType.FOLD,
        )
        two_player_betting.process_action(action)

        assert two_player_betting.players[1].is_folded
        assert two_player_betting.count_active_players() == 1

    def test_process_call(self, two_player_betting):
        action = PlayerAction(
            player_seat=1,
            agent_id=two_player_betting.players[1].agent_id,
            action_type=ActionType.CALL,
        )
        two_player_betting.process_action(action)

        assert two_player_betting.players[1].bet_this_round == 10
        assert two_player_betting.players[1].stack == 980
        assert two_player_betting.pot == 20

    def test_process_raise(self, two_player_betting):
        action = PlayerAction(
            player_seat=1,
            agent_id=two_player_betting.players[1].agent_id,
            action_type=ActionType.RAISE,
            amount=30,
        )
        two_player_betting.process_action(action)

        assert two_player_betting.players[1].bet_this_round == 30
        assert two_player_betting.current_bet == 30
        assert two_player_betting.players[0].has_acted == False

    def test_process_all_in(self, two_player_betting):
        two_player_betting.players[1].stack = 50

        action = PlayerAction(
            player_seat=1,
            agent_id=two_player_betting.players[1].agent_id,
            action_type=ActionType.ALL_IN,
        )
        two_player_betting.process_action(action)

        assert two_player_betting.players[1].stack == 0
        assert two_player_betting.players[1].is_all_in
        assert two_player_betting.players[1].bet_this_round == 50

    def test_round_complete_after_all_act(self, two_player_betting):
        two_player_betting.players[0].has_acted = True

        action = PlayerAction(
            player_seat=1,
            agent_id=two_player_betting.players[1].agent_id,
            action_type=ActionType.CALL,
        )
        is_complete = two_player_betting.process_action(action)

        assert is_complete

    def test_round_not_complete_after_raise(self, two_player_betting):
        action = PlayerAction(
            player_seat=1,
            agent_id=two_player_betting.players[1].agent_id,
            action_type=ActionType.RAISE,
            amount=30,
        )
        is_complete = two_player_betting.process_action(action)

        assert not is_complete

    def test_start_new_round(self, two_player_betting):
        two_player_betting.players[0].bet_this_round = 100
        two_player_betting.players[1].bet_this_round = 100

        two_player_betting.start_new_round(BettingRound.FLOP, 0)

        assert two_player_betting.round == BettingRound.FLOP
        assert two_player_betting.current_bet == 0
        assert two_player_betting.players[0].bet_this_round == 0
        assert two_player_betting.players[1].bet_this_round == 0
        assert two_player_betting.action_on == 0


class TestPlayerBettingState:
    def test_is_active(self):
        player = PlayerBettingState(seat=0, agent_id=uuid4(), stack=1000)
        assert player.is_active

        player.is_folded = True
        assert not player.is_active

    def test_reset_for_round(self):
        player = PlayerBettingState(
            seat=0,
            agent_id=uuid4(),
            stack=1000,
            bet_this_round=100,
            has_acted=True,
        )
        player.reset_for_round()

        assert player.bet_this_round == 0
        assert not player.has_acted
        assert player.total_bet_this_hand == 0
