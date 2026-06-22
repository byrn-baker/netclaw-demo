# Feature: containerlab-mcp, Property 1: Response Schema Invariant
"""Property test verifying the Response Schema Invariant.

For any tool invocation (regardless of which tool is called and whether it
succeeds or fails), the returned JSON object SHALL contain a `status` field
with value "success" or "error", a `command` field containing the executed
CLI command string, and a `duration_ms` field that is a non-negative integer.
If status is "success", a `data` field SHALL be present.
If status is "error", a `message` field SHALL be present.

Validates: Requirements 1.9, 4.1, 4.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from containerlab_mcp.models import StructuredResponse


# --- Strategies ---

# Strategy for generating arbitrary command strings
command_strategy = st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != "")

# Strategy for non-negative integer durations
duration_ms_strategy = st.integers(min_value=0, max_value=10_000_000)

# Strategy for arbitrary data payloads (success responses)
data_strategy = st.one_of(
    st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=5),
    st.lists(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=3), max_size=5),
)

# Strategy for error messages
message_strategy = st.text(min_size=1, max_size=500)

# Strategy for exit codes on error
exit_code_strategy = st.integers(min_value=1, max_value=255)


# Strategy for a successful StructuredResponse
success_response_strategy = st.builds(
    StructuredResponse,
    status=st.just("success"),
    data=data_strategy,
    command=command_strategy,
    duration_ms=duration_ms_strategy,
    message=st.just(None),
    code=st.just(None),
)

# Strategy for an error StructuredResponse
error_response_strategy = st.builds(
    StructuredResponse,
    status=st.just("error"),
    data=st.just(None),
    command=command_strategy,
    duration_ms=duration_ms_strategy,
    message=message_strategy,
    code=st.one_of(st.just(None), exit_code_strategy),
)

# Combined strategy for any valid StructuredResponse
any_response_strategy = st.one_of(success_response_strategy, error_response_strategy)


# --- Property Tests ---


@given(response=success_response_strategy)
@settings(max_examples=100)
def test_success_response_has_required_fields(response: StructuredResponse) -> None:
    """A success response SHALL have status, command, duration_ms, and data fields.

    **Validates: Requirements 1.9, 4.1, 4.4**
    """
    obj = response.model_dump()

    # status must be "success"
    assert obj["status"] == "success"

    # command must be a non-empty string
    assert isinstance(obj["command"], str)
    assert len(obj["command"]) > 0

    # duration_ms must be a non-negative integer
    assert isinstance(obj["duration_ms"], int)
    assert obj["duration_ms"] >= 0

    # data must be present (not None) for success responses
    assert obj["data"] is not None


@given(response=error_response_strategy)
@settings(max_examples=100)
def test_error_response_has_required_fields(response: StructuredResponse) -> None:
    """An error response SHALL have status, command, duration_ms, and message fields.

    **Validates: Requirements 1.9, 4.1, 4.4**
    """
    obj = response.model_dump()

    # status must be "error"
    assert obj["status"] == "error"

    # command must be a non-empty string
    assert isinstance(obj["command"], str)
    assert len(obj["command"]) > 0

    # duration_ms must be a non-negative integer
    assert isinstance(obj["duration_ms"], int)
    assert obj["duration_ms"] >= 0

    # message must be present (not None) for error responses
    assert obj["message"] is not None
    assert isinstance(obj["message"], str)
    assert len(obj["message"]) > 0


@given(response=any_response_strategy)
@settings(max_examples=100)
def test_all_responses_contain_base_schema_fields(response: StructuredResponse) -> None:
    """Any response (success or error) SHALL contain status, command, and duration_ms.

    **Validates: Requirements 1.9, 4.1, 4.4**
    """
    obj = response.model_dump()

    # status must be one of the two allowed values
    assert obj["status"] in ("success", "error")

    # command must always be present as a string
    assert "command" in obj
    assert isinstance(obj["command"], str)

    # duration_ms must always be present as a non-negative integer
    assert "duration_ms" in obj
    assert isinstance(obj["duration_ms"], int)
    assert obj["duration_ms"] >= 0


@given(response=any_response_strategy)
@settings(max_examples=100)
def test_status_determines_conditional_fields(response: StructuredResponse) -> None:
    """Status value SHALL determine which conditional fields are present.

    If status is "success", data SHALL be present.
    If status is "error", message SHALL be present.

    **Validates: Requirements 1.9, 4.1, 4.4**
    """
    obj = response.model_dump()

    if obj["status"] == "success":
        assert obj["data"] is not None, "Success response must have data field"
    elif obj["status"] == "error":
        assert obj["message"] is not None, "Error response must have message field"
        assert len(obj["message"]) > 0, "Error message must be non-empty"


@given(duration=st.integers(min_value=0, max_value=2**31))
@settings(max_examples=100)
def test_duration_ms_accepts_any_non_negative_integer(duration: int) -> None:
    """duration_ms SHALL accept any non-negative integer value.

    **Validates: Requirements 4.4**
    """
    response = StructuredResponse(
        status="success",
        data={"result": "ok"},
        command="clab version",
        duration_ms=duration,
    )
    assert response.duration_ms == duration
    assert response.duration_ms >= 0


@given(duration=st.integers(max_value=-1))
@settings(max_examples=50)
def test_duration_ms_rejects_negative_values(duration: int) -> None:
    """duration_ms SHALL reject negative integer values via Pydantic validation.

    **Validates: Requirements 4.4**
    """
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StructuredResponse(
            status="success",
            data={"result": "ok"},
            command="clab version",
            duration_ms=duration,
        )


@given(status=st.sampled_from(["success", "error"]))
@settings(max_examples=50)
def test_status_field_only_accepts_valid_literals(status: str) -> None:
    """status field SHALL only accept 'success' or 'error' as valid values.

    **Validates: Requirements 1.9, 4.1**
    """
    if status == "success":
        response = StructuredResponse(
            status=status,
            data={"result": "ok"},
            command="clab inspect",
            duration_ms=42,
        )
    else:
        response = StructuredResponse(
            status=status,
            data=None,
            command="clab inspect",
            duration_ms=42,
            message="Something went wrong",
        )
    assert response.status == status


@given(invalid_status=st.text(min_size=1, max_size=20).filter(lambda s: s not in ("success", "error")))
@settings(max_examples=50)
def test_status_field_rejects_invalid_values(invalid_status: str) -> None:
    """status field SHALL reject values other than 'success' or 'error'.

    **Validates: Requirements 1.9, 4.1**
    """
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StructuredResponse(
            status=invalid_status,
            data=None,
            command="clab version",
            duration_ms=0,
        )
