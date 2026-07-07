"""
openai_cost.py

Wrap an OpenAI chat completion, capture real usage, estimate cost, and emit a
structured telemetry event.

OpenAI usage fields (chat.completions response.usage):
  prompt_tokens                            TOTAL input, INCLUDING cached tokens
  completion_tokens                        output, INCLUDING reasoning tokens
  prompt_tokens_details.cached_tokens      cached subset of prompt_tokens
  completion_tokens_details.reasoning_tokens   reasoning subset of completion_tokens

Because cached_tokens is a subset of prompt_tokens, uncached input is
prompt_tokens - cached_tokens. Reasoning tokens are already billed inside
completion_tokens at the output rate, so do not add them again; they are
captured separately only for visibility.

Install:
  pip install "llm-cost-telemetry[openai]"
Auth:
  export OPENAI_API_KEY=sk-...
"""

from __future__ import annotations

import time
from typing import Any, Optional

from .pricing import get_rates
from .telemetry import UsageEvent, emit

try:
    from openai import OpenAI
except ImportError:  # SDK is an optional extra
    OpenAI = None


# =============================================================================
# MODEL SELECTION   (change this one line to switch models)
# =============================================================================
MODEL = "gpt-5.5"                  # current OpenAI flagship (GPT-5.5)
# Other priced options: "gpt-5.4"       (balanced, cheaper)
#                       "gpt-5.4-nano"  (cheapest, routing/extraction)
#                       "gpt-5.2"
# Rates for each live in pricing.py.
# =============================================================================


def _cached_tokens(usage: Any) -> int:
    details = getattr(usage, "prompt_tokens_details", None)
    return getattr(details, "cached_tokens", 0) or 0 if details else 0


def _reasoning_tokens(usage: Any) -> int:
    details = getattr(usage, "completion_tokens_details", None)
    return getattr(details, "reasoning_tokens", 0) or 0 if details else 0


def estimate_cost(model: str, usage: Any) -> float:
    """Estimate USD cost from an OpenAI usage object. No SDK required."""
    p = get_rates("openai", model)
    prompt = usage.prompt_tokens or 0
    completion = usage.completion_tokens or 0  # reasoning already included
    cached = _cached_tokens(usage)
    uncached_input = max(prompt - cached, 0)
    return round(
        (uncached_input / 1_000_000) * p["input"]
        + (cached / 1_000_000) * p["cached_input"]
        + (completion / 1_000_000) * p["output"],
        6,
    )


def tracked_completion(
    client: Any,
    messages: list,
    *,
    model: str = MODEL,
    app: str = "unknown",
    environment: str = "dev",
    feature: str = "unknown",
    workflow_id: Optional[str] = None,
    team: Optional[str] = None,
    session_id: Optional[str] = None,
    user_ref: Optional[str] = None,
    **kwargs,
):
    """
    Call client.chat.completions.create(...) with usage tracking. Returns the
    raw SDK response; emits the telemetry event as a side effect. Defaults to
    MODEL above.
    """
    if OpenAI is None:
        raise RuntimeError(
            "The openai SDK is not installed. "
            'Install it with: pip install "llm-cost-telemetry[openai]"'
        )

    started = time.perf_counter()
    outcome = "success"
    response = None
    try:
        response = client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
    except Exception:
        outcome = "error"
        raise
    finally:
        latency_ms = (time.perf_counter() - started) * 1000
        if response is not None:
            usage = response.usage
            cached = _cached_tokens(usage)
            tool_calls = 0
            if response.choices:
                tc = response.choices[0].message.tool_calls
                tool_calls = len(tc) if tc else 0
            emit(
                UsageEvent(
                    provider="openai",
                    model=model,
                    input_tokens=max((usage.prompt_tokens or 0) - cached, 0),
                    output_tokens=usage.completion_tokens or 0,
                    cached_tokens=cached,
                    reasoning_tokens=_reasoning_tokens(usage),
                    estimated_cost_usd=estimate_cost(model, usage),
                    app=app,
                    environment=environment,
                    feature=feature,
                    workflow_id=workflow_id,
                    team=team,
                    session_id=session_id,
                    user_ref=user_ref,
                    latency_ms=round(latency_ms, 2),
                    tool_calls=tool_calls,
                    outcome=outcome,
                )
            )
    return response


if __name__ == "__main__":
    # Live smoke test:  python -m llm_cost_telemetry.openai_cost
    print(f"Using model: {MODEL}")
    resp = tracked_completion(
        OpenAI(),
        messages=[{"role": "user", "content": "In one sentence, what is FinOps?"}],
        app="cost-demo",
        environment="dev",
        feature="explainer",
        team="platform",
    )
    print("\nModel said:", resp.choices[0].message.content)
