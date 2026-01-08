"""Integration test fixtures.

These fixtures provide minimal mocking for integration tests, allowing
multiple components to interact while controlling external dependencies
(API calls, file system).

Note: Class-level fixtures (isolate_logging, project_with_python,
mock_full_workflow) remain inside their respective test classes.
Shared fixtures are inherited from the root conftest.py.
"""
