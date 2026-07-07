# Convenience targets for llm-cost-telemetry.
# Run "make help" to list them.

.PHONY: help install install-all test smoke-anthropic smoke-openai smoke-gemini smoke-all clean

help:
	@echo "install          install the package (core only, no provider SDKs)"
	@echo "install-all      install with all provider SDKs + dev tools"
	@echo "test             run the offline cost tests (no API keys, no spend)"
	@echo "smoke-anthropic  one live Anthropic call (needs ANTHROPIC_API_KEY)"
	@echo "smoke-openai     one live OpenAI call (needs OPENAI_API_KEY)"
	@echo "smoke-gemini     one live Gemini call (needs GEMINI_API_KEY)"
	@echo "smoke-all        run every provider you have a key for"
	@echo "clean            remove build/cache artifacts"

install:
	pip install -e .

install-all:
	pip install -e ".[all,dev]"

test:
	pytest -q

smoke-anthropic:
	python examples/run_anthropic.py

smoke-openai:
	python examples/run_openai.py

smoke-gemini:
	python examples/run_gemini.py

smoke-all:
	python examples/all_providers.py

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
