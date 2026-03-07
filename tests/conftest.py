"""Pytest configuration for weather-file-builder tests."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="run slow tests"
    )
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests (requires CDS API)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line(
        "markers", "integration: marks tests requiring external services"
    )


def pytest_collection_modifyitems(config, items):
    skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
    skip_integration = pytest.mark.skip(reason="need --run-integration option to run")

    for item in items:
        if "slow" in item.keywords and not config.getoption("--run-slow"):
            item.add_marker(skip_slow)
        if "integration" in item.keywords and not config.getoption("--run-integration"):
            item.add_marker(skip_integration)
