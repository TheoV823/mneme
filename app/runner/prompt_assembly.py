BASE_SYSTEM_PROMPT = "You are a helpful assistant. Respond thoughtfully to the user's request."

MNEME_INJECTION_TEMPLATE = """

<user_profile>
{profile}
</user_profile>

Use the above profile to tailor your response to how this person thinks, decides, and communicates. Do not mention the profile directly."""


def assemble_default():
    return BASE_SYSTEM_PROMPT


def assemble_mneme(mneme_profile):
    return BASE_SYSTEM_PROMPT + MNEME_INJECTION_TEMPLATE.format(profile=mneme_profile)
