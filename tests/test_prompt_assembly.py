from app.runner.prompt_assembly import assemble_default, assemble_mneme

PROFILE = '{"thinking_style": "analytical", "values": ["clarity", "precision"]}'


def test_assemble_default():
    result = assemble_default()
    assert "helpful assistant" in result
    assert "<user_profile>" not in result


def test_assemble_mneme():
    result = assemble_mneme(PROFILE)
    assert "helpful assistant" in result
    assert "<user_profile>" in result
    assert "analytical" in result
    assert "Do not mention the profile" in result


def test_default_and_mneme_share_base():
    default = assemble_default()
    mneme = assemble_mneme(PROFILE)
    assert mneme.startswith(default.rstrip())
