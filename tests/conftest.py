# Pytest configuration
# These tests run without live Supabase access
# Core scientific logic is tested with synthetic data

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests requiring live Supabase"
    )
