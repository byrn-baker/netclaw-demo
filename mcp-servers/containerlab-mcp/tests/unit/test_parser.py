"""Unit tests for OutputParser.parse_table()."""

import pytest

from containerlab_mcp.parser import OutputParser


@pytest.fixture
def parser() -> OutputParser:
    return OutputParser()


class TestParseTable:
    """Tests for table-to-JSON parsing."""

    def test_parse_typical_clab_inspect_output(self, parser: OutputParser) -> None:
        """Parse a typical clab inspect table with multiple rows."""
        raw = (
            "+---+------+--------------+---------------------+------+---------+----------------+----------------------+\n"
            "| # | Name | Container ID | Image               | Kind | State   | IPv4 Address   | IPv6 Address         |\n"
            "+---+------+--------------+---------------------+------+---------+----------------+----------------------+\n"
            "| 1 | p1   | abc123       | ghcr.io/frr:latest  | linux| running | 172.20.20.2/24 | 2001:172:20:20::2/64 |\n"
            "+---+------+--------------+---------------------+------+---------+----------------+----------------------+\n"
        )
        result = parser.parse_table(raw)

        assert len(result) == 1
        assert result[0]["number"] == "1"
        assert result[0]["name"] == "p1"
        assert result[0]["container_id"] == "abc123"
        assert result[0]["image"] == "ghcr.io/frr:latest"
        assert result[0]["kind"] == "linux"
        assert result[0]["state"] == "running"
        assert result[0]["ipv4_address"] == "172.20.20.2/24"
        assert result[0]["ipv6_address"] == "2001:172:20:20::2/64"

    def test_parse_multiple_data_rows(self, parser: OutputParser) -> None:
        """Parse table with multiple data rows."""
        raw = (
            "+---+------+--------------+---------------------+-------+---------+\n"
            "| # | Name | Container ID | Image               | Kind  | State   |\n"
            "+---+------+--------------+---------------------+-------+---------+\n"
            "| 1 | r1   | aaa111       | ghcr.io/frr:latest  | linux | running |\n"
            "| 2 | r2   | bbb222       | ghcr.io/srl:latest  | srl   | running |\n"
            "| 3 | r3   | ccc333       | ghcr.io/ceos:latest | ceos  | running |\n"
            "+---+------+--------------+---------------------+-------+---------+\n"
        )
        result = parser.parse_table(raw)

        assert len(result) == 3
        assert result[0]["name"] == "r1"
        assert result[1]["name"] == "r2"
        assert result[2]["name"] == "r3"
        assert result[0]["container_id"] == "aaa111"
        assert result[2]["kind"] == "ceos"

    def test_parse_empty_table_returns_empty_list(self, parser: OutputParser) -> None:
        """A table with headers but no data rows returns an empty list."""
        raw = (
            "+---+------+--------------+\n"
            "| # | Name | Container ID |\n"
            "+---+------+--------------+\n"
            "+---+------+--------------+\n"
        )
        result = parser.parse_table(raw)
        assert result == []

    def test_parse_empty_string_returns_empty_list(self, parser: OutputParser) -> None:
        """An empty string returns an empty list."""
        assert parser.parse_table("") == []

    def test_parse_non_table_output_returns_empty_list(
        self, parser: OutputParser
    ) -> None:
        """Output that doesn't look like a table returns an empty list."""
        raw = "Some random output\nwithout any table format\n"
        assert parser.parse_table(raw) == []

    def test_header_normalization_spaces_to_underscores(
        self, parser: OutputParser
    ) -> None:
        """Column headers with spaces become snake_case."""
        raw = (
            "+----------------+----------------------+\n"
            "| IPv4 Address   | IPv6 Address         |\n"
            "+----------------+----------------------+\n"
            "| 172.20.20.2/24 | 2001:172:20:20::2/64 |\n"
            "+----------------+----------------------+\n"
        )
        result = parser.parse_table(raw)
        assert "ipv4_address" in result[0]
        assert "ipv6_address" in result[0]

    def test_header_normalization_hash_becomes_number(
        self, parser: OutputParser
    ) -> None:
        """The '#' column header is normalized to 'number'."""
        raw = (
            "+---+------+\n"
            "| # | Name |\n"
            "+---+------+\n"
            "| 1 | foo  |\n"
            "+---+------+\n"
        )
        result = parser.parse_table(raw)
        assert "number" in result[0]
        assert result[0]["number"] == "1"

    def test_header_normalization_special_chars_removed(
        self, parser: OutputParser
    ) -> None:
        """Special characters are stripped from headers."""
        raw = (
            "+-----------+----------+\n"
            "| Foo (bar) | Baz/Qux  |\n"
            "+-----------+----------+\n"
            "| val1      | val2     |\n"
            "+-----------+----------+\n"
        )
        result = parser.parse_table(raw)
        assert "foo_bar" in result[0]
        assert "bazqux" in result[0]

    def test_cell_values_are_stripped(self, parser: OutputParser) -> None:
        """Cell values have leading/trailing whitespace removed."""
        raw = (
            "+----------+----------+\n"
            "| Name     | Status   |\n"
            "+----------+----------+\n"
            "|   hello  |  world   |\n"
            "+----------+----------+\n"
        )
        result = parser.parse_table(raw)
        assert result[0]["name"] == "hello"
        assert result[0]["status"] == "world"

    def test_only_one_separator_returns_empty(self, parser: OutputParser) -> None:
        """A single separator line is not a valid table."""
        raw = "+---+------+\n| # | Name |\n"
        assert parser.parse_table(raw) == []


class TestParseJson:
    """Tests for JSON pass-through parsing."""

    def test_parse_valid_json_object(self, parser: OutputParser) -> None:
        """Parse a valid JSON object string."""
        raw = '{"name": "lab1", "nodes": 3}'
        result = parser.parse_json(raw)
        assert result == {"name": "lab1", "nodes": 3}

    def test_parse_valid_json_array(self, parser: OutputParser) -> None:
        """Parse a valid JSON array string."""
        raw = '[{"name": "r1"}, {"name": "r2"}]'
        result = parser.parse_json(raw)
        assert result == [{"name": "r1"}, {"name": "r2"}]

    def test_parse_empty_object(self, parser: OutputParser) -> None:
        """Parse an empty JSON object."""
        assert parser.parse_json("{}") == {}

    def test_parse_empty_array(self, parser: OutputParser) -> None:
        """Parse an empty JSON array."""
        assert parser.parse_json("[]") == []

    def test_parse_invalid_json_raises_value_error(
        self, parser: OutputParser
    ) -> None:
        """Invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON output"):
            parser.parse_json("not json at all")

    def test_parse_scalar_raises_value_error(self, parser: OutputParser) -> None:
        """A JSON scalar (string, number) raises ValueError."""
        with pytest.raises(ValueError, match="Expected JSON object or array"):
            parser.parse_json('"just a string"')

    def test_parse_nested_json(self, parser: OutputParser) -> None:
        """Parse nested JSON structures."""
        raw = '{"topology": {"nodes": [{"name": "r1", "kind": "srl"}]}}'
        result = parser.parse_json(raw)
        assert result["topology"]["nodes"][0]["name"] == "r1"


class TestSanitizeError:
    """Tests for error message sanitization."""

    def test_strips_absolute_paths(self, parser: OutputParser) -> None:
        """Absolute file paths are replaced with <path>."""
        stderr = "Error: cannot read /home/user/.ssh/id_rsa: permission denied"
        result = parser.sanitize_error(stderr)
        assert "/home/user/.ssh/id_rsa" not in result
        assert "<path>" in result
        assert "permission denied" in result

    def test_strips_credential_password(self, parser: OutputParser) -> None:
        """password=... patterns are stripped."""
        stderr = "connection failed password=s3cret123 to host"
        result = parser.sanitize_error(stderr)
        assert "s3cret123" not in result
        assert "password=" not in result

    def test_strips_credential_token(self, parser: OutputParser) -> None:
        """token=... patterns are stripped."""
        stderr = "auth error token=abc123xyz host unreachable"
        result = parser.sanitize_error(stderr)
        assert "abc123xyz" not in result
        assert "token=" not in result

    def test_strips_credential_key(self, parser: OutputParser) -> None:
        """key=... patterns are stripped."""
        stderr = "failed: key=my_secret_key connection refused"
        result = parser.sanitize_error(stderr)
        assert "my_secret_key" not in result

    def test_preserves_meaningful_message(self, parser: OutputParser) -> None:
        """The error message remains meaningful after sanitization."""
        stderr = "Error: topology file /etc/containerlab/topo.yml not found"
        result = parser.sanitize_error(stderr)
        assert "Error:" in result
        assert "not found" in result

    def test_truncates_long_error(self, parser: OutputParser) -> None:
        """Long error messages are truncated to 4096 chars."""
        stderr = "x" * 5000
        result = parser.sanitize_error(stderr)
        assert len(result) <= 4096

    def test_no_sensitive_info_passes_through(self, parser: OutputParser) -> None:
        """A clean error message passes through unchanged (minus whitespace)."""
        stderr = "Error: lab 'mylab' is not running"
        result = parser.sanitize_error(stderr)
        assert result == stderr

    def test_multiple_paths_all_sanitized(self, parser: OutputParser) -> None:
        """Multiple absolute paths are all replaced."""
        stderr = "tried /usr/bin/clab then /opt/containerlab/bin/clab"
        result = parser.sanitize_error(stderr)
        assert "/usr/bin/clab" not in result
        assert "/opt/containerlab/bin/clab" not in result
        assert result.count("<path>") == 2


class TestTruncateStderr:
    """Tests for stderr truncation."""

    def test_short_string_unchanged(self, parser: OutputParser) -> None:
        """String shorter than max_length is returned as-is."""
        stderr = "short error"
        assert parser.truncate_stderr(stderr) == stderr

    def test_exact_length_unchanged(self, parser: OutputParser) -> None:
        """String exactly at max_length is returned as-is."""
        stderr = "x" * 4096
        assert parser.truncate_stderr(stderr) == stderr

    def test_long_string_truncated(self, parser: OutputParser) -> None:
        """String longer than max_length is truncated."""
        stderr = "x" * 5000
        result = parser.truncate_stderr(stderr)
        assert len(result) == 4096

    def test_custom_max_length(self, parser: OutputParser) -> None:
        """Custom max_length is respected."""
        stderr = "hello world"
        result = parser.truncate_stderr(stderr, max_length=5)
        assert result == "hello"

    def test_empty_string(self, parser: OutputParser) -> None:
        """Empty string passes through."""
        assert parser.truncate_stderr("") == ""
