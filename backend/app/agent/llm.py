"""Minimal provider-agnostic LLM client (Anthropic + OpenAI-compatible) over httpx."""
import json
import re
import time
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

import httpx

from ..config import get_settings


class LLM(ABC):
    name: str

    @abstractmethod
    def complete(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 3000) -> str: ...


def _post(client: httpx.Client, url: str, **kw) -> httpx.Response:
    for attempt in range(4):
        r = client.post(url, **kw)
        if r.status_code in (429, 500, 502, 503, 529) and attempt < 3:
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()
        return r
    raise RuntimeError("unreachable")


class AnthropicLLM(LLM):
    def __init__(self, model: str, api_key: str):
        self.name = f"anthropic:{model}"
        self.model = model
        self.client = httpx.Client(
            base_url="https://api.anthropic.com",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=120,
        )

    def complete(self, system, user, *, json_mode=False, max_tokens=3000):
        r = _post(
            self.client,
            "/v1/messages",
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": 0,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        return "".join(b.get("text", "") for b in r.json()["content"])


class OpenAICompatLLM(LLM):
    def __init__(self, model: str, api_key: str | None, base_url: str | None):
        self.name = f"openai:{model}"
        self.model = model
        self.client = httpx.Client(
            base_url=base_url or "https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120,
        )

    def complete(self, system, user, *, json_mode=False, max_tokens=3000):
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = _post(self.client, "/chat/completions", json=body)
        return r.json()["choices"][0]["message"]["content"]


def extract_json(text: str) -> Any:
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", s, re.S)
        if not m:
            raise ValueError("No JSON found in model output")
        return json.loads(m.group(0))


@lru_cache
def get_llm() -> LLM | None:
    s = get_settings()
    if s.llm_provider == "anthropic":
        return AnthropicLLM(s.llm_model or "claude-sonnet-5-5", s.anthropic_api_key or "")
    if s.llm_provider == "openai":
        return OpenAICompatLLM(s.llm_model or "gpt-4o-mini", s.openai_api_key, s.openai_base_url)
    return None
