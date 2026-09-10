"""Async Anthropic client factory + pricing. Demo shortcut: Anthropic-first-party only, no
Bedrock branch wired up (the sync PROVIDER/_model pattern from Basecamp-Exercises supports it —
add back if needed, skipped here to save time).
"""

import os
from pathlib import Path

from anthropic import AsyncAnthropic

from env_loader import load_env_file

load_env_file(Path(__file__).parent.parent / ".env")

MODEL_HAIKU = "claude-haiku-4-5"
MODEL_SONNET = "claude-sonnet-5"
MODEL_OPUS = "claude-opus-5"

# First-party rates, $/MTok. (Design Document flags day2/02's $3/$15 Sonnet row as the stale
# Sonnet 4.6 rate — these are current for Sonnet 5 / Opus 5 / Haiku 4.5.)
PRICING = {
    MODEL_HAIKU: {"input": 1.00, "output": 5.00},
    MODEL_SONNET: {"input": 2.00, "output": 10.00},
    MODEL_OPUS: {"input": 5.00, "output": 25.00},
}
CACHE_WRITE_MULT = 1.25
CACHE_READ_MULT = 0.10

_client: AsyncAnthropic | None = None


def get_async_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set (advisory-swarm/.env or env var).")
        _client = AsyncAnthropic()
    return _client


def calculate_cost(model: str, usage) -> float:
    p = PRICING[model]
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (
        usage.input_tokens * p["input"]
        + cache_write * p["input"] * CACHE_WRITE_MULT
        + cache_read * p["input"] * CACHE_READ_MULT
        + usage.output_tokens * p["output"]
    ) / 1e6


def output_config_for(model: str, effort: str | None = None, format: dict | None = None) -> dict:
    """Haiku 4.5 400s on output_config.effort; Sonnet/Opus want it. Branch here so callers
    don't have to know which model tier they're on."""
    cfg = {}
    if format is not None:
        cfg["format"] = format
    if effort is not None and model != MODEL_HAIKU:
        cfg["effort"] = effort
    return cfg


def thinking_for(model: str, budget_tokens: int = 2048) -> dict:
    if model == MODEL_HAIKU:
        return {"type": "enabled", "budget_tokens": budget_tokens}
    return {"type": "adaptive"}
