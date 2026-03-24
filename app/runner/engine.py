import json
import random

from app.models.user import get_user
from app.models.prompt import get_prompts_for_user
from app.models.run import insert_run, run_exists
from app.runner.prompt_assembly import assemble_default, assemble_mneme
from app.runner.claude_client import call_claude
from app.utils.hashing import canonical_hash


def run_benchmark_for_user(db, *, user_id, batch_id, model, temperature, max_tokens,
                            protocol_version, api_key):
    user = get_user(db, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    prompts = get_prompts_for_user(db, user_id)
    profile_hash = canonical_hash(user["mneme_profile"])

    completed = 0
    skipped = 0
    failed = 0

    for prompt in prompts:
        if run_exists(db, batch_id, user_id, prompt["id"], model, protocol_version):
            skipped += 1
            continue

        prompt_text = prompt["text"]
        sys_default = assemble_default()
        sys_mneme = assemble_mneme(user["mneme_profile"])

        # Randomize execution order
        default_first = random.choice([True, False])
        execution_order = "default_first" if default_first else "mneme_first"

        try:
            if default_first:
                result_default = call_claude(api_key=api_key, model=model,
                    system_prompt=sys_default, user_prompt=prompt_text,
                    temperature=temperature, max_tokens=max_tokens)
                result_mneme = call_claude(api_key=api_key, model=model,
                    system_prompt=sys_mneme, user_prompt=prompt_text,
                    temperature=temperature, max_tokens=max_tokens)
            else:
                result_mneme = call_claude(api_key=api_key, model=model,
                    system_prompt=sys_mneme, user_prompt=prompt_text,
                    temperature=temperature, max_tokens=max_tokens)
                result_default = call_claude(api_key=api_key, model=model,
                    system_prompt=sys_default, user_prompt=prompt_text,
                    temperature=temperature, max_tokens=max_tokens)

            insert_run(
                db,
                user_id=user_id,
                prompt_id=prompt["id"],
                prompt_text=prompt_text,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                output_default=result_default["output"],
                output_mneme=result_mneme["output"],
                system_prompt_default=sys_default,
                system_prompt_mneme=sys_mneme,
                profile_hash=profile_hash,
                batch_id=batch_id,
                protocol_version=protocol_version,
                api_metadata_default=json.dumps(result_default["metadata"]),
                api_metadata_mneme=json.dumps(result_mneme["metadata"]),
                execution_order=execution_order,
            )
            completed += 1
        except Exception as e:
            failed += 1
            print(f"  ERROR on prompt {prompt['id']}: {e}")

    return {"completed": completed, "skipped": skipped, "failed": failed}
