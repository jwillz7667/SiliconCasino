import pytest

from backend.game_engine.poker.deck import Card, Deck, Rank, Suit, cards_from_string, cards_to_string


class TestCard:
    def test_card_creation(self):
        card = Card(rank=Rank.ACE, suit=Suit.SPADES)
        assert card.rank == Rank.ACE
        assert card.suit == Suit.SPADES

    def test_card_str(self):
        card = Card(rank=Rank.ACE, suit=Suit.SPADES)
        assert str(card) == "As"

        card = Card(rank=Rank.TEN, suit=Suit.HEARTS)
        assert str(card) == "Th"

    def test_card_from_string(self):
        card = Card.from_string("As")
        assert card.rank == Rank.ACE
        assert card.suit == Suit.SPADES

        card = Card.from_string("2c")
        assert card.rank == Rank.TWO
        assert card.suit == Suit.CLUBS

    def test_card_from_string_invalid(self):
        with pytest.raises(ValueError):
            Card.from_string("X")

        with pytest.raises(ValueError):
            Card.from_string("Ax")

        with pytest.raises(ValueError):
            Card.from_string("1s")


class TestDeck:
    def test_deck_has_52_cards(self):
        deck = Deck()
        assert deck.remaining() == 52

    def test_deck_deal(self):
        deck = Deck()
        cards = deck.deal(2)
        assert len(cards) == 2
        assert deck.remaining() == 50

    def test_deck_deal_one(self):
        deck = Deck()
        card = deck.deal_one()
        assert isinstance(card, Card)
        assert deck.remaining() == 51

    def test_deck_shuffle_with_seed_deterministic(self):
        deck1 = Deck(seed=42)
        deck2 = Deck(seed=42)

        cards1 = deck1.deal(5)
        cards2 = deck2.deal(5)

        assert cards1 == cards2

    def test_deck_reset(self):
        deck = Deck()
        deck.deal(10)
        assert deck.remaining() == 42

        deck.reset()
        assert deck.remaining() == 52

    def test_deck_burn(self):
        deck = Deck()
        deck.burn()
        assert deck.remaining() == 51

    def test_deck_cannot_deal_more_than_available(self):
        deck = Deck()
        deck.deal(50)
        with pytest.raises(ValueError):
            deck.deal(5)


class TestCardsConversion:
    def test_cards_to_string(self):
        cards = [
            Card(rank=Rank.ACE, suit=Suit.HEARTS),
            Card(rank=Rank.KING, suit=Suit.HEARTS),
        ]
        assert cards_to_string(cards) == "AhKh"

    def test_cards_from_string(self):
        cards = cards_from_string("AhKhQhJhTh")
        assert len(cards) == 5
        assert cards[0] == Card(rank=Rank.ACE, suit=Suit.HEARTS)
        assert cards[4] == Card(rank=Rank.TEN, suit=Suit.HEARTS)

    def test_cards_from_string_invalid(self):
        with pytest.raises(ValueError):
            cards_from_string("AhK")
