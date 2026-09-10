"""Runs the financial_advisor persona against the live API — draft mode and rebuttal mode.

Shared core used by scripts/smoke_financial_advisor.py and scripts/dev_ui.py so both talk to
the model the same way. Not the real orchestrator — no session/caching/SSE — just enough to
exercise the persona, tools, and schemas end to end before the shared skeleton exists.
"""

import json
import os
from pathlib import Path

from anthropic import Anthropic

from env_loader import load_env_file
from tools_financial_advisor import TOOL_IMPLS, TOOL_SCHEMAS

load_env_file(Path(__file__).parent.parent / ".env")

MODEL = "claude-sonnet-5"
PERSONA = (Path(__file__).parent / "prompts" / "financial_advisor.txt").read_text()

DRAFT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "domain_findings": {"type": "string"},
            "recommendation": {"type": "string"},
            "cross_domain_implications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string"},
                        "implication": {"type": "string"},
                    },
                    "required": ["domain", "implication"],
                    "additionalProperties": False,
                },
            },
            "what_id_push_back_on": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"domain": {"type": "string"}, "concern": {"type": "string"}},
                    "required": ["domain", "concern"],
                    "additionalProperties": False,
                },
            },
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "open_questions": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "domain_findings",
            "recommendation",
            "cross_domain_implications",
            "what_id_push_back_on",
            "assumptions",
            "open_questions",
        ],
        "additionalProperties": False,
    },
}

REBUTTAL_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "position": {"type": "string", "enum": ["hold", "concede", "qualify"]},
            "reasoning": {"type": "string"},
            "condition_under_which_other_is_right": {"type": "string"},
            "revised_recommendation": {"type": "string"},
        },
        "required": [
            "position",
            "reasoning",
            "condition_under_which_other_is_right",
            "revised_recommendation",
        ],
        "additionalProperties": False,
    },
}

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Put it in advisory-swarm/.env or export it."
            )
        _client = Anthropic()
    return _client


def _get_structured_result(response) -> dict:
    text_blocks = [b for b in response.content if b.type == "text" and b.text.strip()]
    if not text_blocks:
        raise RuntimeError(f"no text block in response (stop_reason={response.stop_reason})")
    try:
        return json.loads(text_blocks[-1].text)
    except json.JSONDecodeError as exc:
        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                "response was truncated by max_tokens before the JSON closed — raise max_tokens"
            ) from exc
        raise


def _run_tool_loop(system, messages, output_schema, tool_log=None, max_iterations=6):
    client = _get_client()
    response = client.messages.create(
        model=MODEL, max_tokens=2500, system=system, messages=messages, tools=TOOL_SCHEMAS
    )
    for _ in range(max_iterations):
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = TOOL_IMPLS[block.name](**block.input)
                if tool_log is not None:
                    tool_log.append({"tool": block.name, "input": block.input, "output": result})
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}
                )
        messages.append({"role": "user", "content": tool_results})
        response = client.messages.create(
            model=MODEL, max_tokens=2500, system=system, messages=messages, tools=TOOL_SCHEMAS
        )

    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": "Provide your structured output as JSON now."})
    final = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        system=system,
        messages=messages,
        output_config={"format": output_schema},
        tool_choice={"type": "none"},
    )
    return _get_structured_result(final)


def run_draft(scenario: str, tool_log=None) -> dict:
    return _run_tool_loop(
        system=PERSONA,
        messages=[{"role": "user", "content": scenario}],
        output_schema=DRAFT_SCHEMA,
        tool_log=tool_log,
    )


def run_rebuttal(question: str, counterpart_quote: str, tool_log=None) -> dict:
    prompt = (
        f"Rebuttal round. The contested question: {question}\n\n"
        f'The other specialist said: "{counterpart_quote}"\n\n'
        "You do not have access to their full draft. Respond with your position."
    )
    return _run_tool_loop(
        system=PERSONA,
        messages=[{"role": "user", "content": prompt}],
        output_schema=REBUTTAL_SCHEMA,
        tool_log=tool_log,
    )
