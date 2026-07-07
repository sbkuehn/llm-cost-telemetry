"""
anthropic_cost.py

Wrap an Anthropic Claude call, capture real usage, estimate cost, and emit a
structured telemetry event.

Anthropic usage fields (anthropic.types.Usage):
  input_tokens                  uncached input (EXCLUDES cache reads/writes)
  output_tokens                 generated output
  cache_creation_input_tokens   tokens written to cache (priced at cache_write)
  cache_read_input_tokens       tokens read from cache (priced at cache_read)

Because input_tokens already excludes cache activity, the four buckets are
summed. This is the opposite of OpenAI/Gemini, where cached tokens are a subset
of the reported input and must be subtracted.

Install:
  pip install "llm-cost-telemetry[anthropic]"
Auth:
  export ANTHROPIC_API_KEY=sk-ant-...
"""

from __future__ import annotations

import time
from typing import Any, Optional

from .pricing import get_rates
from .telemetry import UsageEvent, emit

try:
    import anthropic
except ImportError:  # SDK is an optional extra
    anthropic = None


# =============================================================================
# MODEL SELECTION   (change this one line to switch models)
# =============================================================================
MODEL = "claude-opus-4-8"          # current Anthropic flagship (Opus 4.8)
# Other priced options: "claude-sonnet-4-6"  (balanced, cheaper)
#                       "claude-haiku-4-5"   (fastest, cheapest)
# Rates for each live in pricing.py.
# =============================================================================


def estimate_cost(model: str, usage: Any) -> float:
    """Estimate USD cost from an Anthropic usage object. No SDK required."""
    p = get_rates("anthropic", model)
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    return round(
        (input_tokens / 1_000_000) * p["input"]
        + (output_tokens / 1_000_000) * p["output"]
        + (cache_write / 1_000_000) * p["cache_write_5m"]
        + (cache_read / 1_000_000) * p["cache_read"],
        6,
    )


def tracked_message(
    client: Any,
    messages: list,
    *,
    model: str = MODEL,
    max_tokens: int = 1024,
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
    Call client.messages.create(...) with usage tracking. Returns the raw SDK
    response so callers use it exactly as they would normally; the telemetry
    event is emitted as a side effect. Defaults to MODEL above.
    """
    if anthropic is None:
        raise RuntimeError(
            "The anthropic SDK is not installed. "
            'Install it with: pip install "llm-cost-telemetry[anthropic]"'
        )

    started = time.perf_counter()
    outcome = "success"
    response = None
    try:
        response = client.messages.create(
            model=model, max_tokens=max_tokens, messages=messages, **kwargs
        )
    except Exception:
        outcome = "error"
        raise
    finally:
        latency_ms = (time.perf_counter() - started) * 1000
        if response is not None:
            usage = response.usage
            tool_calls = sum(
                1 for block in response.content
                if getattr(block, "type", None) == "tool_use"
            )
            emit(
                UsageEvent(
                    provider="anthropic",
                    model=model,
                    input_tokens=getattr(usage, "input_tokens", 0) or 0,
                    output_tokens=getattr(usage, "output_tokens", 0) or 0,
                    cached_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                    cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
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
    # Live smoke test:  python -m llm_cost_telemetry.anthropic_cost
    print(f"Using model: {MODEL}")
    resp = tracked_message(
        anthropic.Anthropic(),
        messages=[{"role": "user", "content": "In one sentence, what is FinOps?"}],
        app="cost-demo",
        environment="dev",
        feature="explainer",
        team="platform",
    )
    print("\nModel said:", resp.content[0].text)
