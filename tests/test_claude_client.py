from unittest.mock import MagicMock, patch
from app.runner.claude_client import call_claude


def _mock_response():
    msg = MagicMock()
    msg.id = "msg_test123"
    msg.content = [MagicMock(text="This is the response.")]
    msg.stop_reason = "end_turn"
    msg.usage.input_tokens = 50
    msg.usage.output_tokens = 100
    return msg


@patch("app.runner.claude_client.anthropic.Anthropic")
def test_call_claude_returns_output_and_metadata(MockAnthropic):
    client = MockAnthropic.return_value
    client.messages.create.return_value = _mock_response()

    result = call_claude(
        api_key="sk-test",
        model="test-model",
        system_prompt="You are helpful.",
        user_prompt="Tell me something.",
        temperature=0.7,
        max_tokens=2048,
    )

    assert result["output"] == "This is the response."
    assert result["metadata"]["request_id"] == "msg_test123"
    assert result["metadata"]["stop_reason"] == "end_turn"
    assert result["metadata"]["input_tokens"] == 50
    assert result["metadata"]["output_tokens"] == 100
    assert "latency_ms" in result["metadata"]
