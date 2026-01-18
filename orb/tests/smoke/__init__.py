"""Smoke tests for K os API.

Run with: pytest -m smoke

These tests verify that all major API endpoints are responding correctly.
They require the K os API to be running on port 8001.

Usage:
    # Run all smoke tests
    pytest -m smoke

    # Run smoke tests with verbose output
    pytest -m smoke -v

    # Run only health tests
    pytest -m smoke tests/smoke/test_api_endpoints.py::TestCoreHealthSystem

    # Skip smoke tests in normal test runs
    pytest -m "not smoke"
"""
