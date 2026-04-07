import json
from app.profiles.renderer import render_profile_for_prompt
from app.profiles.signals import is_structured_profile

BASE_SYSTEM_PROMPT = "You are a helpful assistant. Respond thoughtfully to the user's request."

# Kept only for legacy profiles (old arbitrary JSON blobs from pre-refactor users)
LEGACY_INJECTION_TEMPLATE = """

<user_profile>
{profile}
</user_profile>

Use the above profile to tailor your response to how this person thinks, decides, and communicates. Do not mention the profile directly."""


def _is_structured_json(mneme_profile_str):
    """Return True if the profile string is a new structured (post-merge) profile."""
    try:
        return is_structured_profile(json.loads(mneme_profile_str))
    except (json.JSONDecodeError, TypeError, AttributeError):
        return False


def assemble_default():
    return BASE_SYSTEM_PROMPT


def assemble_mneme(mneme_profile):
    """Assemble the mneme system prompt. Call signature unchanged from pre-refactor.

    Structured profiles (new): inject rendered text directly, no XML wrapper.
    Legacy profiles (old): keep <user_profile> XML wrapper to preserve
    existing benchmark run assertions.
    """
    rendered = render_profile_for_prompt(mneme_profile)
    if _is_structured_json(mneme_profile):
        return BASE_SYSTEM_PROMPT + "\n\n" + rendered
    else:
        return BASE_SYSTEM_PROMPT + LEGACY_INJECTION_TEMPLATE.format(profile=rendered)
