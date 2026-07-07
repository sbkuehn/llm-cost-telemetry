"""
Live smoke test for the OpenAI wrapper.

    pip install -e ".[openai]"
    export OPENAI_API_KEY=sk-...
    python examples/run_openai.py

Makes one small real API call and prints the structured telemetry event plus
the model's answer.
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

from llm_cost_telemetry.openai_cost import tracked_completion, MODEL


def main() -> None:
    print(f"Using model: {MODEL}")
    resp = tracked_completion(
        OpenAI(),
        messages=[{"role": "user", "content": "In one sentence, what is FinOps?"}],
        app="cost-demo",
        environment="dev",
        feature="explainer",
        team="platform",
    )
    print("\nModel said:", resp.choices[0].message.content)


if __name__ == "__main__":
    main()
