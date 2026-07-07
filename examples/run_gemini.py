"""
Live smoke test for the Gemini wrapper.

    pip install -e ".[gemini]"
    export GEMINI_API_KEY=...      # or GOOGLE_API_KEY
    python examples/run_gemini.py

Makes one small real API call and prints the structured telemetry event plus
the model's answer.
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai

from llm_cost_telemetry.gemini_cost import tracked_generate, MODEL


def main() -> None:
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


if __name__ == "__main__":
    main()
