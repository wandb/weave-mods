import asyncio
import weave
from litellm import acompletion
from typing import Any
import litellm
from litellm.caching.caching import Cache

litellm.cache = Cache(disk_cache_dir="/tmp/litellm_cache")


@weave.op
async def run_llm(prompt: str, **kwargs) -> str:
    messages = [{"role": "user", "content": prompt}]
    response = await acompletion(messages=messages, **kwargs, caching=True)
    return response["choices"][0]["message"]["content"]


@weave.op
async def run_llms_pairwise(
    model_a: dict[str, Any], model_b: dict[str, Any], prompt: str, **kwargs
) -> dict[str, str]:
    response_a = run_llm(prompt=prompt, **model_a, **kwargs)
    response_b = run_llm(prompt=prompt, **model_b, **kwargs)
    results = await asyncio.gather(response_a, response_b)
    return {"response_a": results[0], "response_b": results[1]}
