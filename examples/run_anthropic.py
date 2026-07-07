"""
Live smoke test for the Anthropic wrapper.

    pip install -e ".[anthropic]"
    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/run_anthropic.py

Makes one small real API call (fractions of a cent) and prints the structured
telemetry event plus the model's answer.
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import anthropic

from llm_cost_telemetry.anthropic_cost import tracked_message, MODEL


def main() -> None:
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


if __name__ == "__main__":
    main()
