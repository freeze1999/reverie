"""LLM and tool backends.

The engine depends only on the small ``LLMBackend`` and ``ToolBackend``
protocols, so it is fully provider-agnostic. Two LLM backends ship here:

* ``MockBackend``, deterministic and network-free, for the demo and the tests.
* ``OpenAICompatBackend``, talks to any OpenAI-compatible ``/chat/completions``
  endpoint (OpenAI, DeepSeek, Together, OpenRouter, a local vLLM/Ollama, ...),
  using only the standard library.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Callable, Optional, Protocol


class LLMBackend(Protocol):
    def complete(
        self, system: str, user: str, *, max_tokens: int = 800, temperature: float = 0.9
    ) -> str:
        ...


class ToolBackend(Protocol):
    """Executes a phase-3 directive that needs to read or change the world.

    In a real deployment this is wired to your agent's full tool-enabled session
    (web search, file I/O, code execution, ...). The engine treats it as a black
    box that takes a directive string and returns whatever the session produced.
    """

    def run(self, directive: str) -> str:
        ...


class MockBackend:
    """A deterministic LLM stand-in.

    Responses are matched by substring against the *user* prompt, so a test or
    demo can script the whole feel -> realize -> execute loop with no API key.
    """

    def __init__(self, scripted: Optional[dict[str, str]] = None, default: str = "(mock) no scripted response"):
        self.scripted = scripted or {}
        self.default = default
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, *, max_tokens: int = 800, temperature: float = 0.9) -> str:
        self.calls.append((system, user))
        for needle, response in self.scripted.items():
            if needle in user:
                return response
        return self.default


class OpenAICompatBackend:
    """Calls any OpenAI-compatible chat-completions endpoint via stdlib only.

    Configure with arguments or these environment variables:
        REVERIE_LLM_BASE_URL   (default: https://api.openai.com/v1)
        REVERIE_LLM_API_KEY
        REVERIE_LLM_MODEL      (default: gpt-4o-mini)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 150.0,
        retries: int = 3,
    ):
        self.base_url = (base_url or os.environ.get("REVERIE_LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("REVERIE_LLM_API_KEY", "")
        self.model = model or os.environ.get("REVERIE_LLM_MODEL", "gpt-4o-mini")
        self.timeout = timeout
        self.retries = retries

    def complete(self, system: str, user: str, *, max_tokens: int = 800, temperature: float = 0.9) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        ).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=body,
            headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"},
        )
        last = ""
        for _ in range(self.retries):
            try:
                raw = urllib.request.urlopen(req, timeout=self.timeout).read()
                return json.loads(raw)["choices"][0]["message"]["content"].strip()
            except Exception as e:  # noqa: BLE001 - surface after retries
                last = str(e)
                time.sleep(2)
        raise RuntimeError(f"LLM call failed after {self.retries} attempts: {last}")


class NullToolBackend:
    """A tool backend that does nothing, forces every action down the text-only
    path. Useful as a safe default and in tests."""

    def run(self, directive: str) -> str:
        return "[no tool backend configured]"


class CallableToolBackend:
    """Adapts a plain ``Callable[[str], str]`` into a ToolBackend."""

    def __init__(self, fn: Callable[[str], str]):
        self._fn = fn

    def run(self, directive: str) -> str:
        return self._fn(directive)
