import os
import json
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def complete_json(self, prompt: str, images: list[bytes] | None = None) -> dict:
        ...


class NullClient(LLMClient):
    """Offline pass-through used for deterministic-only runs and unit tests."""

    def __init__(self, fail: bool = False):
        self.fail = fail

    def complete_json(self, prompt, images=None):
        if self.fail:
            raise RuntimeError("llm unavailable")
        return {"_null": True}


class GeminiClient(LLMClient):
    def __init__(self, model: str | None = None):
        from google import genai
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    def complete_json(self, prompt, images=None):
        from google.genai import types
        parts: list = [prompt]
        for im in (images or []):
            parts.append(types.Part.from_bytes(data=im, mime_type="image/png"))
        resp = self.client.models.generate_content(
            model=self.model, contents=parts,
            config={"response_mime_type": "application/json"},
        )
        return json.loads(resp.text)


def make_client() -> LLMClient:
    use = os.environ.get("DUCTQUOTE_LLM", "gemini") == "gemini"
    if use and os.environ.get("GEMINI_API_KEY"):
        return GeminiClient()
    return NullClient()
