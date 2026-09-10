"""run_turn() — the supervisor. NO fastapi import here; server.py is just one caller.

Demo shortcuts taken deliberately (documented, not accidental):
- No router / direct tier — every turn runs the full 3-specialist swarm.
- No prompt caching, no session memory, no multi-turn patching — single turn only.
- No retry/backoff, no per-specialist timeout/degraded handling.
- Synthesis defaults to Sonnet 5, not the Design Document's Opus 5 (cost/speed while iterating —
  flip DEFAULT_CONFIG["synthesis_model"] to MODEL_OPUS for the real demo run).
These are exactly the things the Design Document calls "compressible" — cut for time, not
because they don't matter.
"""

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

from client import MODEL_SONNET, calculate_cost, get_async_client, output_config_for
from schemas import CONFLICT_LIST_SCHEMA, MEMO_SCHEMA, REBUTTAL_SCHEMA, SPECIALIST_DRAFT_SCHEMA
from specialists import SPECIALISTS
from tools import ALL_TOOL_IMPLS, ALL_TOOL_SCHEMAS

APP_DIR = Path(__file__).parent

HOUSE_METHOD = (
    "You are one specialist on a three-person advisory panel (financial advisor, tax CPA, "
    "estate attorney) helping a client with a real scenario. Ground every claim in a tool call — "
    "never invent a number. Stay inside your own domain; flag cross-domain concerns rather than "
    "answering them yourself."
)

DEFAULT_CONFIG = {
    "draft_model": MODEL_SONNET,
    "draft_effort": "medium",
    "extraction_model": MODEL_SONNET,
    "extraction_effort": "high",
    "rebuttal_model": MODEL_SONNET,
    "rebuttal_effort": "medium",
    "synthesis_model": MODEL_SONNET,  # Design Document default is Opus 5 — see module docstring
    "synthesis_effort": "high",
}

PHASE_MODEL_KEY = {
    "drafts": "draft_model",
    "extraction": "extraction_model",
    "rebuttal": "rebuttal_model",
    "synthesis": "synthesis_model",
}


async def _noop_sink(event: dict) -> None:
    pass


@dataclass
class TurnResult:
    memo: dict | None
    drafts: dict
    conflicts: list
    dropped_conflicts: list
    rebuttals: dict
    usage_by_phase: dict = field(default_factory=dict)
    cost_by_phase: dict = field(default_factory=dict)
    total_cost: float = 0.0


async def _call(client, model, system, messages, tools=None, output_schema=None, effort=None,
                 tool_choice=None, max_tokens=4000):
    kwargs = {}
    if tools:
        kwargs["tools"] = tools
    output_config = output_config_for(model, effort=effort, format=output_schema)
    if output_config:
        kwargs["output_config"] = output_config
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    return await client.messages.create(
        model=model, max_tokens=max_tokens, system=system, messages=messages, **kwargs
    )


def _get_text(response) -> str:
    blocks = [b for b in response.content if b.type == "text" and b.text.strip()]
    if not blocks:
        raise RuntimeError(f"no text block in response (stop_reason={response.stop_reason})")
    return blocks[-1].text


def _parse_json(response) -> dict:
    text = _get_text(response)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                "response truncated by max_tokens before the JSON closed — raise max_tokens "
                "for this call"
            ) from exc
        raise


async def _run_tool_loop(client, model, system, messages, output_schema, sink, agent_id,
                          effort=None, max_iterations=6):
    usage = []
    response = await _call(client, model, system, messages, tools=ALL_TOOL_SCHEMAS, effort=effort)
    usage.append(response.usage)
    for _ in range(max_iterations):
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = ALL_TOOL_IMPLS[block.name](**block.input)
                await sink({"type": "tool_call", "agent_id": agent_id, "tool": block.name,
                            "input_summary": block.input})
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}
                )
        messages.append({"role": "user", "content": tool_results})
        response = await _call(client, model, system, messages, tools=ALL_TOOL_SCHEMAS, effort=effort)
        usage.append(response.usage)

    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": "Provide your structured output as JSON now."})
    final = await _call(client, model, system, messages, output_schema=output_schema, effort=effort,
                         tool_choice={"type": "none"})
    usage.append(final.usage)
    return _parse_json(final), usage


def _draft_full_text(draft: dict) -> str:
    """Flatten every string value in a draft for substring quote-validation."""
    parts = [draft.get("domain_findings", ""), draft.get("recommendation", "")]
    for item in draft.get("cross_domain_implications", []):
        parts.append(item.get("implication", ""))
    for item in draft.get("what_id_push_back_on", []):
        parts.append(item.get("concern", ""))
    parts.extend(draft.get("assumptions", []))
    parts.extend(draft.get("open_questions", []))
    return "\n".join(parts)


async def _draft_specialist(client, spec, query, profile, sink, config):
    persona = (APP_DIR / spec["persona_file"]).read_text()
    system = HOUSE_METHOD + "\n\n" + persona
    await sink({"type": "agent_start", "agent_id": spec["id"], "title": spec["display_name"],
                "model": config["draft_model"]})
    messages = [{
        "role": "user",
        "content": f"Client profile:\n{json.dumps(profile)}\n\nScenario:\n{query}",
    }]
    draft, usage = await _run_tool_loop(
        client, config["draft_model"], system, messages, SPECIALIST_DRAFT_SCHEMA, sink, spec["id"],
        effort=config["draft_effort"],
    )
    await sink({"type": "draft_complete", "agent_id": spec["id"], "draft": draft})
    return spec["id"], draft, usage


def _validate_conflicts(conflicts: list, drafts_text: dict) -> tuple[list, list]:
    kept, dropped = [], []
    for c in conflicts[:3]:  # hard cap, regardless of how many the extractor proposes
        if c.get("materiality") == "framing_only":
            dropped.append({"id": c.get("id"), "reason": "framing_only, not material"})
            continue
        bad_quote = None
        for pos in c.get("positions", []):
            text = drafts_text.get(pos.get("agent"), "")
            if pos.get("quote", "") not in text:
                bad_quote = pos.get("agent")
                break
        if bad_quote:
            dropped.append({"id": c.get("id"), "reason": f"unverifiable quote from {bad_quote}"})
        else:
            kept.append(c)
    return kept, dropped


async def _extract_conflicts(client, drafts, config, sink):
    drafts_text = {aid: _draft_full_text(d) for aid, d in drafts.items()}
    prompt = (
        "Here are the full drafts from each specialist (structured JSON). Find genuine "
        "conflicts — cases where the specialists imply different next actions or different "
        "numbers, not just different emphasis. Every quote must be copied verbatim from the "
        "draft's own text fields (domain_findings, recommendation, cross_domain_implications, "
        "what_id_push_back_on, assumptions, open_questions) so it can be verified by substring "
        "match. If there are no material conflicts, return an empty conflicts list and say why "
        "in rationale — never leave rationale blank.\n\n" + json.dumps(drafts, indent=2)
    )
    response = await _call(
        client, config["extraction_model"],
        "You are the supervisor extracting cross-domain conflicts between specialist drafts.",
        [{"role": "user", "content": prompt}], output_schema=CONFLICT_LIST_SCHEMA,
        effort=config["extraction_effort"],
    )
    result = _parse_json(response)
    kept, dropped = _validate_conflicts(result.get("conflicts", []), drafts_text)
    await sink({"type": "conflicts", "found": kept, "dropped": dropped,
                "rationale": result.get("rationale", "")})
    return kept, dropped, [response.usage]


async def _rebut(client, spec, conflict, sink, config):
    persona = (APP_DIR / spec["persona_file"]).read_text()
    system = HOUSE_METHOD + "\n\n" + persona
    counterpart = next((p for p in conflict["positions"] if p["agent"] != spec["id"]), None)
    quote = counterpart["quote"] if counterpart else ""
    prompt = (
        f"Rebuttal round. Contested question: {conflict['question']}\n\n"
        f'A counterpart specialist said: "{quote}"\n\n'
        "You do not have access to their full draft — only this quoted span. Respond with your "
        "position on its merits."
    )
    rebuttal, usage = await _run_tool_loop(
        client, config["rebuttal_model"], system, [{"role": "user", "content": prompt}],
        REBUTTAL_SCHEMA, sink, spec["id"], effort=config["rebuttal_effort"],
    )
    await sink({"type": "rebuttal", "agent_id": spec["id"], "conflict_id": conflict["id"],
                "position": rebuttal["position"], "text": rebuttal["reasoning"]})
    return conflict["id"], spec["id"], rebuttal, usage


async def _synthesize(client, query, profile, drafts, conflicts, rebuttals, config, sink):
    prompt = (
        f"Scenario:\n{query}\n\nClient profile:\n{json.dumps(profile)}\n\n"
        f"Specialist drafts:\n{json.dumps(drafts, indent=2)}\n\n"
        f"Conflicts and rebuttals:\n"
        f"{json.dumps({'conflicts': conflicts, 'rebuttals': rebuttals}, indent=2)}\n\n"
        "Synthesize one integrated memo for the client. Every conflict above must get an "
        "explicit resolution in conflicts_resolved with the tradeoff stated plainly — never "
        "silently pick a side. open_questions must name which licensed professional to consult "
        "for each item."
    )
    response = await _call(
        client, config["synthesis_model"],
        "You are the supervisor synthesizing the panel's drafts and rebuttals into one memo.",
        [{"role": "user", "content": prompt}], output_schema=MEMO_SCHEMA,
        effort=config["synthesis_effort"], max_tokens=6000,
    )
    memo = _parse_json(response)
    await sink({"type": "memo", "memo": memo})
    return memo, [response.usage]


async def run_turn(query: str, profile: dict, config: dict | None = None, sink=None) -> TurnResult:
    config = {**DEFAULT_CONFIG, **(config or {})}
    sink = sink or _noop_sink
    client = get_async_client()

    await sink({"type": "turn_start", "tier": "swarm",
                "reason": "fixed panel, no router in this demo cut"})

    draft_results = await asyncio.gather(
        *[_draft_specialist(client, spec, query, profile, sink, config) for spec in SPECIALISTS]
    )
    drafts = {aid: draft for aid, draft, _ in draft_results}
    usage_by_phase = {"drafts": [u for _, _, usages in draft_results for u in usages]}

    if len(drafts) >= 2:
        conflicts, dropped, extraction_usage = await _extract_conflicts(client, drafts, config, sink)
    else:
        conflicts, dropped, extraction_usage = [], [], []
    usage_by_phase["extraction"] = extraction_usage

    rebuttals: dict = {}
    rebuttal_usage: list = []
    if conflicts:
        spec_by_id = {s["id"]: s for s in SPECIALISTS}
        tasks = [
            _rebut(client, spec_by_id[pos["agent"]], conflict, sink, config)
            for conflict in conflicts
            for pos in conflict["positions"]
            if pos["agent"] in spec_by_id
        ]
        for conflict_id, agent_id, rebuttal, usage in await asyncio.gather(*tasks):
            rebuttals.setdefault(conflict_id, {})[agent_id] = rebuttal
            rebuttal_usage.extend(usage)
    usage_by_phase["rebuttal"] = rebuttal_usage

    memo, synthesis_usage = await _synthesize(
        client, query, profile, drafts, conflicts, rebuttals, config, sink
    )
    usage_by_phase["synthesis"] = synthesis_usage

    cost_by_phase = {
        phase: sum(calculate_cost(config[PHASE_MODEL_KEY[phase]], u) for u in usages)
        for phase, usages in usage_by_phase.items()
    }
    total_cost = sum(cost_by_phase.values())
    await sink({"type": "usage", "by_phase": cost_by_phase, "total_cost": total_cost})
    await sink({"type": "done"})

    return TurnResult(
        memo=memo, drafts=drafts, conflicts=conflicts, dropped_conflicts=dropped,
        rebuttals=rebuttals, usage_by_phase=usage_by_phase, cost_by_phase=cost_by_phase,
        total_cost=total_cost,
    )
