"""
test_pricing.py

Offline tests for the cost estimators. These need no API keys and make no
network calls, so they cost nothing to run:

    pip install -e ".[dev]"
    pytest -q

Fake usage objects (SimpleNamespace) stand in for the provider SDK responses,
so the provider SDKs do not need to be installed either. The expected dollar
values below are computed by hand from the June 2026 rate tables in pricing.py.
"""

from types import SimpleNamespace

import pytest

from llm_cost_telemetry.anthropic_cost import estimate_cost as claude_cost
from llm_cost_telemetry.openai_cost import estimate_cost as openai_cost
from llm_cost_telemetry.gemini_cost import estimate_cost as gemini_cost
from llm_cost_telemetry.pricing import get_rates


def test_anthropic_opus_sums_four_buckets():
    # input excludes cache, so all four buckets are summed
    usage = SimpleNamespace(
        input_tokens=10_000,
        output_tokens=2_000,
        cache_creation_input_tokens=5_000,
        cache_read_input_tokens=50_000,
    )
    # 10k*5 + 2k*25 + 5k*6.25 + 50k*0.50, all /1e6
    assert claude_cost("claude-opus-4-8", usage) == pytest.approx(0.15625)


def test_anthropic_sonnet_rates():
    usage = SimpleNamespace(
        input_tokens=10_000,
        output_tokens=2_000,
        cache_creation_input_tokens=5_000,
        cache_read_input_tokens=50_000,
    )
    assert claude_cost("claude-sonnet-4-6", usage) == pytest.approx(0.09375)


def test_openai_subtracts_cached_from_prompt():
    usage = SimpleNamespace(
        prompt_tokens=12_000,                 # includes the cached tokens
        completion_tokens=3_000,              # reasoning already included here
        prompt_tokens_details=SimpleNamespace(cached_tokens=4_000),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=1_000),
    )
    # uncached 8k*5 + cached 4k*0.50 + output 3k*30, all /1e6
    assert openai_cost("gpt-5.5", usage) == pytest.approx(0.132)


def test_openai_cheaper_model():
    usage = SimpleNamespace(
        prompt_tokens=12_000,
        completion_tokens=3_000,
        prompt_tokens_details=SimpleNamespace(cached_tokens=4_000),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=1_000),
    )
    # uncached 8k*2.50 + cached 4k*0.25 + output 3k*15, all /1e6
    assert openai_cost("gpt-5.4", usage) == pytest.approx(0.066)


def test_gemini_flash_bills_thinking_as_output():
    usage = SimpleNamespace(
        prompt_token_count=20_000,
        cached_content_token_count=5_000,
        candidates_token_count=2_000,
        thoughts_token_count=1_000,           # billed at output rate
    )
    # uncached 15k*1.50 + cached 5k*0.15 + output (2k+1k)*9, all /1e6
    assert gemini_cost("gemini-3.5-flash", usage) == pytest.approx(0.05025)


def test_gemini_pro_standard_tier_under_threshold():
    usage = SimpleNamespace(
        prompt_token_count=50_000,
        cached_content_token_count=0,
        candidates_token_count=1_000,
        thoughts_token_count=0,
    )
    # 50k*2 + 1k*12, all /1e6
    assert gemini_cost("gemini-3.1-pro", usage) == pytest.approx(0.112)


def test_gemini_pro_high_tier_over_threshold():
    usage = SimpleNamespace(
        prompt_token_count=250_000,           # crosses the 200K step-up
        cached_content_token_count=0,
        candidates_token_count=1_000,
        thoughts_token_count=0,
    )
    # 250k*4 + 1k*18, all /1e6
    assert gemini_cost("gemini-3.1-pro", usage) == pytest.approx(1.018)


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_rates("nope", "whatever")


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        get_rates("anthropic", "claude-not-a-real-model")
