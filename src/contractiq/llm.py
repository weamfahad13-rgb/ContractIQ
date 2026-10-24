"""The only module that talks to an LLM provider. Swap providers here, nowhere else."""

import time
from functools import cache

from pydantic import BaseModel

from contractiq.config import GEMINI_API_KEY, GEMINI_FALLBACK_MODELS, GEMINI_FAST_MODEL, GEMINI_MAIN_MODEL


class LLMNotConfigured(RuntimeError):
    pass


class LLMRateLimited(RuntimeError):
    pass


MAX_WAIT_S = 60  # wait out per-minute limits; skip to the next model on longer (daily) ones

# Free-tier quotas are per model, so a model that hit its daily limit is skipped until it resets.
_exhausted_until: dict[str, float] = {}


def _retry_delay(err) -> float:
    for d in (err.details or {}).get("error", {}).get("details", []):
        if d.get("@type", "").endswith("RetryInfo"):
            return float(d.get("retryDelay", "0s").rstrip("s") or 0)
    return 10.0


@cache
def _client():
    if not GEMINI_API_KEY:
        raise LLMNotConfigured("GEMINI_API_KEY is not set in .env")
    from google import genai
    from google.genai import types
    # Fail fast instead of hanging the chat when the model is overloaded.
    return genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=60_000))


def _call(model: str, prompt: str, config):
    """One model, waiting out short per-minute limits. Returns None if the model is unavailable."""
    from google.genai import errors

    for _ in range(3):
        try:
            return _client().models.generate_content(model=model, contents=prompt, config=config)
        except errors.ClientError as e:
            if e.code != 429:
                raise
            delay = _retry_delay(e)
            if delay > MAX_WAIT_S:
                _exhausted_until[model] = time.time() + delay
                return None
            time.sleep(delay + 1)
        except errors.ServerError:  # 503 "high demand": try the next model rather than wait
            return None
    return None


def generate(prompt: str, *, system: str | None = None, fast: bool = False,
             schema: type[BaseModel] | None = None):
    """Return text, or a parsed `schema` instance when one is given."""
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0,
        response_mime_type="application/json" if schema else None,
        response_schema=schema,
    )
    models = [GEMINI_FAST_MODEL if fast else GEMINI_MAIN_MODEL, *GEMINI_FALLBACK_MODELS]
    for model in dict.fromkeys(models):
        if _exhausted_until.get(model, 0) > time.time():
            continue
        response = _call(model, prompt, config)
        if response is None:
            continue
        if schema:
            return response.parsed if response.parsed is not None else schema.model_validate_json(response.text)
        return response.text or ""
    raise LLMRateLimited("The Gemini free-tier quota is used up for now. Please try again later.")
