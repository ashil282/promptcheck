import time
from dataclasses import dataclass

import httpx


class ClientError(Exception):
    pass


@dataclass
class Reply:
    text: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Client:
    """Minimal client for anything that speaks /v1/chat/completions
    (Ollama, llama.cpp server, vLLM, LM Studio, OpenAI...)."""

    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 120.0):
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/", headers=headers, timeout=timeout
        )

    def chat(self, model: str, messages: list[dict], temperature: float = 0.0) -> Reply:
        body = {"model": model, "messages": messages, "temperature": temperature}
        start = time.perf_counter()
        try:
            r = self._http.post("chat/completions", json=body)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text[:200]}") from e
        except httpx.HTTPError as e:
            raise ClientError(f"can't reach {self._http.base_url}: {e}") from e
        except ValueError as e:
            raise ClientError("response wasn't JSON") from e
        ms = int((time.perf_counter() - start) * 1000)

        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ClientError("unexpected response shape") from e
        usage = data.get("usage") or {}
        return Reply(
            text=text,
            latency_ms=ms,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
