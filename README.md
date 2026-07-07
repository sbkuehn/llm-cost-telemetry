# LLM Cost Telemetry

Capture **real** token usage and estimated cost from Anthropic, OpenAI, and
Google, and emit a structured telemetry event you can attribute to a feature,
workflow, and team.

Provider dashboards tell you what the service consumed. They do not tell you
which business workflow created the cost, which feature is responsible, who owns
it, or whether it produced any value. This is the small, dependency-light layer
that closes that gap.

Companion code for the post **Your LLM Has a Spending Problem: How Prompts,
Context Windows, and Agent Loops Quietly Torch Your Budget** on
[shankuehn.io](https://shankuehn.io).

Author: Shannon Eldridge-Kuehn ([shankuehn.io](https://shankuehn.io))

## Why this exists

A generic token estimator is fine for explaining the concept. For anything real
you want provider-returned usage, because each provider reports it differently
and each one has a place where a naive estimate goes wrong. This library gets
all three right:

- **Anthropic** reports `input_tokens` *excluding* cache reads and writes, so
  you sum four buckets rather than subtracting.
- **OpenAI** reports cached tokens as a *subset* of `prompt_tokens`, so you
  subtract before pricing the rest.
- **Gemini** does the same with `cached_content_token_count`, and bills
  `thoughts_token_count` (thinking) at the output rate, not the input rate.

Get any of those wrong and your cost-per-interaction number is fiction. The
token counts come straight from the provider; only the dollar figure is a local
reconstruction from a rate card, which is why the field is named
`estimated_cost_usd` and not `cost_usd`.

## Repository layout

- `src/llm_cost_telemetry/pricing.py` : single source of truth for per-MTok
  rates across all three providers, including Anthropic cache tiers and Gemini
  context-tier (over 200K) pricing. Update this one file when prices move.
- `src/llm_cost_telemetry/telemetry.py` : provider-agnostic `UsageEvent`
  dataclass plus `emit()` and `set_sink()`. Defaults to structured JSON on
  stdout; swap the sink for App Insights, OpenTelemetry, a queue, or a database.
- `src/llm_cost_telemetry/anthropic_cost.py` : `tracked_message()` wraps
  `messages.create`, captures usage, emits an event.
- `src/llm_cost_telemetry/openai_cost.py` : `tracked_completion()` wraps
  `chat.completions.create`.
- `src/llm_cost_telemetry/gemini_cost.py` : `tracked_generate()` wraps
  `models.generate_content` (current `google-genai` SDK).
- `examples/` : runnable smoke tests per provider, plus `all_providers.py`
  which runs whichever providers you have keys for and prints a comparison.
- `tests/` : offline pytest suite for the cost math. No API keys, no spend.

The core package (`pricing.py`, `telemetry.py`) has no third-party dependencies.
You only install the SDK for the providers you actually call.

## Requirements

- Python 3.9 or newer.
- A developer API key for each provider you want to run (not a chat
  subscription). The account may need a small amount of credit for calls to go
  through.

## Installation

```bash
git clone https://github.com/shankuehn/llm-cost-telemetry.git
cd llm-cost-telemetry
python -m venv .venv
source .venv/bin/activate           # Windows PowerShell: .venv\Scripts\Activate.ps1
```

Install the package plus only the providers you need. The extras keep the
provider SDKs optional:

```bash
pip install -e ".[anthropic]"       # just Claude
pip install -e ".[openai]"          # just OpenAI
pip install -e ".[gemini]"          # just Gemini
pip install -e ".[all]"             # all three
pip install -e ".[all,dev]"         # all three + pytest + python-dotenv
```

If you prefer `make`:

```bash
make install-all                    # installs [all,dev]
make help                           # lists every target
```

## Configuration

Set the key for whichever provider you are running.

macOS / Linux:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=...
```

Windows PowerShell:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:OPENAI_API_KEY = "sk-..."
$env:GEMINI_API_KEY = "..."
```

Or copy `.env.example` to `.env` and fill it in. The example scripts load `.env`
automatically when `python-dotenv` is installed (it comes with the `dev` extra).

Where to get keys:

- Anthropic: https://console.anthropic.com (Settings, then API Keys)
- OpenAI: https://platform.openai.com (API keys)
- Google Gemini: https://aistudio.google.com (Get API key)

## Quickstart: run a live smoke test

Each example makes one small real API call (fractions of a cent) and prints
three things: the model it used, the structured telemetry event, and the model's
answer. Run them from the repo root after installing.

```bash
python examples/run_anthropic.py
python examples/run_openai.py
python examples/run_gemini.py
```

Expected output looks like this:

```
Using model: claude-opus-4-8
{"name": "AIUsageEvent", "provider": "anthropic", "model": "claude-opus-4-8", "input_tokens": 14, "output_tokens": 38, "cached_tokens": 0, "cache_write_tokens": 0, "reasoning_tokens": 0, "estimated_cost_usd": 0.00102, "app": "cost-demo", "feature": "explainer", "team": "platform", ...}

Model said: FinOps is the practice of bringing financial accountability to variable cloud and AI spend...
```

That JSON line is the whole point. It is what you ship to your log store.

To run every provider you have a key for and see a side-by-side comparison of
tokens, latency, and cost:

```bash
python examples/all_providers.py     # or: make smoke-all
```

Providers without a key (or without their SDK installed) are skipped with a note,
so this runs fine with just one provider configured.

## Run the offline tests (no keys, no spend)

The cost math is fully covered by tests that use fake usage objects, so they need
no API keys, make no network calls, and do not even require the provider SDKs.

```bash
pip install -e ".[dev]"
pytest -q                            # or: make test
```

This is also how the pricing was verified before release. Every expected dollar
value is computed by hand in a comment next to the assertion.

## Using it in your own code

Each wrapper returns the **raw SDK response** (so you use it exactly as you
normally would) and emits the telemetry event as a side effect. Attribution
fields are keyword-only, so they read clearly at the call site.

```python
import anthropic
from llm_cost_telemetry.anthropic_cost import tracked_message

client = anthropic.Anthropic()
resp = tracked_message(
    client,
    messages=[{"role": "user", "content": "What changed in this contract draft?"}],
    # model defaults to the flagship; override per call if you want another
    app="contracts-app",
    environment="prod",
    feature="contract-diff",
    workflow_id="run-8f2a",          # ties multi-step agent runs together
    team="legal-eng",
)
print(resp.content[0].text)
```

OpenAI and Gemini follow the same shape:

```python
from openai import OpenAI
from llm_cost_telemetry.openai_cost import tracked_completion

resp = tracked_completion(OpenAI(),
    messages=[{"role": "user", "content": "..."}],
    app="contracts-app", feature="contract-diff", team="legal-eng")
```

```python
from google import genai
from llm_cost_telemetry.gemini_cost import tracked_generate

resp = tracked_generate(genai.Client(),
    contents="...", app="contracts-app", feature="contract-diff", team="legal-eng")
```

If you only want the number and not the event, call the estimators directly on
any usage object. These need no SDK installed, which is exactly how the tests
exercise them:

```python
from llm_cost_telemetry.anthropic_cost import estimate_cost
cost = estimate_cost("claude-opus-4-8", resp.usage)
```

## Switching models

Each provider module has a highlighted `MODEL` constant near the top, defaulted
to that provider's current flagship. Change that one line to switch the default
for everything, or pass `model=` per call to override.

- `anthropic_cost.py` defaults to `claude-opus-4-8`
- `openai_cost.py` defaults to `gpt-5.5`
- `gemini_cost.py` defaults to `gemini-3.1-pro`

Every model in the default list (and several cheaper alternatives) has rates in
`pricing.py`. If you pass a model that is not in the table, you get a clear
`ValueError` listing the known models rather than a silently wrong number.

## What an event looks like

```json
{
  "name": "AIUsageEvent",
  "provider": "anthropic",
  "model": "claude-opus-4-8",
  "input_tokens": 10000,
  "output_tokens": 2000,
  "cached_tokens": 50000,
  "cache_write_tokens": 5000,
  "reasoning_tokens": 0,
  "estimated_cost_usd": 0.15625,
  "app": "contracts-app",
  "environment": "prod",
  "feature": "contract-diff",
  "workflow_id": "run-8f2a",
  "team": "legal-eng",
  "latency_ms": 842.5,
  "tool_calls": 2,
  "outcome": "success",
  "total_tokens": 67000
}
```

## Routing events to a real sink

By default `emit()` writes one JSON line per event to stdout. To send events
somewhere real, swap the sink once at startup and every caller follows, with no
other code changes:

```python
from llm_cost_telemetry.telemetry import set_sink

def to_app_insights(event):
    # your Application Insights / OpenTelemetry / queue / DB client here
    tracer.track_event("AIUsageEvent", event.to_dict())

set_sink(to_app_insights)
```

The `UsageEvent.to_dict()` method includes the derived `total_tokens` field and
is ready to serialize.

## Azure Log Analytics: KQL

The event shape maps onto Application Insights `customEvents`. Emit with
`name="AIUsageEvent"` and these fields as `customDimensions`, and this query
works as written:

```kql
customEvents
| where name == "AIUsageEvent"
| extend Provider = tostring(customDimensions.provider)
| extend Feature = tostring(customDimensions.feature)
| extend Model = tostring(customDimensions.model)
| extend TotalTokens = todouble(customDimensions.total_tokens)
| extend EstimatedCost = todouble(customDimensions.estimated_cost_usd)
| summarize
    Requests = count(),
    TotalTokens = sum(TotalTokens),
    EstimatedCost = sum(EstimatedCost)
    by Provider, Feature, Model, bin(timestamp, 1d)
| order by EstimatedCost desc
```

Cost per workflow is one more `summarize ... by workflow_id` away, which is the
unit-economics conversation finance actually wants to have.

## Maintaining the pricing tables

Rates in `pricing.py` were verified June 2026 and the date lives in
`PRICING_VERIFIED`. Provider pricing changes often, so treat that file as living
config:

- Anthropic: https://www.anthropic.com/pricing
- OpenAI: https://openai.com/api/pricing/
- Google: https://ai.google.dev/gemini-api/docs/pricing

When you refresh a rate, bump `PRICING_VERIFIED`, add a line to `CHANGELOG.md`,
and rerun `pytest` (update the expected values if a rate you test on changed).

## A word on accuracy

`estimated_cost_usd` is an estimate for attribution and trending, not an
invoice. The token counts are exact, straight from the provider. The dollar
figure can drift from your real bill if your rate card is stale, or if you have
committed-use discounts, enterprise pricing, taxes, or free-tier credits the
rate card does not know about. Reconcile against provider billing for anything
financial. None of the tools in this space save money on their own; they make
spend visible, and the savings come from acting on what you see.

## Related tools

If you outgrow a single emitter and want a full platform, these are worth a look:

- Langfuse (tracing, prompt analytics, cost attribution): https://langfuse.com
- Helicone (request visibility, caching, spend tracking): https://www.helicone.ai
  Note: Helicone has moved into maintenance mode following its acquisition by
  Mintlify, so check whether it still fits before building on it.
- OpenLIT (OpenTelemetry-native AI observability): https://openlit.io
- LiteLLM (proxy-based routing, provider abstraction, budget controls):
  https://www.litellm.ai
- OpenAI Cookbook (practical implementation examples): https://cookbook.openai.com
- FinOps Foundation (AI economics as part of broader FinOps): https://www.finops.org

Note that LiteLLM and Helicone both want to be the proxy on the hot path, so
running both is redundant. A common production pattern is LiteLLM for routing and
budgets plus Langfuse for tracing and evals. And the same accuracy caveat above
applies to all of them: they derive cost from a price table that can lag.

## Troubleshooting

- `ModuleNotFoundError: llm_cost_telemetry`: install the package first with
  `pip install -e .` (from the repo root), or activate the virtualenv where you
  installed it.
- `RuntimeError: The <provider> SDK is not installed`: install that provider's
  extra, for example `pip install -e ".[openai]"`.
- Authentication errors on a smoke test: confirm the matching key is exported in
  the same shell, and that the account has credit.
- A `ValueError` about an unknown model: the model is not in `pricing.py`. Add it
  with current rates, or switch `MODEL` to one that is listed.

## License

MIT. See [LICENSE.md](LICENSE.md).
