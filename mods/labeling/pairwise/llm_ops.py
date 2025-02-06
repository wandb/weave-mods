import asyncio
import weave
from litellm import acompletion
from typing import Any
import os


@weave.op
async def run_llm(prompt: str, **kwargs) -> str:
    messages = [{"role": "user", "content": prompt}]
    response = await acompletion(messages=messages, **kwargs)
    return response["choices"][0]["message"]["content"]


@weave.op
async def run_llms_pairwise(
    model_a: dict[str, Any], model_b: dict[str, Any], prompt: str, **kwargs
) -> dict[str, str]:
    response_a = run_llm(prompt=prompt, **model_a, **kwargs)
    response_b = run_llm(prompt=prompt, **model_b, **kwargs)
    results = await asyncio.gather(response_a, response_b)
    return {"response_a": results[0], "response_b": results[1]}


async def main():
    weave.init("parambharat/weave-mods")
    model_a = {
        "model": "gpt-4o-mini",
        "api_key": os.environ.get("OPENAI_API_KEY"),
    }
    model_b = {
        "model": "gpt-4o",
        "api_key": os.environ.get("OPENAI_API_KEY"),
    }
    prompt = "What is the meaning of life?"
    result = await run_llms_pairwise(model_a=model_a, model_b=model_b, prompt=prompt)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
