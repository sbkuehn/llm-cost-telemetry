# Contributing

Contributions are welcome. This is a small, focused project, so the bar is
simple: keep it defensible to a practitioner reading the code.

## Getting set up

```bash
git clone https://github.com/shankuehn/llm-cost-telemetry.git
cd llm-cost-telemetry
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
pytest -q
```

## Guidelines

- The core package (`pricing.py`, `telemetry.py`) must stay dependency-free.
  Provider SDKs belong behind the optional extras and guarded imports.
- Any change to cost math needs a matching test in `tests/` with the expected
  dollar value computed by hand in a comment.
- When you refresh a rate, update `PRICING_VERIFIED` in `pricing.py` and note it
  in `CHANGELOG.md`.
- Prices are estimates for attribution and trending, never invoices. Do not add
  logic that implies the numbers are authoritative billing figures.

## Reporting a pricing change

Open an issue with the provider, model, the old and new rate, the effective
date, and a link to the provider's pricing page. Rate changes are the most
common and most valuable contribution here.
