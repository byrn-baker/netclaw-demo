"""Property-based tests for the destroy safety gate.

# Feature: containerlab-mcp, Property 5: Destroy Safety Gate

Validates: Requirements 5.1, 5.2, 5.3, 5.4
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from containerlab_mcp.safety import SafetyGate


# --- Strategies ---

# Topology names: non-empty strings (realistic lab names)
topology_name_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: len(s.strip()) > 0)

# Confirmation strings that differ from target (for mismatch testing)
# We'll generate pairs where confirm != target


# --- Property 5: Destroy Safety Gate ---
# Feature: containerlab-mcp, Property 5: Destroy Safety Gate


class TestDestroySafetyGate:
    """Property 5: Destroy safety gate only allows execution when confirmation matches exactly."""

    @given(
        target_name=topology_name_st,
        cleanup=st.booleans(),
    )
    @settings(max_examples=100)
    def test_exact_match_no_cleanup_passes(
        self, target_name: str, cleanup: bool
    ) -> None:
        """Validates: Requirements 5.1, 5.2

        When confirm_topology_name exactly matches the target topology name
        and cleanup is False (or cleanup is True with confirm_cleanup=True),
        validation passes.
        """
        gate = SafetyGate()

        # When cleanup is False, matching name is sufficient
        # When cleanup is True, we also need confirm_cleanup=True
        confirm_cleanup = True if cleanup else None

        result = gate.validate_destroy(
            target_name=target_name,
            confirm_topology_name=target_name,
            cleanup=cleanup,
            confirm_cleanup=confirm_cleanup,
        )

        assert result.passed is True
        assert result.error_message is None

    @given(target_name=topology_name_st)
    @settings(max_examples=100)
    def test_missing_confirmation_rejects(self, target_name: str) -> None:
        """Validates: Requirements 5.1, 5.2

        When confirm_topology_name is None, the operation is rejected
        without CLI execution.
        """
        gate = SafetyGate()

        result = gate.validate_destroy(
            target_name=target_name,
            confirm_topology_name=None,
            cleanup=False,
            confirm_cleanup=None,
        )

        assert result.passed is False
        assert result.error_message is not None

    @given(
        target_name=topology_name_st,
        confirm_name=topology_name_st,
        cleanup=st.booleans(),
        confirm_cleanup=st.one_of(st.none(), st.booleans()),
    )
    @settings(max_examples=100)
    def test_name_mismatch_rejects(
        self,
        target_name: str,
        confirm_name: str,
        cleanup: bool,
        confirm_cleanup: bool | None,
    ) -> None:
        """Validates: Requirements 5.1, 5.2

        When confirm_topology_name does not exactly match the target topology name
        (case-sensitive), the operation is rejected without CLI execution.
        """
        # Ensure the confirmation string differs from target
        if confirm_name == target_name:
            # Mutate to guarantee mismatch
            confirm_name = confirm_name + "_mismatch"

        gate = SafetyGate()

        result = gate.validate_destroy(
            target_name=target_name,
            confirm_topology_name=confirm_name,
            cleanup=cleanup,
            confirm_cleanup=confirm_cleanup,
        )

        assert result.passed is False
        assert result.error_message is not None

    @given(target_name=topology_name_st)
    @settings(max_examples=100)
    def test_case_sensitivity(self, target_name: str) -> None:
        """Validates: Requirements 5.1

        The confirmation must be an exact case-sensitive match. Swapping
        case should cause rejection (unless the name has no alphabetic chars).
        """
        gate = SafetyGate()

        swapped = target_name.swapcase()

        # Only test when swapcase actually changes the string
        if swapped != target_name:
            result = gate.validate_destroy(
                target_name=target_name,
                confirm_topology_name=swapped,
                cleanup=False,
                confirm_cleanup=None,
            )

            assert result.passed is False
            assert result.error_message is not None

    @given(
        target_name=topology_name_st,
        confirm_cleanup=st.one_of(st.none(), st.just(False)),
    )
    @settings(max_examples=100)
    def test_cleanup_without_confirm_cleanup_rejects(
        self, target_name: str, confirm_cleanup: bool | None
    ) -> None:
        """Validates: Requirements 5.3, 5.4

        When cleanup is True but confirm_cleanup is missing or False,
        the operation is rejected even if confirm_topology_name matches.
        """
        gate = SafetyGate()

        result = gate.validate_destroy(
            target_name=target_name,
            confirm_topology_name=target_name,
            cleanup=True,
            confirm_cleanup=confirm_cleanup,
        )

        assert result.passed is False
        assert result.error_message is not None

    @given(target_name=topology_name_st)
    @settings(max_examples=100)
    def test_cleanup_with_confirm_cleanup_true_passes(
        self, target_name: str
    ) -> None:
        """Validates: Requirements 5.3

        When cleanup is True and confirm_cleanup is True and
        confirm_topology_name matches, the operation passes.
        """
        gate = SafetyGate()

        result = gate.validate_destroy(
            target_name=target_name,
            confirm_topology_name=target_name,
            cleanup=True,
            confirm_cleanup=True,
        )

        assert result.passed is True
        assert result.error_message is None

    @given(
        target_name=topology_name_st,
        confirm_name=st.one_of(st.none(), topology_name_st),
        cleanup=st.booleans(),
        confirm_cleanup=st.one_of(st.none(), st.booleans()),
    )
    @settings(max_examples=100)
    def test_comprehensive_gate_logic(
        self,
        target_name: str,
        confirm_name: str | None,
        cleanup: bool,
        confirm_cleanup: bool | None,
    ) -> None:
        """Validates: Requirements 5.1, 5.2, 5.3, 5.4

        For any combination of inputs, the destroy operation proceeds
        only when:
        (a) confirm_topology_name exactly matches target_name, AND
        (b) if cleanup is True, confirm_cleanup is also True.
        All other combinations result in rejection.
        """
        gate = SafetyGate()

        result = gate.validate_destroy(
            target_name=target_name,
            confirm_topology_name=confirm_name,
            cleanup=cleanup,
            confirm_cleanup=confirm_cleanup,
        )

        # Determine expected outcome
        name_matches = confirm_name is not None and confirm_name == target_name
        cleanup_ok = (not cleanup) or (confirm_cleanup is True)
        should_pass = name_matches and cleanup_ok

        assert result.passed is should_pass, (
            f"Expected passed={should_pass} but got passed={result.passed}. "
            f"target={target_name!r}, confirm={confirm_name!r}, "
            f"cleanup={cleanup}, confirm_cleanup={confirm_cleanup}"
        )

        if should_pass:
            assert result.error_message is None
        else:
            assert result.error_message is not None
