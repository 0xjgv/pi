"""Unit test fixtures.

These fixtures provide heavy mocking for isolated unit tests.
Use the appropriate layer based on test scope (see root conftest.py).

Mock Architecture Overview:
--------------------------
Layer 1 (Lowest): DSPy LM Mock - mock_lm
Layer 2 (Middle): Claude SDK Mock - mock_claude_client
Layer 3 (Highest): Workflow Stage Mock - mock_workflow_stages

Note: Most fixtures remain in the root conftest.py since they are shared
between unit and integration tests. This file exists for organizational
clarity and any unit-specific fixtures that may be added in the future.
"""
