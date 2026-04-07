from unittest.mock import patch
from app.runner.compare import run_comparison


_FAKE_USER = {"id": "u1", "mneme_profile": '{"decision_style": null}'}
_FAKE_DEFAULT = {"output": "default_output", "metadata": {}}
_FAKE_MNEME = {"output": "mneme_output", "metadata": {}}

_CALL_KWARGS = dict(user=_FAKE_USER, prompt_text="test prompt",
                    api_key="k", model="m", temperature=0.7, max_tokens=100)


def test_run_comparison_a_is_default_when_coin_true():
    with patch("app.runner.compare.call_claude", side_effect=[_FAKE_DEFAULT, _FAKE_MNEME]):
        with patch("app.runner.compare.random.choice", return_value=True):
            result = run_comparison(**_CALL_KWARGS)

    assert result["option_a_mode"] == "default"
    assert result["option_b_mode"] == "mneme"
    assert result["output_a"] == "default_output"
    assert result["output_b"] == "mneme_output"


def test_run_comparison_a_is_mneme_when_coin_false():
    with patch("app.runner.compare.call_claude", side_effect=[_FAKE_DEFAULT, _FAKE_MNEME]):
        with patch("app.runner.compare.random.choice", return_value=False):
            result = run_comparison(**_CALL_KWARGS)

    assert result["option_a_mode"] == "mneme"
    assert result["option_b_mode"] == "default"
    assert result["output_a"] == "mneme_output"
    assert result["output_b"] == "default_output"


def test_run_comparison_calls_claude_twice():
    with patch("app.runner.compare.call_claude", side_effect=[_FAKE_DEFAULT, _FAKE_MNEME]) as mock_call:
        with patch("app.runner.compare.random.choice", return_value=True):
            run_comparison(**_CALL_KWARGS)

    assert mock_call.call_count == 2


def test_run_comparison_result_keys():
    with patch("app.runner.compare.call_claude", side_effect=[_FAKE_DEFAULT, _FAKE_MNEME]):
        with patch("app.runner.compare.random.choice", return_value=True):
            result = run_comparison(**_CALL_KWARGS)

    assert set(result.keys()) == {"output_a", "output_b", "option_a_mode", "option_b_mode"}
