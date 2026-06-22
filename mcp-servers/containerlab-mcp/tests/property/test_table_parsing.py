# Feature: containerlab-mcp, Property 2: Table Parsing Correctness
"""Property-based tests for table parsing correctness.

**Validates: Requirements 4.2, 4.6**

For any well-formed table output consisting of a header row and zero or more
data rows (where columns are separated by consistent whitespace or delimiters),
parsing SHALL produce a JSON array where each element is an object with keys
matching the normalized (lowercase snake_case) column headers and values matching
the corresponding row cells. A table with zero data rows SHALL produce an empty array.
"""

from __future__ import annotations

import re

from hypothesis import given, assume, settings
from hypothesis import strategies as st

from containerlab_mcp.parser import OutputParser


# --- Strategies ---

def alpha_header_strategy() -> st.SearchStrategy[str]:
    """Generate alphabetic column header strings (1-3 words)."""
    word = st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
        min_size=2,
        max_size=8,
    )
    # Single word or multi-word headers
    return st.one_of(
        word,
        st.tuples(word, word).map(lambda t: f"{t[0]} {t[1]}"),
    )


def cell_value_strategy() -> st.SearchStrategy[str]:
    """Generate cell values that don't contain pipe or newline characters."""
    return st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "S"),
            blacklist_characters="|+\n\r",
        ),
        min_size=1,
        max_size=12,
    )


def build_clab_table(headers: list[str], rows: list[list[str]]) -> str:
    """Build a clab-style table string from headers and rows.

    Format:
        +------+--------+
        | Col1 | Col2   |
        +------+--------+
        | val1 | val2   |
        +------+--------+
    """
    # Determine column widths (max of header and all row values, min width 3)
    num_cols = len(headers)
    col_widths = []
    for i in range(num_cols):
        max_width = len(headers[i])
        for row in rows:
            max_width = max(max_width, len(row[i]))
        col_widths.append(max(max_width, 3))

    # Build separator line
    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    # Build header line
    header_cells = []
    for i, h in enumerate(headers):
        header_cells.append(f" {h:<{col_widths[i]}} ")
    header_line = "|" + "|".join(header_cells) + "|"

    # Build data lines
    data_lines = []
    for row in rows:
        row_cells = []
        for i, cell in enumerate(row):
            row_cells.append(f" {cell:<{col_widths[i]}} ")
        data_lines.append("|" + "|".join(row_cells) + "|")

    # Assemble table
    lines = [separator, header_line, separator]
    for data_line in data_lines:
        lines.append(data_line)
        lines.append(separator)

    # If no data rows, just header + two separators
    if not rows:
        lines = [separator, header_line, separator]

    return "\n".join(lines)


def normalize_header(header: str) -> str:
    """Mirror the parser's normalization logic for verification."""
    if header.strip() == "#":
        return "number"

    result = header.lower()
    result = re.sub(r"[\s\-]+", "_", result)
    result = re.sub(r"[^a-z0-9_]", "", result)
    result = re.sub(r"_+", "_", result)
    result = result.strip("_")
    return result


# --- Property Tests ---


@settings(max_examples=100)
@given(
    headers=st.lists(alpha_header_strategy(), min_size=1, max_size=6),
    rows=st.data(),
)
def test_table_parsing_produces_correct_rows_and_headers(headers, rows):
    """Table parsing produces correct number of rows with normalized headers.

    For any well-formed table with N headers and M data rows, parse_table()
    shall return exactly M dicts, each with keys matching normalized headers.
    """
    # Ensure unique normalized headers (parser can't distinguish duplicates)
    normalized = [normalize_header(h) for h in headers]
    assume(len(set(normalized)) == len(normalized))
    # Ensure no empty normalized headers
    assume(all(len(n) > 0 for n in normalized))

    num_cols = len(headers)
    # Draw a list of rows, each row has exactly num_cols cells
    row_data = rows.draw(
        st.lists(
            st.lists(cell_value_strategy(), min_size=num_cols, max_size=num_cols),
            min_size=0,
            max_size=5,
        )
    )

    # Build the table string
    table_str = build_clab_table(headers, row_data)

    # Parse
    parser = OutputParser()
    result = parser.parse_table(table_str)

    # Verify correct number of rows
    assert len(result) == len(row_data), (
        f"Expected {len(row_data)} rows, got {len(result)}"
    )

    # Verify each row has the correct keys (normalized headers)
    expected_keys = set(normalized)
    for i, row_dict in enumerate(result):
        assert set(row_dict.keys()) == expected_keys, (
            f"Row {i}: expected keys {expected_keys}, got {set(row_dict.keys())}"
        )

    # Verify cell values match (stripped)
    for i, row_dict in enumerate(result):
        for j, header in enumerate(headers):
            key = normalized[j]
            expected_value = row_data[i][j].strip()
            actual_value = row_dict[key].strip()
            assert actual_value == expected_value, (
                f"Row {i}, col '{key}': expected '{expected_value}', got '{actual_value}'"
            )


@settings(max_examples=100)
@given(
    headers=st.lists(alpha_header_strategy(), min_size=1, max_size=6),
)
def test_empty_table_produces_empty_array(headers):
    """A table with zero data rows SHALL produce an empty array.

    For any set of headers, a table with only the header row and no data
    rows must return an empty list.
    """
    # Ensure unique normalized headers
    normalized = [normalize_header(h) for h in headers]
    assume(len(set(normalized)) == len(normalized))
    assume(all(len(n) > 0 for n in normalized))

    # Build table with no data rows
    table_str = build_clab_table(headers, [])

    # Parse
    parser = OutputParser()
    result = parser.parse_table(table_str)

    # Must be an empty array
    assert result == [], f"Expected empty list, got {result}"


@settings(max_examples=100)
@given(
    headers=st.lists(alpha_header_strategy(), min_size=1, max_size=6),
)
def test_header_normalization_is_lowercase_snake_case(headers):
    """Parsed keys must be lowercase snake_case versions of column headers.

    For any header, the normalized key shall be lowercase, use underscores
    for separators, and contain only alphanumeric characters and underscores.
    """
    normalized = [normalize_header(h) for h in headers]
    assume(len(set(normalized)) == len(normalized))
    assume(all(len(n) > 0 for n in normalized))

    # Build a table with one data row so we can inspect keys
    row = ["x"] * len(headers)
    table_str = build_clab_table(headers, [row])

    parser = OutputParser()
    result = parser.parse_table(table_str)

    assert len(result) == 1
    for key in result[0].keys():
        # Must be lowercase
        assert key == key.lower(), f"Key '{key}' is not lowercase"
        # Must match snake_case pattern (alphanumeric and underscores only)
        assert re.match(r"^[a-z0-9][a-z0-9_]*[a-z0-9]$|^[a-z0-9]$", key), (
            f"Key '{key}' is not valid snake_case"
        )
