import time
import anthropic


def call_claude(*, api_key, model, system_prompt, user_prompt, temperature, max_tokens):
    client = anthropic.Anthropic(api_key=api_key)

    start = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    latency_ms = round((time.monotonic() - start) * 1000)

    output = response.content[0].text if response.content else ""

    metadata = {
        "request_id": response.id,
        "stop_reason": response.stop_reason,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "latency_ms": latency_ms,
    }

    return {"output": output, "metadata": metadata}
