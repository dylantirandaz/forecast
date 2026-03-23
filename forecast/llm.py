from __future__ import annotations

import json

from forecast.config import MODEL_COSTS

_api_keys: dict[str, str] = {}


def set_api_key(provider: str, key: str) -> None:
    _api_keys[provider] = key


def call_llm(
    prompt: str,
    system: str,
    provider: str,
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 1500,
) -> tuple[str, int, int]:
    if provider == "anthropic":
        return _call_anthropic(prompt, system, model, temperature, max_tokens)
    return _call_openai(prompt, system, model, temperature, max_tokens)


def _call_anthropic(
    prompt: str,
    system: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> tuple[str, int, int]:
    import anthropic

    kwargs = {}
    if _api_keys.get("anthropic"):
        kwargs["api_key"] = _api_keys["anthropic"]
    client = anthropic.Anthropic(**kwargs)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text, resp.usage.input_tokens, resp.usage.output_tokens


def _call_openai(
    prompt: str,
    system: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> tuple[str, int, int]:
    import openai

    kwargs = {}
    if _api_keys.get("openai"):
        kwargs["api_key"] = _api_keys["openai"]
    client = openai.OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return (
        resp.choices[0].message.content,
        resp.usage.prompt_tokens,
        resp.usage.completion_tokens,
    )


def parse_llm_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = [line for line in text.split("\n") if not line.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    costs = MODEL_COSTS.get(model, {"input": 0.003, "output": 0.015})
    return (tokens_in / 1000 * costs["input"]) + (tokens_out / 1000 * costs["output"])
