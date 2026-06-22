"""Property-based test fixtures for containerlab-mcp."""

import pytest
from hypothesis import settings

# Register a profile for CI with more examples
settings.register_profile("ci", max_examples=200)
settings.register_profile("default", max_examples=100)
settings.load_profile("default")
