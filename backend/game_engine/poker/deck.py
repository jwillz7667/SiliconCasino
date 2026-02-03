import random
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar


class Suit(IntEnum):
    CLUBS = 0
    DIAMONDS = 1
    HEARTS = 2
    SPADES = 3


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14


RANK_CHARS = "23456789TJQKA"
SUIT_CHARS = "cdhs"


@dataclass(frozen=True, slots=True)
class Card:
    """Represents a playing card."""

    rank: Rank
    suit: Suit

    RANK_NAMES: ClassVar[dict[Rank, str]] = {
        Rank.TWO: "2",
        Rank.THREE: "3",
        Rank.FOUR: "4",
        Rank.FIVE: "5",
        Rank.SIX: "6",
        Rank.SEVEN: "7",
        Rank.EIGHT: "8",
        Rank.NINE: "9",
        Rank.TEN: "T",
        Rank.JACK: "J",
        Rank.QUEEN: "Q",
        Rank.KING: "K",
        Rank.ACE: "A",
    }

    SUIT_NAMES: ClassVar[dict[Suit, str]] = {
        Suit.CLUBS: "c",
        Suit.DIAMONDS: "d",
        Suit.HEARTS: "h",
        Suit.SPADES: "s",
    }

    def __str__(self) -> str:
        return f"{self.RANK_NAMES[self.rank]}{self.SUIT_NAMES[self.suit]}"

    def __repr__(self) -> str:
        return f"Card({str(self)})"

    @classmethod
    def from_string(cls, s: str) -> "Card":
        """Create a card from a string like 'Ah' or 'Td'."""
        if len(s) != 2:
            raise ValueError(f"Invalid card string: {s}")

        rank_char = s[0].upper()
        suit_char = s[1].lower()

        rank_idx = RANK_CHARS.find(rank_char)
        if rank_idx == -1:
            raise ValueError(f"Invalid rank: {rank_char}")

        suit_idx = SUIT_CHARS.find(suit_char)
        if suit_idx == -1:
            raise ValueError(f"Invalid suit: {suit_char}")

        return cls(rank=Rank(rank_idx + 2), suit=Suit(suit_idx))

    def to_treys_string(self) -> str:
        """Convert to treys library format."""
        return str(self)


class Deck:
    """A standard 52-card deck."""

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._cards: list[Card] = []
        self._dealt: set[Card] = set()
        self.reset()

    def reset(self) -> None:
        """Reset the deck to a full 52 cards and shuffle."""
        self._cards = [
            Card(rank=rank, suit=suit) for suit in Suit for rank in Rank
        ]
        self._dealt = set()
        self.shuffle()

    def shuffle(self) -> None:
        """Shuffle the remaining cards."""
        self._rng.shuffle(self._cards)

    def deal(self, count: int = 1) -> list[Card]:
        """Deal cards from the top of the deck."""
        if count > len(self._cards):
            raise ValueError(f"Cannot deal {count} cards, only {len(self._cards)} remaining")

        dealt = self._cards[:count]
        self._cards = self._cards[count:]
        self._dealt.update(dealt)
        return dealt

    def deal_one(self) -> Card:
        """Deal a single card."""
        return self.deal(1)[0]

    def remaining(self) -> int:
        """Number of cards remaining in deck."""
        return len(self._cards)

    def burn(self) -> Card:
        """Burn one card (for dealing community cards)."""
        return self.deal_one()

    @property
    def is_empty(self) -> bool:
        return len(self._cards) == 0


def cards_to_string(cards: list[Card]) -> str:
    """Convert a list of cards to a compact string representation."""
    return "".join(str(c) for c in cards)


def cards_from_string(s: str) -> list[Card]:
    """Parse a string of cards like 'AhKhQhJhTh' into a list of Cards."""
    if len(s) % 2 != 0:
        raise ValueError(f"Invalid cards string: {s}")
    return [Card.from_string(s[i : i + 2]) for i in range(0, len(s), 2)]
