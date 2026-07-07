"""
llm_cost_telemetry

Capture real token usage and estimated cost from Anthropic, OpenAI, and Google,
and emit structured, attributable telemetry events.

Core primitives (pricing + telemetry) have no third-party dependencies and are
exported here. The provider wrappers live in their own modules so their SDKs
stay optional:

    from llm_cost_telemetry.anthropic_cost import tracked_message
    from llm_cost_telemetry.openai_cost import tracked_completion
    from llm_cost_telemetry.gemini_cost import tracked_generate
"""

from .pricing import (
    PRICING_VERIFIED,
    get_rates,
    ANTHROPIC_PRICING,
    OPENAI_PRICING,
    GEMINI_PRICING,
)
from .telemetry import UsageEvent, emit, set_sink

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "PRICING_VERIFIED",
    "get_rates",
    "ANTHROPIC_PRICING",
    "OPENAI_PRICING",
    "GEMINI_PRICING",
    "UsageEvent",
    "emit",
    "set_sink",
]
