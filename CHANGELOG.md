# Changelog

All notable changes to this project are documented here. This project follows
semantic versioning.

## [1.0.0]

Initial release.

- Cost estimation and structured telemetry for Anthropic, OpenAI, and Google Gemini.
- Central `pricing.py` rate tables (verified June 2026), including Anthropic
  cache tiers and Gemini context-tier (over 200K) pricing.
- Provider-agnostic `UsageEvent` and a swappable `emit()` sink (`set_sink`).
- Thin `tracked_*` wrappers that return the raw SDK response and emit an event
  as a side effect.
- Correct handling of the three provider-specific token accounting quirks:
  Anthropic sums four buckets; OpenAI and Gemini subtract cached tokens from
  reported input; Gemini bills thinking tokens at the output rate.
- Optional per-provider install extras so SDKs stay optional.
- Offline pytest suite that needs no API keys and makes no network calls.
- Example runners per provider plus a cross-provider comparison script.
