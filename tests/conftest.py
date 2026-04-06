"""Shared test fixtures: mock LLM that returns controllable responses."""

import sys
import json
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")


class MockLLM:
    """Controllable mock LLM. Set .next_response before each call."""

    def __init__(self):
        self.calls = []  # record all calls for assertion
        self.responses = []  # queue of responses
        self._default_response = "{}"

    def set_response(self, data: dict | str):
        """Set a single response for the next call."""
        self.responses = [data if isinstance(data, str) else json.dumps(data)]

    def set_responses(self, *data_list):
        """Set a sequence of responses for multiple calls."""
        self.responses = [
            d if isinstance(d, str) else json.dumps(d) for d in data_list
        ]

    def create(self, **kwargs):
        self.calls.append(kwargs)
        resp_text = self.responses.pop(0) if self.responses else self._default_response
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = resp_text
        mock_resp.usage = MagicMock(total_tokens=50)
        return mock_resp

    @property
    def call_count(self):
        return len(self.calls)

    def last_user_prompt(self) -> str:
        if not self.calls:
            return ""
        msgs = self.calls[-1].get("messages", [])
        return msgs[-1]["content"] if msgs else ""

    def last_system_prompt(self) -> str:
        if not self.calls:
            return ""
        msgs = self.calls[-1].get("messages", [])
        return msgs[0]["content"] if msgs and msgs[0]["role"] == "system" else ""


@pytest.fixture
def mock_llm():
    """Provides a controllable mock LLM and patches it into the client."""
    llm = MockLLM()
    mock_client = MagicMock()
    mock_client.chat.completions.create = llm.create

    with patch("backend.llm_client._get_client", return_value=mock_client):
        # Reset singleton
        import backend.llm_client
        backend.llm_client._client = None
        yield llm
