"""Output parser for ContainerLab CLI responses.

Converts raw CLI output (tables, JSON) into structured Python objects.
"""

from __future__ import annotations

import json
import re


class OutputParser:
    """Parses raw ContainerLab CLI output into structured data."""

    def parse_table(self, raw: str) -> list[dict[str, str]]:
        """Parse a table with +---+ separators into a list of dicts.

        ContainerLab's inspect output uses a format like:
            +---+------+--------------+
            | # | Name | Container ID |
            +---+------+--------------+
            | 1 | p1   | abc123       |
            +---+------+--------------+

        Column headers are normalized to lowercase snake_case.
        A table with zero data rows returns an empty list.

        Args:
            raw: Raw table string from CLI output.

        Returns:
            A list of dicts, one per data row, keyed by normalized headers.
        """
        lines = raw.splitlines()

        # Find separator lines (lines matching +---+---+ pattern)
        separator_pattern = re.compile(r"^\+[-+]+\+$")
        separator_indices = [
            i for i, line in enumerate(lines) if separator_pattern.match(line.strip())
        ]

        if len(separator_indices) < 2:
            # Not a valid table — no separators found or only one
            return []

        # The header row is between the first and second separator
        header_line = lines[separator_indices[0] + 1]

        # Detect column boundaries from the first separator line
        first_separator = lines[separator_indices[0]].strip()
        col_boundaries = self._detect_column_boundaries(first_separator)

        # Extract and normalize headers
        headers = self._extract_cells(header_line, col_boundaries)
        normalized_headers = [self._normalize_header(h) for h in headers]

        # Data rows are between the second separator and the last separator
        # (or between each pair of separators after the header)
        data_rows: list[dict[str, str]] = []

        # Collect all non-separator, non-empty lines after the second separator
        # and before the last separator
        for i in range(separator_indices[1] + 1, len(lines)):
            line = lines[i]
            stripped = line.strip()

            # Skip separator lines
            if separator_pattern.match(stripped):
                continue

            # Skip empty lines
            if not stripped:
                continue

            # Must be a pipe-delimited data row
            if not stripped.startswith("|"):
                continue

            cells = self._extract_cells(line, col_boundaries)
            row = {}
            for header, cell in zip(normalized_headers, cells):
                row[header] = cell
            data_rows.append(row)

        return data_rows

    def _detect_column_boundaries(self, separator: str) -> list[tuple[int, int]]:
        """Detect column start/end positions from a separator line.

        A separator looks like: +---+------+--------------+
        Each segment between + characters is a column.

        Returns:
            List of (start, end) character positions for each column's content area.
        """
        boundaries: list[tuple[int, int]] = []
        i = 0
        while i < len(separator):
            if separator[i] == "+":
                # Find the next +
                next_plus = separator.find("+", i + 1)
                if next_plus == -1:
                    break
                # Content area is between the + characters (exclusive of +)
                # The pipe characters in data rows align with the + positions
                # Content starts at i+1 and ends at next_plus-1 (within the pipes)
                boundaries.append((i + 1, next_plus))
                i = next_plus
            else:
                i += 1
        return boundaries

    def _extract_cells(
        self, line: str, boundaries: list[tuple[int, int]]
    ) -> list[str]:
        """Extract cell values from a data/header line using column boundaries.

        Args:
            line: A pipe-delimited line like "| # | Name | Container ID |"
            boundaries: Column boundary positions from the separator.

        Returns:
            List of stripped cell values.
        """
        cells: list[str] = []
        for start, end in boundaries:
            if start < len(line) and end <= len(line):
                cell = line[start:end].strip().strip("|").strip()
            elif start < len(line):
                cell = line[start:].strip().strip("|").strip()
            else:
                cell = ""
            cells.append(cell)
        return cells

    def _normalize_header(self, header: str) -> str:
        """Normalize a column header to lowercase snake_case.

        - Convert to lowercase
        - Replace spaces with underscores
        - Remove special characters (keep alphanumeric and underscores)
        - Collapse multiple underscores

        Args:
            header: Raw header string (e.g., "Container ID", "IPv4 Address", "#")

        Returns:
            Normalized header (e.g., "container_id", "ipv4_address", "number")
        """
        # Special case for "#" column
        if header.strip() == "#":
            return "number"

        # Lowercase
        result = header.lower()

        # Replace spaces and hyphens with underscores
        result = re.sub(r"[\s\-]+", "_", result)

        # Remove special characters (keep alphanumeric and underscores)
        result = re.sub(r"[^a-z0-9_]", "", result)

        # Collapse multiple underscores
        result = re.sub(r"_+", "_", result)

        # Strip leading/trailing underscores
        result = result.strip("_")

        return result

    # --- JSON pass-through parsing ---

    def parse_json(self, raw: str) -> dict | list:
        """Parse raw JSON string from CLI output.

        Used for commands invoked with `--format json` that produce
        JSON output directly.

        Args:
            raw: Raw JSON string from CLI stdout.

        Returns:
            Parsed JSON object (dict or list).

        Raises:
            ValueError: If the string is not valid JSON.
        """
        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"Invalid JSON output: {exc}") from exc

        if not isinstance(result, (dict, list)):
            raise ValueError(
                f"Expected JSON object or array, got {type(result).__name__}"
            )
        return result

    # --- Error message sanitization ---

    # Pattern for absolute filesystem paths (Unix-style)
    _PATH_PATTERN = re.compile(r"/(?:[a-zA-Z0-9_.\-]+/)+[a-zA-Z0-9_.\-]+")

    # Pattern for credential-like key=value strings
    _CREDENTIAL_PATTERN = re.compile(
        r"\b(password|passwd|token|secret|key|credential|auth_token|api_key)"
        r"\s*[=:]\s*\S+",
        re.IGNORECASE,
    )

    def sanitize_error(self, stderr: str) -> str:
        """Strip sensitive information from error messages.

        Removes:
        - Absolute filesystem paths (replaced with <path>)
        - Credential-like strings (password=..., token=..., key=..., etc.)

        The result is also truncated to 4096 characters.

        Args:
            stderr: Raw stderr output from CLI execution.

        Returns:
            Sanitized error message safe to expose to agents.
        """
        # Replace absolute paths with <path>
        sanitized = self._PATH_PATTERN.sub("<path>", stderr)

        # Strip credential-like key=value pairs
        sanitized = self._CREDENTIAL_PATTERN.sub("", sanitized)

        # Clean up any resulting double/triple spaces from removals
        sanitized = re.sub(r"  +", " ", sanitized)

        # Truncate to 4096 characters
        return self.truncate_stderr(sanitized)

    def truncate_stderr(self, stderr: str, max_length: int = 4096) -> str:
        """Truncate stderr output to a maximum length.

        Args:
            stderr: Raw or pre-processed stderr string.
            max_length: Maximum allowed length (default: 4096).

        Returns:
            The stderr string, truncated to max_length characters if needed.
        """
        if len(stderr) <= max_length:
            return stderr
        return stderr[:max_length]
