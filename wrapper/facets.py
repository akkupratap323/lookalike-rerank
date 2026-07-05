"""Stage 0: facet check — one business or several? -> query list."""
import os

import config
import llm


async def facet_queries(seed_name, seed_domain, seed_desc) -> dict:
    client = llm.deepseek_client()
    p = open(os.path.join(config.PROMPTS_DIR, "facet_check.txt")).read()
    msg = (p.replace("{{SEED_NAME}}", seed_name)
            .replace("{{SEED_DOMAIN}}", seed_domain)
            .replace("{{SEED_DESC}}", seed_desc))
    out = await llm.chat(client, config.WRAPPER_SMART_MODEL,
                         [{"role": "user", "content": msg}])
    result = llm.extract_json(out)
    if not result.get("queries"):
        result["queries"] = [seed_desc]
    return result
