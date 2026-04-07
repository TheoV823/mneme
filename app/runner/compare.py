import random
from app.runner.claude_client import call_claude
from app.runner.prompt_assembly import assemble_default, assemble_mneme


def run_comparison(*, user, prompt_text, api_key, model, temperature, max_tokens):
    """Run a single prompt against both default and Mneme-personalized AI.

    Both API calls are made before returning. A/B assignment is randomized
    so the caller sees a blind comparison without knowing which mode is which.

    Returns:
        {
            "output_a": str,
            "output_b": str,
            "option_a_mode": "default" | "mneme",
            "option_b_mode": "default" | "mneme",
        }

    Raises:
        Any exception from call_claude propagates — do not swallow.
        The caller is responsible for handling API failures.
    """
    system_default = assemble_default()
    system_mneme = assemble_mneme(user["mneme_profile"])

    result_default = call_claude(
        api_key=api_key, model=model, system_prompt=system_default,
        user_prompt=prompt_text, temperature=temperature, max_tokens=max_tokens,
    )
    result_mneme = call_claude(
        api_key=api_key, model=model, system_prompt=system_mneme,
        user_prompt=prompt_text, temperature=temperature, max_tokens=max_tokens,
    )

    # Randomly assign which mode is shown as A vs B (blind comparison)
    if random.choice([True, False]):
        option_a_mode, option_b_mode = "default", "mneme"
        output_a, output_b = result_default["output"], result_mneme["output"]
    else:
        option_a_mode, option_b_mode = "mneme", "default"
        output_a, output_b = result_mneme["output"], result_default["output"]

    return {
        "output_a": output_a,
        "output_b": output_b,
        "option_a_mode": option_a_mode,
        "option_b_mode": option_b_mode,
    }
