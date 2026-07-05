"""Thin async LLM client used by every stage. OpenAI-compatible for both providers."""
import asyncio
import json
import re
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

import config


def deepseek_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)


def judge_client() -> AsyncOpenAI:
    jc = config.judge_config()
    return AsyncOpenAI(api_key=jc.api_key, base_url=jc.base_url)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20))
async def chat(client: AsyncOpenAI, model: str, messages: list, temperature: float = 0.0) -> str:
    resp = await client.chat.completions.create(
        model=model, messages=messages, temperature=temperature
    )
    return resp.choices[0].message.content or ""


def extract_json(text: str):
    """Pull the first JSON object/array out of a model reply (handles ```json fences)."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = min([i for i in (text.find("["), text.find("{")) if i >= 0])
    depth, in_str, esc = 0, False, False
    opener, closer = text[start], "]" if text[start] == "[" else "}"
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
    raise ValueError("no complete JSON found in model reply")


async def map_batches(client, model, prompt_template: str, items: list, batch_size: int,
                      render, concurrency: int = None):
    """Run prompt over items in batches, concurrently. `render(batch)->str` fills the prompt.
    Returns flat list of parsed JSON rows (each batch must return a JSON array)."""
    concurrency = concurrency or config.CONCURRENCY
    sem = asyncio.Semaphore(concurrency)
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

    async def one(batch):
        async with sem:
            msg = prompt_template.replace("{{ITEMS}}", render(batch))
            out = await chat(client, model, [{"role": "user", "content": msg}])
            rows = extract_json(out)
            if len(rows) != len(batch):
                raise ValueError(f"batch size mismatch: sent {len(batch)}, got {len(rows)}")
            return rows

    results = await asyncio.gather(*[one(b) for b in batches])
    return [row for rows in results for row in rows]
