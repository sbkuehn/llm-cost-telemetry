"""
telemetry.py

A provider-agnostic structured usage event, plus a simple emitter.

The whole point of this module: provider dashboards tell you what the service
consumed. They do not tell you which feature, workflow, or team created the
cost, or whether it produced any business value. This event carries that
attribution alongside the raw token counts and estimated cost, so you can
answer business questions instead of staring at infrastructure telemetry.

Out of the box this emits structured JSON to stdout (pick it up with whatever
log shipper you already run). The shape maps cleanly onto Azure Application
Insights customEvents: emit name="AIUsageEvent" with these fields as
customDimensions and the KQL in the README works as written. Swap emit() for
your own sink (App Insights, OpenTelemetry, Kafka, a database) without touching
callers.
"""

import json
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Callable, Optional


@dataclass
class UsageEvent:
    # provider-returned usage (normalized across providers)
    provider: str                       # "anthropic" | "openai" | "gemini"
    model: str
    input_tokens: int                   # uncached input only
    output_tokens: int                  # visible output (excludes reasoning/thinking)
    cached_tokens: int = 0              # cache reads
    cache_write_tokens: int = 0         # Anthropic cache writes (0 elsewhere)
    reasoning_tokens: int = 0           # OpenAI reasoning / Gemini thoughts
    estimated_cost_usd: float = 0.0

    # application attribution (the part dashboards cannot give you)
    app: str = "unknown"
    environment: str = "dev"            # dev | staging | prod
    feature: str = "unknown"            # e.g. "contract-diff", "support-copilot"
    workflow_id: Optional[str] = None   # ties multi-step agent runs together
    team: Optional[str] = None          # cost ownership
    session_id: Optional[str] = None
    user_ref: Optional[str] = None      # hashed/pseudonymous, never raw PII

    # operational signal
    latency_ms: Optional[float] = None
    tool_calls: int = 0
    outcome: str = "success"            # success | error | retry | refusal

    # bookkeeping
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cached_tokens
            + self.cache_write_tokens
            + self.reasoning_tokens
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_tokens"] = self.total_tokens
        return d


# The active sink. Replace via set_sink() to route events somewhere real.
_sink: Callable[[UsageEvent], None]


def _stdout_sink(event: UsageEvent) -> None:
    """Default sink: structured JSON to stdout, one line per event."""
    sys.stdout.write(json.dumps({"name": "AIUsageEvent", **event.to_dict()}) + "\n")
    sys.stdout.flush()


_sink = _stdout_sink


def set_sink(sink: Callable[[UsageEvent], None]) -> None:
    """
    Swap the emitter's destination without touching any caller.

    Example (Azure Application Insights via opencensus/OpenTelemetry, a queue,
    a database, etc.):

        from llm_cost_telemetry.telemetry import set_sink

        def to_app_insights(event):
            tracer.track_event("AIUsageEvent", event.to_dict())

        set_sink(to_app_insights)
    """
    global _sink
    _sink = sink


def emit(event: UsageEvent) -> None:
    """Emit a usage event through the active sink (stdout JSON by default)."""
    _sink(event)
