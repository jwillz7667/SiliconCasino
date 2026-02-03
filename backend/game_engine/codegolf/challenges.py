"""Pre-defined Code Golf challenges.

A collection of challenges with varying difficulty levels.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Difficulty(str, Enum):
    """Challenge difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


@dataclass
class ChallengeTemplate:
    """Template for a Code Golf challenge."""
    slug: str
    title: str
    description: str
    test_cases: list[dict]  # [{"input": "", "expected": "", "is_hidden": False}]
    difficulty: Difficulty
    allowed_languages: list[str] = field(default_factory=lambda: ["python", "javascript", "go"])
    example_solution_length: Optional[int] = None  # Approximate shortest known solution
    tags: list[str] = field(default_factory=list)


# Collection of built-in challenges
CHALLENGES: list[ChallengeTemplate] = [
    # Easy challenges
    ChallengeTemplate(
        slug="hello-world",
        title="Hello World",
        description="""Print "Hello, World!" to standard output.

No input is provided.

**Output:**
```
Hello, World!
```
""",
        test_cases=[
            {"input": "", "expected": "Hello, World!", "is_hidden": False},
        ],
        difficulty=Difficulty.EASY,
        example_solution_length=22,
        tags=["basics", "output"],
    ),

    ChallengeTemplate(
        slug="echo",
        title="Echo",
        description="""Read a line of input and print it back.

**Input:** A single line of text.
**Output:** The same line of text.

**Example:**
```
Input: Silicon Casino
Output: Silicon Casino
```
""",
        test_cases=[
            {"input": "Silicon Casino", "expected": "Silicon Casino", "is_hidden": False},
            {"input": "Hello", "expected": "Hello", "is_hidden": False},
            {"input": "123", "expected": "123", "is_hidden": True},
            {"input": "", "expected": "", "is_hidden": True},
        ],
        difficulty=Difficulty.EASY,
        example_solution_length=15,
        tags=["basics", "input", "output"],
    ),

    ChallengeTemplate(
        slug="reverse-string",
        title="Reverse String",
        description="""Read a string and print it reversed.

**Input:** A single line of text.
**Output:** The text reversed.

**Example:**
```
Input: poker
Output: rekop
```
""",
        test_cases=[
            {"input": "poker", "expected": "rekop", "is_hidden": False},
            {"input": "hello", "expected": "olleh", "is_hidden": False},
            {"input": "a", "expected": "a", "is_hidden": True},
            {"input": "12345", "expected": "54321", "is_hidden": True},
            {"input": "", "expected": "", "is_hidden": True},
        ],
        difficulty=Difficulty.EASY,
        example_solution_length=20,
        tags=["strings", "basics"],
    ),

    ChallengeTemplate(
        slug="sum-numbers",
        title="Sum of Numbers",
        description="""Read two integers and print their sum.

**Input:** Two space-separated integers.
**Output:** Their sum.

**Example:**
```
Input: 3 5
Output: 8
```
""",
        test_cases=[
            {"input": "3 5", "expected": "8", "is_hidden": False},
            {"input": "10 20", "expected": "30", "is_hidden": False},
            {"input": "0 0", "expected": "0", "is_hidden": True},
            {"input": "-5 10", "expected": "5", "is_hidden": True},
            {"input": "100 -100", "expected": "0", "is_hidden": True},
        ],
        difficulty=Difficulty.EASY,
        example_solution_length=25,
        tags=["math", "basics"],
    ),

    # Medium challenges
    ChallengeTemplate(
        slug="fizzbuzz",
        title="FizzBuzz",
        description="""Print numbers 1 to N, but:
- For multiples of 3, print "Fizz" instead
- For multiples of 5, print "Buzz" instead
- For multiples of both 3 and 5, print "FizzBuzz"

**Input:** A single integer N.
**Output:** Numbers 1 to N with FizzBuzz rules, one per line.

**Example (N=15):**
```
1
2
Fizz
4
Buzz
Fizz
7
8
Fizz
Buzz
11
Fizz
13
14
FizzBuzz
```
""",
        test_cases=[
            {"input": "5", "expected": "1\n2\nFizz\n4\nBuzz", "is_hidden": False},
            {"input": "15", "expected": "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz", "is_hidden": False},
            {"input": "1", "expected": "1", "is_hidden": True},
            {"input": "3", "expected": "1\n2\nFizz", "is_hidden": True},
        ],
        difficulty=Difficulty.MEDIUM,
        example_solution_length=60,
        tags=["loops", "conditionals", "classic"],
    ),

    ChallengeTemplate(
        slug="fibonacci",
        title="Fibonacci Sequence",
        description="""Print the first N Fibonacci numbers.

The Fibonacci sequence starts with 1, 1, and each subsequent number is the sum of the previous two.

**Input:** A single integer N (1 ≤ N ≤ 30).
**Output:** First N Fibonacci numbers, space-separated.

**Example:**
```
Input: 8
Output: 1 1 2 3 5 8 13 21
```
""",
        test_cases=[
            {"input": "8", "expected": "1 1 2 3 5 8 13 21", "is_hidden": False},
            {"input": "1", "expected": "1", "is_hidden": False},
            {"input": "2", "expected": "1 1", "is_hidden": True},
            {"input": "10", "expected": "1 1 2 3 5 8 13 21 34 55", "is_hidden": True},
        ],
        difficulty=Difficulty.MEDIUM,
        example_solution_length=50,
        tags=["math", "sequences", "classic"],
    ),

    ChallengeTemplate(
        slug="prime-check",
        title="Prime Check",
        description="""Determine if a number is prime.

**Input:** A single integer N (N ≥ 2).
**Output:** "yes" if N is prime, "no" otherwise.

**Example:**
```
Input: 17
Output: yes

Input: 15
Output: no
```
""",
        test_cases=[
            {"input": "17", "expected": "yes", "is_hidden": False},
            {"input": "15", "expected": "no", "is_hidden": False},
            {"input": "2", "expected": "yes", "is_hidden": True},
            {"input": "1000003", "expected": "yes", "is_hidden": True},
            {"input": "100", "expected": "no", "is_hidden": True},
        ],
        difficulty=Difficulty.MEDIUM,
        example_solution_length=45,
        tags=["math", "primes"],
    ),

    ChallengeTemplate(
        slug="palindrome",
        title="Palindrome Check",
        description="""Check if a string is a palindrome (reads the same forwards and backwards).
Ignore case and non-alphanumeric characters.

**Input:** A single line of text.
**Output:** "yes" if palindrome, "no" otherwise.

**Example:**
```
Input: A man, a plan, a canal: Panama
Output: yes

Input: hello
Output: no
```
""",
        test_cases=[
            {"input": "A man, a plan, a canal: Panama", "expected": "yes", "is_hidden": False},
            {"input": "hello", "expected": "no", "is_hidden": False},
            {"input": "racecar", "expected": "yes", "is_hidden": True},
            {"input": "Was it a car or a cat I saw?", "expected": "yes", "is_hidden": True},
            {"input": "abc", "expected": "no", "is_hidden": True},
        ],
        difficulty=Difficulty.MEDIUM,
        example_solution_length=55,
        tags=["strings", "classic"],
    ),

    # Hard challenges
    ChallengeTemplate(
        slug="sort-numbers",
        title="Sort Numbers",
        description="""Sort a list of integers in ascending order.

**Input:** Space-separated integers.
**Output:** Same integers, sorted in ascending order.

**Example:**
```
Input: 5 2 8 1 9
Output: 1 2 5 8 9
```
""",
        test_cases=[
            {"input": "5 2 8 1 9", "expected": "1 2 5 8 9", "is_hidden": False},
            {"input": "1", "expected": "1", "is_hidden": False},
            {"input": "3 3 3", "expected": "3 3 3", "is_hidden": True},
            {"input": "-5 10 -3 0 7", "expected": "-5 -3 0 7 10", "is_hidden": True},
            {"input": "100 50 75 25", "expected": "25 50 75 100", "is_hidden": True},
        ],
        difficulty=Difficulty.HARD,
        example_solution_length=35,
        tags=["sorting", "arrays"],
    ),

    ChallengeTemplate(
        slug="anagram",
        title="Anagram Check",
        description="""Check if two strings are anagrams (contain the same letters in different order).
Ignore case and spaces.

**Input:** Two lines, each containing a string.
**Output:** "yes" if anagrams, "no" otherwise.

**Example:**
```
Input:
listen
silent

Output: yes
```
""",
        test_cases=[
            {"input": "listen\nsilent", "expected": "yes", "is_hidden": False},
            {"input": "hello\nworld", "expected": "no", "is_hidden": False},
            {"input": "Astronomer\nMoon starer", "expected": "yes", "is_hidden": True},
            {"input": "abc\ncba", "expected": "yes", "is_hidden": True},
            {"input": "aab\naba", "expected": "yes", "is_hidden": True},
        ],
        difficulty=Difficulty.HARD,
        example_solution_length=60,
        tags=["strings", "sorting"],
    ),

    ChallengeTemplate(
        slug="count-vowels",
        title="Vowel Counter",
        description="""Count the number of vowels (a, e, i, o, u) in a string.
Case-insensitive.

**Input:** A single line of text.
**Output:** The count of vowels.

**Example:**
```
Input: Silicon Casino
Output: 6
```
""",
        test_cases=[
            {"input": "Silicon Casino", "expected": "6", "is_hidden": False},
            {"input": "hello", "expected": "2", "is_hidden": False},
            {"input": "xyz", "expected": "0", "is_hidden": True},
            {"input": "AEIOU", "expected": "5", "is_hidden": True},
            {"input": "The quick brown fox", "expected": "5", "is_hidden": True},
        ],
        difficulty=Difficulty.EASY,
        example_solution_length=40,
        tags=["strings", "counting"],
    ),

    ChallengeTemplate(
        slug="binary-convert",
        title="Decimal to Binary",
        description="""Convert a decimal integer to binary.

**Input:** A non-negative integer.
**Output:** Its binary representation (no leading zeros, except for 0 itself).

**Example:**
```
Input: 42
Output: 101010
```
""",
        test_cases=[
            {"input": "42", "expected": "101010", "is_hidden": False},
            {"input": "0", "expected": "0", "is_hidden": False},
            {"input": "1", "expected": "1", "is_hidden": True},
            {"input": "255", "expected": "11111111", "is_hidden": True},
            {"input": "1024", "expected": "10000000000", "is_hidden": True},
        ],
        difficulty=Difficulty.MEDIUM,
        example_solution_length=25,
        tags=["math", "binary"],
    ),

    # Expert challenges
    ChallengeTemplate(
        slug="quine",
        title="Quine",
        description="""Write a program that outputs its own source code.

No input is provided. Your program must output exactly its own source code, byte for byte.

**Note:** The empty program is not a valid quine.
""",
        test_cases=[
            # Quine tests are special - expected is the code itself
            # This is handled specially in the judge
            {"input": "", "expected": "__QUINE__", "is_hidden": False, "description": "Output must match source"},
        ],
        difficulty=Difficulty.EXPERT,
        example_solution_length=50,
        tags=["meta", "classic", "expert"],
    ),

    ChallengeTemplate(
        slug="diamond",
        title="Diamond Pattern",
        description="""Print a diamond pattern of asterisks.

**Input:** An odd positive integer N.
**Output:** A diamond of height N, centered with spaces.

**Example (N=5):**
```
  *
 ***
*****
 ***
  *
```
""",
        test_cases=[
            {"input": "5", "expected": "  *\n ***\n*****\n ***\n  *", "is_hidden": False},
            {"input": "3", "expected": " *\n***\n *", "is_hidden": False},
            {"input": "1", "expected": "*", "is_hidden": True},
            {"input": "7", "expected": "   *\n  ***\n *****\n*******\n *****\n  ***\n   *", "is_hidden": True},
        ],
        difficulty=Difficulty.HARD,
        example_solution_length=70,
        tags=["patterns", "loops"],
    ),

    ChallengeTemplate(
        slug="poker-hand",
        title="Poker Hand Rank",
        description="""Determine the rank of a poker hand.

**Input:** 5 cards in format "RankSuit" (e.g., "AS" for Ace of Spades).
Ranks: 2-9, T(10), J, Q, K, A
Suits: S(Spades), H(Hearts), D(Diamonds), C(Clubs)

**Output:** The hand rank name:
- "Royal Flush"
- "Straight Flush"
- "Four of a Kind"
- "Full House"
- "Flush"
- "Straight"
- "Three of a Kind"
- "Two Pair"
- "One Pair"
- "High Card"

**Example:**
```
Input: AS KS QS JS TS
Output: Royal Flush
```
""",
        test_cases=[
            {"input": "AS KS QS JS TS", "expected": "Royal Flush", "is_hidden": False},
            {"input": "7H 7D 7S 7C 2H", "expected": "Four of a Kind", "is_hidden": False},
            {"input": "KS KH KC 3S 3D", "expected": "Full House", "is_hidden": True},
            {"input": "2D 5D 8D JD AD", "expected": "Flush", "is_hidden": True},
            {"input": "5S 6H 7D 8C 9S", "expected": "Straight", "is_hidden": True},
            {"input": "AS 2H 3D 4C 5S", "expected": "Straight", "is_hidden": True, "description": "Ace-low straight"},
        ],
        difficulty=Difficulty.EXPERT,
        example_solution_length=200,
        tags=["poker", "cards", "logic"],
    ),
]


def get_challenge_by_slug(slug: str) -> Optional[ChallengeTemplate]:
    """Get a challenge template by its slug."""
    for challenge in CHALLENGES:
        if challenge.slug == slug:
            return challenge
    return None


def get_challenges_by_difficulty(difficulty: Difficulty) -> list[ChallengeTemplate]:
    """Get all challenges of a given difficulty."""
    return [c for c in CHALLENGES if c.difficulty == difficulty]


def get_all_challenges() -> list[ChallengeTemplate]:
    """Get all challenge templates."""
    return CHALLENGES.copy()
