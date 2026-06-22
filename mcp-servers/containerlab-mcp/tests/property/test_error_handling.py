"""Property-based tests for error handling: sanitization and truncation.

# Feature: containerlab-mcp, Property 8: Error Response Sanitization
# Feature: containerlab-mcp, Property 9: Stderr Truncation
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from containerlab_mcp.parser import OutputParser


# --- Strategies ---

def _absolute_path_strategy() -> st.SearchStrategy[str]:
    """Generate realistic absolute Unix paths."""
    segment = st.from_regex(r"[a-zA-Z0-9_.\-]+", fullmatch=True).filter(lambda s: len(s) > 0)
    return st.lists(segment, min_size=2, max_size=6).map(lambda parts: "/" + "/".join(parts))


def _credential_pattern_strategy() -> st.SearchStrategy[str]:
    """Generate credential-like key=value patterns."""
    keys = st.sampled_from([
        "password", "passwd", "token", "secret", "key",
        "credential", "auth_token", "api_key",
        "PASSWORD", "Token", "SECRET",
    ])
    separators = st.sampled_from(["=", ": ", "=", ":"])
    values = st.from_regex(r"\S+", fullmatch=True).filter(lambda s: len(s) > 0 and len(s) < 50)
    return st.tuples(keys, separators, values).map(lambda t: f"{t[0]}{t[1]}{t[2]}")


def _context_text_strategy() -> st.SearchStrategy[str]:
    """Generate surrounding context text that doesn't contain paths or credentials."""
    return st.from_regex(r"[a-zA-Z ]{1,60}", fullmatch=True)


# --- Property 8: Error Response Sanitization ---


class TestErrorResponseSanitization:
    """Property 8: Error Response Sanitization.

    For any CLI error output containing absolute file paths or credential-like
    strings, the sanitized message SHALL NOT contain those sensitive values but
    SHALL still convey a meaningful failure reason.

    **Validates: Requirements 1.10**
    """

    @given(
        path=_absolute_path_strategy(),
        prefix=_context_text_strategy(),
        suffix=_context_text_strategy(),
    )
    @settings(max_examples=100)
    def test_absolute_paths_are_removed(
        self, path: str, prefix: str, suffix: str
    ) -> None:
        """Sanitized output must not contain any generated absolute path.

        # Feature: containerlab-mcp, Property 8: Error Response Sanitization
        **Validates: Requirements 1.10**
        """
        stderr = f"{prefix} {path} {suffix}"
        parser = OutputParser()
        result = parser.sanitize_error(stderr)

        # The absolute path must be removed
        assert path not in result, (
            f"Absolute path '{path}' was not sanitized from output"
        )
        # The result should still be non-empty (meaningful)
        assert len(result.strip()) > 0, "Sanitized result is empty"

    @given(
        credential=_credential_pattern_strategy(),
        prefix=_context_text_strategy(),
        suffix=_context_text_strategy(),
    )
    @settings(max_examples=100)
    def test_credential_patterns_are_removed(
        self, credential: str, prefix: str, suffix: str
    ) -> None:
        """Sanitized output must not contain any credential-like key=value string.

        # Feature: containerlab-mcp, Property 8: Error Response Sanitization
        **Validates: Requirements 1.10**
        """
        stderr = f"{prefix} {credential} {suffix}"
        parser = OutputParser()
        result = parser.sanitize_error(stderr)

        # The full credential pattern must be removed
        assert credential not in result, (
            f"Credential pattern '{credential}' was not sanitized from output"
        )
        # The result should still be non-empty (meaningful)
        assert len(result.strip()) > 0, "Sanitized result is empty"

    @given(
        paths=st.lists(_absolute_path_strategy(), min_size=1, max_size=5),
        credentials=st.lists(_credential_pattern_strategy(), min_size=1, max_size=3),
        context=_context_text_strategy(),
    )
    @settings(max_examples=100)
    def test_combined_sensitive_data_all_removed(
        self, paths: list[str], credentials: list[str], context: str
    ) -> None:
        """When both paths and credentials are present, all are sanitized.

        # Feature: containerlab-mcp, Property 8: Error Response Sanitization
        **Validates: Requirements 1.10**
        """
        # Build a stderr with mixed sensitive data
        parts = [context] + paths + credentials + [context]
        stderr = " ".join(parts)
        parser = OutputParser()
        result = parser.sanitize_error(stderr)

        for path in paths:
            assert path not in result, (
                f"Path '{path}' was not sanitized"
            )
        for cred in credentials:
            assert cred not in result, (
                f"Credential '{cred}' was not sanitized"
            )

    @given(message=_context_text_strategy())
    @settings(max_examples=100)
    def test_clean_messages_pass_through(self, message: str) -> None:
        """Messages without sensitive data pass through unchanged (modulo whitespace).

        # Feature: containerlab-mcp, Property 8: Error Response Sanitization
        **Validates: Requirements 1.10**
        """
        # Ensure the message doesn't accidentally contain path or credential patterns
        assume("/" not in message)
        assume("password" not in message.lower())
        assume("token" not in message.lower())
        assume("secret" not in message.lower())
        assume("key" not in message.lower())
        assume("credential" not in message.lower())

        parser = OutputParser()
        result = parser.sanitize_error(message)
        assert result == message


# --- Strategies for large strings ---


def _large_text_strategy(min_size: int = 4097, max_size: int = 10000) -> st.SearchStrategy[str]:
    """Generate large strings efficiently by repeating a small pattern.

    This avoids Hypothesis health check failures with large min_size text.
    """
    base = st.text(
        alphabet=st.characters(categories=("L", "N", "P", "Z")),
        min_size=10,
        max_size=100,
    )
    count = st.integers(min_value=min_size // 100 + 1, max_value=max_size // 10)
    return st.builds(
        lambda b, n: (b * n)[:max(min_size, min(len(b) * n, max_size))],
        base,
        count,
    ).filter(lambda s: min_size <= len(s) <= max_size)


# --- Property 9: Stderr Truncation ---


class TestStderrTruncation:
    """Property 9: Stderr Truncation.

    For any stderr string, if length exceeds 4096 characters the result SHALL
    be truncated to exactly 4096 chars. If ≤4096, included in full.

    **Validates: Requirements 4.3**
    """

    @given(stderr=_large_text_strategy(min_size=4097, max_size=10000))
    @settings(max_examples=100)
    def test_long_stderr_truncated_to_4096(self, stderr: str) -> None:
        """Stderr longer than 4096 characters is truncated to exactly 4096.

        # Feature: containerlab-mcp, Property 9: Stderr Truncation
        **Validates: Requirements 4.3**
        """
        parser = OutputParser()
        result = parser.truncate_stderr(stderr)

        assert len(result) == 4096, (
            f"Expected exactly 4096 chars, got {len(result)}"
        )
        # The truncated result must be the first 4096 characters
        assert result == stderr[:4096]

    @given(stderr=st.text(min_size=0, max_size=4096))
    @settings(max_examples=100)
    def test_short_stderr_included_in_full(self, stderr: str) -> None:
        """Stderr of 4096 characters or fewer is returned unchanged.

        # Feature: containerlab-mcp, Property 9: Stderr Truncation
        **Validates: Requirements 4.3**
        """
        parser = OutputParser()
        result = parser.truncate_stderr(stderr)

        assert result == stderr, (
            f"Stderr of length {len(stderr)} should be returned unchanged"
        )

    @given(
        short=st.text(min_size=0, max_size=4096),
        long=_large_text_strategy(min_size=4097, max_size=10000),
    )
    @settings(max_examples=100)
    def test_truncation_boundary_invariant(self, short: str, long: str) -> None:
        """For any stderr: result length is min(len(stderr), 4096) and is a prefix.

        # Feature: containerlab-mcp, Property 9: Stderr Truncation
        **Validates: Requirements 4.3**
        """
        parser = OutputParser()

        # Short strings pass through unchanged
        result_short = parser.truncate_stderr(short)
        assert len(result_short) == len(short)
        assert result_short == short

        # Long strings are truncated to exactly 4096
        result_long = parser.truncate_stderr(long)
        assert len(result_long) == 4096
        assert long.startswith(result_long)

    @given(stderr=_large_text_strategy(min_size=4097, max_size=8000))
    @settings(max_examples=100)
    def test_sanitize_error_respects_truncation(self, stderr: str) -> None:
        """sanitize_error() also truncates to 4096 (applied after sanitization).

        # Feature: containerlab-mcp, Property 9: Stderr Truncation
        **Validates: Requirements 4.3**
        """
        parser = OutputParser()
        result = parser.sanitize_error(stderr)

        assert len(result) <= 4096, (
            f"sanitize_error result exceeds 4096 chars: {len(result)}"
        )
