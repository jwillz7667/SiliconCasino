"""Unit tests for Code Golf engine."""

import pytest
from backend.game_engine.codegolf.judge import SolutionJudge, TestCase
from backend.game_engine.codegolf.sandbox import Language


class TestSolutionJudge:
    """Tests for the Code Golf solution judge."""

    @pytest.fixture
    def judge(self):
        return SolutionJudge()

    def test_calculate_code_length_ascii(self, judge):
        """Test code length calculation for ASCII code."""
        code = "print('hello')"
        assert judge.calculate_code_length(code) == 14

    def test_calculate_code_length_unicode(self, judge):
        """Test code length calculation for unicode code."""
        code = "print('🎰')"
        # Emoji takes 4 bytes in UTF-8
        assert judge.calculate_code_length(code) == 14

    def test_normalize_output_trailing_whitespace(self, judge):
        """Test output normalization strips trailing whitespace."""
        output = "hello   \nworld  \n\n"
        expected = "hello\nworld"
        assert judge.normalize_output(output) == expected

    def test_normalize_output_crlf(self, judge):
        """Test output normalization handles Windows line endings."""
        output = "hello\r\nworld\r\n"
        expected = "hello\nworld"
        assert judge.normalize_output(output) == expected

    def test_compare_output_exact_match(self, judge):
        """Test exact output comparison."""
        assert judge.compare_output("hello", "hello")
        assert not judge.compare_output("hello", "world")

    def test_compare_output_trailing_newline_tolerance(self, judge):
        """Test output comparison is lenient on trailing newlines."""
        assert judge.compare_output("hello\n", "hello")
        assert judge.compare_output("hello", "hello\n\n")

    def test_compare_output_trailing_space_tolerance(self, judge):
        """Test output comparison is lenient on trailing spaces."""
        assert judge.compare_output("hello  ", "hello")


class TestTestCase:
    """Tests for TestCase data structure."""

    def test_test_case_creation(self):
        """Test creating a test case."""
        tc = TestCase(
            input="5 3",
            expected_output="8",
            is_hidden=False,
            description="Add two numbers",
        )
        assert tc.input == "5 3"
        assert tc.expected_output == "8"
        assert not tc.is_hidden

    def test_test_case_hidden(self):
        """Test hidden test case."""
        tc = TestCase(
            input="10 20",
            expected_output="30",
            is_hidden=True,
        )
        assert tc.is_hidden


class TestLanguageConfig:
    """Tests for language configuration."""

    def test_supported_languages(self):
        """Test that expected languages are supported."""
        from backend.game_engine.codegolf.sandbox import LANGUAGE_CONFIGS

        assert Language.PYTHON in LANGUAGE_CONFIGS
        assert Language.JAVASCRIPT in LANGUAGE_CONFIGS
        assert Language.GO in LANGUAGE_CONFIGS

    def test_python_config(self):
        """Test Python language configuration."""
        from backend.game_engine.codegolf.sandbox import LANGUAGE_CONFIGS

        config = LANGUAGE_CONFIGS[Language.PYTHON]
        assert config.image == "python:3.11-slim"
        assert config.file_extension == ".py"
        assert config.compile_command is None  # Python is interpreted
        assert config.timeout > 0

    def test_go_config_has_compile(self):
        """Test Go language requires compilation."""
        from backend.game_engine.codegolf.sandbox import LANGUAGE_CONFIGS

        config = LANGUAGE_CONFIGS[Language.GO]
        assert config.compile_command is not None


class TestChallengeTemplates:
    """Tests for built-in challenge templates."""

    def test_get_all_challenges(self):
        """Test getting all challenge templates."""
        from backend.game_engine.codegolf.challenges import get_all_challenges

        challenges = get_all_challenges()
        assert len(challenges) > 0

    def test_get_challenge_by_slug(self):
        """Test getting challenge by slug."""
        from backend.game_engine.codegolf.challenges import get_challenge_by_slug

        hello = get_challenge_by_slug("hello-world")
        assert hello is not None
        assert hello.title == "Hello World"
        assert len(hello.test_cases) > 0

    def test_get_challenge_invalid_slug(self):
        """Test getting non-existent challenge."""
        from backend.game_engine.codegolf.challenges import get_challenge_by_slug

        result = get_challenge_by_slug("nonexistent")
        assert result is None

    def test_challenge_has_required_fields(self):
        """Test challenge templates have required fields."""
        from backend.game_engine.codegolf.challenges import get_all_challenges

        for challenge in get_all_challenges():
            assert challenge.slug
            assert challenge.title
            assert challenge.description
            assert len(challenge.test_cases) > 0
            assert challenge.difficulty
