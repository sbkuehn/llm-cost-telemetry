"""
Run the same prompt across every provider you have configured, then print a
side-by-side comparison of tokens, latency, and estimated cost.

    pip install -e ".[all]"
    export ANTHROPIC_API_KEY=...    # set whichever you have; missing ones are skipped
    export OPENAI_API_KEY=...
    export GEMINI_API_KEY=...
    python examples/all_providers.py

Providers without a key (or without their SDK installed) are skipped with a
note, so this runs fine with just one provider configured.
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from llm_cost_telemetry.telemetry import UsageEvent, set_sink

PROMPT = "In one sentence, what is FinOps?"

# Capture events into a list instead of printing JSON, so we can render a table.
_events: list[UsageEvent] = []
set_sink(_events.append)


def run_anthropic() -> str | None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "no ANTHROPIC_API_KEY"
    try:
        import anthropic
        from llm_cost_telemetry.anthropic_cost import tracked_message
    except ImportError:
        return "anthropic SDK not installed"
    tracked_message(
        anthropic.Anthropic(),
        messages=[{"role": "user", "content": PROMPT}],
        app="cost-demo", feature="cross-provider-bench", team="platform",
    )
    return None


def run_openai() -> str | None:
    if not os.getenv("OPENAI_API_KEY"):
        return "no OPENAI_API_KEY"
    try:
        from openai import OpenAI
        from llm_cost_telemetry.openai_cost import tracked_completion
    except ImportError:
        return "openai SDK not installed"
    tracked_completion(
        OpenAI(),
        messages=[{"role": "user", "content": PROMPT}],
        app="cost-demo", feature="cross-provider-bench", team="platform",
    )
    return None


def run_gemini() -> str | None:
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        return "no GEMINI_API_KEY"
    try:
        from google import genai
        from llm_cost_telemetry.gemini_cost import tracked_generate
    except ImportError:
        return "google-genai SDK not installed"
    tracked_generate(
        genai.Client(),
        contents=PROMPT,
        app="cost-demo", feature="cross-provider-bench", team="platform",
    )
    return None


def main() -> None:
    for name, fn in (("anthropic", run_anthropic), ("openai", run_openai), ("gemini", run_gemini)):
        skip = fn()
        if skip:
            print(f"skipping {name}: {skip}")

    if not _events:
        print("\nNo providers ran. Set at least one API key and try again.")
        return

    print("\n{:<11} {:<20} {:>8} {:>8} {:>8} {:>10} {:>12}".format(
        "provider", "model", "in", "out", "cache", "latency", "cost_usd"))
    print("-" * 82)
    for e in _events:
        print("{:<11} {:<20} {:>8} {:>8} {:>8} {:>9.0f}ms {:>12.6f}".format(
            e.provider, e.model, e.input_tokens, e.output_tokens,
            e.cached_tokens, e.latency_ms or 0, e.estimated_cost_usd))

    print("\nRemember: estimated_cost_usd is for attribution and trending, "
          "not invoicing. Reconcile against provider billing.")


if __name__ == "__main__":
    main()
