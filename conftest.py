"""Project-wide pytest fixtures."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_generate_vehicle_catalog():
    """Prevent the AI catalog generation task from running during tests."""
    with patch('ai_assistant.tasks.generate_vehicle_catalog.delay') as mock:
        yield mock
