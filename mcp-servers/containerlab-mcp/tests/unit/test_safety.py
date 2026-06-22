"""Unit tests for the SafetyGate destroy confirmation validation."""

import pytest

from containerlab_mcp.safety import SafetyGate, ValidationResult


@pytest.fixture
def gate() -> SafetyGate:
    return SafetyGate()


class TestValidateDestroyBasicApproval:
    """Tests for successful destroy validation."""

    def test_exact_match_no_cleanup_passes(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name="my-lab",
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is True
        assert result.error_message is None

    def test_exact_match_cleanup_with_confirm_passes(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name="my-lab",
            cleanup=True,
            confirm_cleanup=True,
        )
        assert result.passed is True
        assert result.error_message is None

    def test_exact_match_no_cleanup_confirm_cleanup_false_passes(self, gate: SafetyGate):
        """When cleanup=False, confirm_cleanup value is irrelevant."""
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name="my-lab",
            cleanup=False,
            confirm_cleanup=False,
        )
        assert result.passed is True
        assert result.error_message is None

    def test_exact_match_no_cleanup_confirm_cleanup_none_passes(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name="my-lab",
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is True
        assert result.error_message is None


class TestValidateDestroyNameMismatch:
    """Tests for topology name confirmation failures."""

    def test_confirm_name_none_rejects(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name=None,
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is False
        assert result.error_message is not None
        assert "confirm_topology_name" in result.error_message

    def test_confirm_name_wrong_rejects(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name="wrong-name",
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is False
        assert "mismatch" in result.error_message.lower()

    def test_confirm_name_case_sensitive_uppercase_rejects(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name="My-Lab",
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is False
        assert "case-sensitive" in result.error_message.lower()

    def test_confirm_name_case_sensitive_all_caps_rejects(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="My-Lab",
            confirm_topology_name="my-lab",
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is False
        assert result.error_message is not None

    def test_confirm_name_extra_whitespace_rejects(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name=" my-lab",
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is False
        assert result.error_message is not None

    def test_confirm_name_empty_string_rejects(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name="",
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is False
        assert result.error_message is not None


class TestValidateDestroyCleanupConfirmation:
    """Tests for cleanup confirmation logic."""

    def test_cleanup_true_confirm_cleanup_none_rejects(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name="my-lab",
            cleanup=True,
            confirm_cleanup=None,
        )
        assert result.passed is False
        assert "cleanup" in result.error_message.lower()

    def test_cleanup_true_confirm_cleanup_false_rejects(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name="my-lab",
            cleanup=True,
            confirm_cleanup=False,
        )
        assert result.passed is False
        assert "cleanup" in result.error_message.lower()

    def test_cleanup_true_name_mismatch_rejects_on_name(self, gate: SafetyGate):
        """Name mismatch is checked first, even with cleanup issues."""
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name="wrong",
            cleanup=True,
            confirm_cleanup=True,
        )
        assert result.passed is False
        assert "mismatch" in result.error_message.lower()

    def test_cleanup_true_name_none_rejects_on_name(self, gate: SafetyGate):
        """None confirmation is checked first, even with cleanup issues."""
        result = gate.validate_destroy(
            target_name="my-lab",
            confirm_topology_name=None,
            cleanup=True,
            confirm_cleanup=True,
        )
        assert result.passed is False
        assert "confirm_topology_name" in result.error_message


class TestValidationResultModel:
    """Tests for the ValidationResult data model."""

    def test_passed_result_construction(self):
        result = ValidationResult(passed=True)
        assert result.passed is True
        assert result.error_message is None

    def test_failed_result_construction(self):
        result = ValidationResult(passed=False, error_message="Some error")
        assert result.passed is False
        assert result.error_message == "Some error"

    def test_result_serialization(self):
        result = ValidationResult(passed=False, error_message="test error")
        data = result.model_dump()
        assert data == {"passed": False, "error_message": "test error"}


class TestEdgeCases:
    """Edge case tests for unusual topology names."""

    def test_empty_target_name_with_empty_confirm_passes(self, gate: SafetyGate):
        """Even empty strings pass if they match exactly."""
        result = gate.validate_destroy(
            target_name="",
            confirm_topology_name="",
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is True

    def test_unicode_topology_name_exact_match(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="lab-ñoño",
            confirm_topology_name="lab-ñoño",
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is True

    def test_unicode_topology_name_mismatch(self, gate: SafetyGate):
        result = gate.validate_destroy(
            target_name="lab-ñoño",
            confirm_topology_name="lab-nono",
            cleanup=False,
            confirm_cleanup=None,
        )
        assert result.passed is False

    def test_special_characters_in_name(self, gate: SafetyGate):
        name = "lab_with-special.chars/and:colons"
        result = gate.validate_destroy(
            target_name=name,
            confirm_topology_name=name,
            cleanup=True,
            confirm_cleanup=True,
        )
        assert result.passed is True
