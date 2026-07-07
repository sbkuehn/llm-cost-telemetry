"""
pricing.py

Single source of truth for per-token pricing across Anthropic, OpenAI, and Google.

All prices are USD per 1,000,000 tokens (per MTok).
Verified June 2026. Prices change often. Check the provider pages before you
bill anything to anyone:

  Anthropic: https://www.anthropic.com/pricing
  OpenAI:    https://openai.com/api/pricing/
  Google:    https://ai.google.dev/gemini-api/docs/pricing

Cost levers worth knowing:
  * Cache reads are roughly 0.1x input across all three providers.
  * Anthropic separates cache *write* (5-minute vs 1-hour) from cache *read*.
  * OpenAI and Gemini report cached tokens as a SUBSET of input tokens, so you
    subtract cached from input before pricing the rest.
  * Reasoning / thinking tokens are billed at the OUTPUT rate (OpenAI rolls them
    into completion_tokens; Gemini exposes them separately as thoughts_token_count).
  * Some Gemini models use context-tier pricing: input/output rates step up once
    the prompt crosses 200K tokens. See GEMINI_PRICING context_threshold below.
"""

from typing import Optional

# Update this when you refresh the tables below.
PRICING_VERIFIED = "2026-06"


# Anthropic (Claude)
# input_tokens already EXCLUDES cache reads and cache writes, so the four
# buckets are summed (not subtracted). cache_write_5m is the 5-minute TTL rate
# (1.25x input); cache_write_1h is 2x input if you use longer caching.
ANTHROPIC_PRICING = {
    "claude-opus-4-8": {
        "input": 5.00,
        "output": 25.00,
        "cache_write_5m": 6.25,   # 1.25x input
        "cache_write_1h": 10.00,  # 2x input
        "cache_read": 0.50,       # 0.1x input
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
        "cache_read": 0.30,
    },
    "claude-haiku-4-5": {
        "input": 1.00,
        "output": 5.00,
        "cache_write_5m": 1.25,
        "cache_write_1h": 2.00,
        "cache_read": 0.10,
    },
}


# OpenAI (ChatGPT / GPT)
# prompt_tokens INCLUDES cached tokens. cached_input is the rate for the cached
# subset (0.1x input). Reasoning tokens are already inside completion_tokens.
OPENAI_PRICING = {
    "gpt-5.5": {
        "input": 5.00,
        "output": 30.00,
        "cached_input": 0.50,
    },
    "gpt-5.4": {
        "input": 2.50,
        "output": 15.00,
        "cached_input": 0.25,
    },
    "gpt-5.4-nano": {
        "input": 0.20,
        "output": 1.25,
        "cached_input": 0.02,
    },
    "gpt-5.2": {
        "input": 1.75,
        "output": 14.00,
        "cached_input": 0.175,
    },
}


# Google (Gemini)
# prompt_token_count INCLUDES cached tokens. cached_input is 0.1x input.
# thoughts_token_count is billed at the output rate.
# Pro models use context-tier pricing: rates step up past context_threshold
# tokens of input. Models without "context_threshold" are flat-rate.
GEMINI_PRICING = {
    "gemini-3.1-pro": {
        "input": 2.00,
        "output": 12.00,
        "cached_input": 0.20,
        "context_threshold": 200_000,
        "input_high": 4.00,
        "output_high": 18.00,
        "cached_input_high": 0.40,
    },
    "gemini-3-pro": {
        "input": 2.00,
        "output": 12.00,
        "cached_input": 0.20,
        "context_threshold": 200_000,
        "input_high": 4.00,
        "output_high": 18.00,
        "cached_input_high": 0.40,
    },
    "gemini-3.5-flash": {
        "input": 1.50,
        "output": 9.00,
        "cached_input": 0.15,
    },
    "gemini-3-flash": {
        "input": 0.50,
        "output": 3.00,
        "cached_input": 0.05,
    },
    "gemini-3.1-flash-lite": {
        "input": 0.25,
        "output": 1.50,
        "cached_input": 0.025,
    },
}


_TABLES = {
    "anthropic": ANTHROPIC_PRICING,
    "openai": OPENAI_PRICING,
    "gemini": GEMINI_PRICING,
}


def get_rates(provider: str, model: str, prompt_tokens: Optional[int] = None) -> dict:
    """
    Return the effective per-MTok rates for a model.

    For Gemini Pro models with context-tier pricing, pass prompt_tokens so the
    correct tier is selected. If prompt_tokens crosses context_threshold, the
    high-context rates are returned under the standard keys.
    """
    table = _TABLES.get(provider)
    if table is None:
        raise ValueError(
            f"Unknown provider: {provider!r}. "
            f"Expected one of: {', '.join(_TABLES)}"
        )
    rates = table.get(model)
    if rates is None:
        raise ValueError(
            f"Unknown {provider} model: {model!r}. "
            f"Known models: {', '.join(table)}"
        )

    threshold = rates.get("context_threshold")
    if threshold is not None and prompt_tokens is not None and prompt_tokens > threshold:
        return {
            "input": rates["input_high"],
            "output": rates["output_high"],
            "cached_input": rates["cached_input_high"],
        }
    return dict(rates)
