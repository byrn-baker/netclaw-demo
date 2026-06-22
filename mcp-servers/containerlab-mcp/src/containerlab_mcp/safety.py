"""Safety gate for destructive ContainerLab operations."""

from __future__ import annotations

from pydantic import BaseModel


class ValidationResult(BaseModel):
    """Result of a safety gate validation check."""

    passed: bool
    error_message: str | None = None


class SafetyGate:
    """Validates confirmation parameters for destructive operations.

    Ensures destroy operations are only executed when the caller provides
    exact confirmation of the target topology name, and (if cleanup is
    requested) explicit cleanup confirmation.
    """

    def validate_destroy(
        self,
        target_name: str,
        confirm_topology_name: str | None,
        cleanup: bool,
        confirm_cleanup: bool | None,
    ) -> ValidationResult:
        """Validate destroy operation confirmation parameters.

        Args:
            target_name: The actual topology name being targeted for destruction.
            confirm_topology_name: The confirmation string provided by the caller.
                Must exactly match target_name (case-sensitive).
            cleanup: Whether cleanup of lab files is requested.
            confirm_cleanup: Explicit confirmation for cleanup. Required to be
                True when cleanup is True.

        Returns:
            ValidationResult with passed=True if all checks pass, or
            passed=False with a descriptive error_message on failure.
        """
        # Check 1: confirm_topology_name must not be None and must exactly match
        if confirm_topology_name is None:
            return ValidationResult(
                passed=False,
                error_message=(
                    "Destroy operation rejected: 'confirm_topology_name' parameter "
                    "is required. Please provide the exact topology name to confirm "
                    "destruction."
                ),
            )

        if confirm_topology_name != target_name:
            return ValidationResult(
                passed=False,
                error_message=(
                    f"Destroy operation rejected: confirmation mismatch. "
                    f"Expected '{target_name}' but received '{confirm_topology_name}'. "
                    f"The confirm_topology_name must be an exact case-sensitive match."
                ),
            )

        # Check 2: If cleanup is True, confirm_cleanup must also be True
        if cleanup:
            if confirm_cleanup is not True:
                return ValidationResult(
                    passed=False,
                    error_message=(
                        "Destroy operation rejected: cleanup was requested but "
                        "'confirm_cleanup' is not set to true. Both "
                        "'confirm_topology_name' match and 'confirm_cleanup: true' "
                        "are required when cleanup is enabled."
                    ),
                )

        # All checks passed
        return ValidationResult(passed=True, error_message=None)
