"""LLM provider abstraction.

Providers:
  * GeminiProvider - Google Gemini REST API (needs GEMINI_API_KEY; free tier available).
  * OllamaProvider - local open-source models via Ollama (free, runs on your PC).
  * None           - "demo mode": no LLM. The agent then answers with deterministic templates that
                     are CLEARLY labelled as demo/rule-based output in the UI and the database.

Every provider implements generate(system, messages) -> str and may raise LLMError.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from ..config import Settings, get_settings


class LLMError(RuntimeError):
    pass


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


class GeminiProvider:
    name = "gemini"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.s = settings
        self.model = settings.gemini_model
        self.client = httpx.Client(timeout=settings.llm_timeout_seconds, transport=transport)

    @property
    def label(self) -> str:
        return f"gemini:{self.model}"

    def generate(self, system: str, messages: list[ChatMessage]) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
                         for m in messages],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 400},
        }
        try:
            r = self.client.post(url, json=body, headers={"x-goog-api-key": self.s.gemini_api_key})
        except httpx.HTTPError as e:
            raise LLMError(f"Gemini request failed: {type(e).__name__}") from e
        if r.status_code != 200:
            raise LLMError(f"Gemini returned HTTP {r.status_code}")
        try:
            parts = r.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, ValueError) as e:
            raise LLMError("Gemini returned an unexpected response shape") from e
        if not text:
            raise LLMError("Gemini returned an empty response")
        return text

    def embed(self, text: str) -> list[float]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_embedding_model}:embedContent"
        r = self.client.post(url, json={"content": {"parts": [{"text": text[:8000]}]}},
                             headers={"x-goog-api-key": self.s.gemini_api_key})
        if r.status_code != 200:
            raise LLMError(f"Gemini embedding HTTP {r.status_code}")
        return r.json()["embedding"]["values"]


class GrokProvider:
    name = "grok"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.s = settings
        self.model = settings.grok_model
        self.client = httpx.Client(timeout=settings.llm_timeout_seconds, transport=transport)

    @property
    def label(self) -> str:
        return f"grok:{self.model}"

    def generate(self, system: str, messages: list[ChatMessage]) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] +
                        [{"role": m.role, "content": m.content} for m in messages],
            "temperature": 0.3,
            "max_tokens": 400,
        }
        try:
            r = self.client.post("https://api.x.ai/v1/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {self.s.grok_api_key}"})
        except httpx.HTTPError as e:
            raise LLMError(f"Grok request failed: {type(e).__name__}") from e
        if r.status_code != 200:
            raise LLMError(f"Grok returned HTTP {r.status_code}")
        try:
            text = r.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise LLMError("Grok returned an unexpected response shape") from e
        if not text:
            raise LLMError("Grok returned an empty response")
        return text


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.s = settings
        self.model = settings.ollama_model
        self.client = httpx.Client(timeout=settings.llm_timeout_seconds, transport=transport)

    @property
    def label(self) -> str:
        return f"ollama:{self.model}"

    def generate(self, system: str, messages: list[ChatMessage]) -> str:
        body = {"model": self.model, "stream": False, "options": {"temperature": 0.3},
                "messages": [{"role": "system", "content": system}] +
                            [{"role": m.role, "content": m.content} for m in messages]}
        try:
            r = self.client.post(f"{self.s.ollama_base_url.rstrip('/')}/api/chat", json=body)
        except httpx.HTTPError as e:
            raise LLMError(f"Ollama request failed: {type(e).__name__}") from e
        if r.status_code != 200:
            raise LLMError(f"Ollama returned HTTP {r.status_code}")
        text = (r.json().get("message") or {}).get("content", "").strip()
        if not text:
            raise LLMError("Ollama returned an empty response")
        return text


_ollama_probe: tuple[float, bool] = (0.0, False)


def _ollama_available(settings: Settings) -> bool:
    """Cheap cached probe (60 s) so 'auto' mode can use a local Ollama if it is running."""
    global _ollama_probe
    ts, ok = _ollama_probe
    if time.time() - ts < 60:
        return ok
    try:
        r = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=1.5)
        names = [m.get("name", "") for m in r.json().get("models", [])] if r.status_code == 200 else []
        ok = any(n.split(":")[0] == settings.ollama_model.split(":")[0] for n in names)
    except Exception:
        ok = False
    _ollama_probe = (time.time(), ok)
    return ok


_override: object | None = None  # used by tests to inject a fake provider


def set_provider_override(p) -> None:
    global _override
    _override = p


def get_provider(settings: Settings | None = None):
    """Return a provider instance, or None for demo mode."""
    if _override is not None:
        return None if _override == "demo" else _override
    s = settings or get_settings()
    choice = s.llm_provider.lower()
    if choice == "demo":
        return None
    if choice == "grok":
        return GrokProvider(s) if s.grok_api_key else None
    if choice == "gemini":
        return GeminiProvider(s) if s.gemini_api_key else None
    if choice == "ollama":
        return OllamaProvider(s)
    # auto
    if s.grok_api_key:
        return GrokProvider(s)
    if s.gemini_api_key:
        return GeminiProvider(s)
    if _ollama_available(s):
        return OllamaProvider(s)
    return None


def provider_status(settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    p = get_provider(s)
    return {
        "configured_provider": s.llm_provider,
        "active": p.label if p else "demo-rules",
        "mode": "llm" if p else "demo",
        "grok_key_present": bool(s.grok_api_key),
        "grok_model": s.grok_model,
        "gemini_key_present": bool(s.gemini_api_key),
        "ollama_url": s.ollama_base_url,
        "ollama_model": s.ollama_model,
        "embeddings": bool(s.gemini_api_key),
    }
