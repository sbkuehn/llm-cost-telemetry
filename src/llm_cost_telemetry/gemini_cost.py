"""
gemini_cost.py

Wrap a Google Gemini call, capture real usage, estimate cost, and emit a
structured telemetry event.

Uses the current google-genai SDK (the older google-generativeai package is
being retired). Usage comes back on response.usage_metadata:
  prompt_token_count             TOTAL input, INCLUDING cached tokens
  cached_content_token_count     cached subset of prompt_token_count
  candidates_token_count         visible output
  thoughts_token_count           thinking tokens, billed at the OUTPUT rate
  total_token_count              provider's own total

Two gotchas this handles:
  1. cached_content_token_count is a subset of prompt_token_count, so uncached
     input is prompt - cached.
  2. thoughts_token_count is billed as output, so it is added to the output
     bucket, not the input one.

Gemini Pro models use context-tier pricing (rates step up past 200K input
tokens). get_rates() in pricing.py selects the right tier when passed the
prompt token count.

Install:
  pip install "llm-cost-telemetry[gemini]"
Auth:
  export GEMINI_API_KEY=...      # or GOOGLE_API_KEY
"""

from __future__ import annotations

import time
from typing import Any, Optional

from .pricing import get_rates
from .telemetry import UsageEvent, emit

try:
    from google import genai
except ImportError:  # SDK is an optional extra
    genai = None


# =============================================================================
# MODEL SELECTION   (change this one line to switch models)
# =============================================================================
MODEL = "gemini-3.1-pro"           # current Gemini flagship (3.1 Pro, tiered >200K)
# Other priced options: "gemini-3.5-flash"       (balanced, cheaper)
#                       "gemini-3-flash"          (cheaper still)
#                       "gemini-3.1-flash-lite"   (cheapest, routing/extraction)
# Rates for each live in pricing.py.
# =============================================================================


def estimate_cost(model: str, usage: Any) -> float:
    """Estimate USD cost from a Gemini usage_metadata object. No SDK required."""
    prompt = getattr(usage, "prompt_token_count", 0) or 0
    cached = getattr(usage, "cached_content_token_count", 0) or 0
    candidates = getattr(usage, "candidates_token_count", 0) or 0
    thoughts = getattr(usage, "thoughts_token_count", 0) or 0

    # Tier is chosen on total input (prompt_token_count) for Pro models.
    p = get_rates("gemini", model, prompt_tokens=prompt)
    uncached_input = max(prompt - cached, 0)
    billable_output = candidates + thoughts  # thinking billed as output
    return round(
        (uncached_input / 1_000_000) * p["input"]
        + (cached / 1_000_000) * p["cached_input"]
        + (billable_output / 1_000_000) * p["output"],
        6,
    )


def tracked_generate(
    client: Any,
    contents: Any,
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
    Call client.models.generate_content(...) with usage tracking. Returns the
    raw SDK response; emits the telemetry event as a side effect. Defaults to
    MODEL above.
    """
    if genai is None:
        raise RuntimeError(
            "The google-genai SDK is not installed. "
            'Install it with: pip install "llm-cost-telemetry[gemini]"'
        )

    started = time.perf_counter()
    outcome = "success"
    response = None
    try:
        response = client.models.generate_content(
            model=model, contents=contents, **kwargs
        )
    except Exception:
        outcome = "error"
        raise
    finally:
        latency_ms = (time.perf_counter() - started) * 1000
        if response is not None:
            usage = response.usage_metadata
            prompt = getattr(usage, "prompt_token_count", 0) or 0
            cached = getattr(usage, "cached_content_token_count", 0) or 0
            emit(
                UsageEvent(
                    provider="gemini",
                    model=model,
                    input_tokens=max(prompt - cached, 0),
                    output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                    cached_tokens=cached,
                    reasoning_tokens=getattr(usage, "thoughts_token_count", 0) or 0,
                    estimated_cost_usd=estimate_cost(model, usage),
                    app=app,
                    environment=environment,
                    feature=feature,
                    workflow_id=workflow_id,
                    team=team,
                    session_id=session_id,
                    user_ref=user_ref,
                    latency_ms=round(latency_ms, 2),
                    outcome=outcome,
                )
            )
    return response


if __name__ == "__main__":
    # Live smoke test:  python -m llm_cost_telemetry.gemini_cost
    print(f"Using model: {MODEL}")
    resp = tracked_generate(
        genai.Client(),
        contents="In one sentence, what is FinOps?",
        app="cost-demo",
        environment="dev",
        feature="explainer",
        team="platform",
    )
    print("\nModel said:", resp.text)
