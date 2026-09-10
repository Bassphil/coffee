"""
Standalone harness for the estate_attorney specialist.

Runs the specialist directly against the Anthropic API — no orchestrator.py,
no schemas.py, no tools.py, no session.py. Those don't exist yet; this
script stubs just enough of each (clearly marked STUB_*) to exercise the
estate_attorney persona, schema, and tool end to end.

Two things it checks in the same run:
  1. Draft phase — does the draft ground its facts in get_state_trust_rules,
     and does it surface the QSBS/trust-timing tension in
     cross_domain_implications / what_id_push_back_on?
  2. Rebuttal phase — fed a fabricated tax_cpa quote (only the quoted span,
     per the Design Document's isolation rule — never a full draft), does
     the specialist hold/qualify instead of capitulating?

NOTE ON API SHAPES: `thinking={"type": "adaptive"}` and
`output_config={"effort": ..., "format": {"type": "json_schema", "schema": ...}}`
were verified live against claude-sonnet-5 in this session. Two things the
API required that the Design Document doesn't spell out: `system` must be a
list of `{"type": "text", "text": ...}` blocks, not raw strings; and every
object node in a `output_config.format` schema needs
`additionalProperties: false` or the API 400s.

Usage:
    cd advisory-swarm
    python3 -m venv .venv && ./.venv/bin/pip install -r ../requirements.txt
    export ANTHROPIC_API_KEY="sk-ant-..."
    ./.venv/bin/python run_estate_attorney.py
"""

import asyncio
import json
from pathlib import Path

from anthropic import AsyncAnthropic

from app.schemas.estate_attorney import SPECIALIST_DRAFT_SCHEMA, REBUTTAL_SCHEMA
from app.tools.estate_attorney_tools import TOOL_SPEC, get_state_trust_rules

MODEL = "claude-sonnet-5"
MAX_TOOL_ITERATIONS = 6  # per the Design Document's per-specialist tool-loop cap

APP_DIR = Path(__file__).resolve().parent / "app"
PERSONA = (APP_DIR / "prompts" / "estate_attorney.txt").read_text()
PROFILE = json.loads((APP_DIR / "data" / "client_profile_sample.json").read_text())

TOOLS = {"get_state_trust_rules": get_state_trust_rules}

# Stand-in for the real system[0] (house method + memo contract + tool rules),
# which belongs in the shared orchestrator/prompts, not here.
STUB_HOUSE_METHOD = (
    "You are one of three specialists on a financial advisory panel "
    "(financial_advisor, tax_cpa, estate_attorney). Ground every factual claim "
    "in a tool call rather than memory. Respond only in the required structured "
    "format."
)

# Stand-in for the real system[1] (session block: profile + standing-memo digest).
STUB_SESSION_BLOCK = f"Client profile:\n{json.dumps(PROFILE, indent=2)}"


async def _run_with_tools(client: AsyncAnthropic, system_blocks: list[str], messages: list[dict], schema: dict) -> dict:
    system_content = [{"type": "text", "text": block} for block in system_blocks]
    for _ in range(MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_content,
            tools=[TOOL_SPEC],
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        )

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:
            text_block = next((b for b in response.content if b.type == "text"), None)
            if text_block is None:
                raise RuntimeError(
                    f"no text block in response (stop_reason={response.stop_reason}, "
                    f"block types={[b.type for b in response.content]})"
                )
            return json.loads(text_block.text)

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for call in tool_calls:
            result = TOOLS[call.name](**call.input)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(result)}
            )
        messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(f"estate_attorney did not finish within {MAX_TOOL_ITERATIONS} tool iterations")


async def run_draft(client: AsyncAnthropic) -> dict:
    messages = [
        {
            "role": "user",
            "content": (
                "Draft your estate-planning analysis for this client's scenario. "
                "Cover any trust or gifting strategy relevant to the pending sale, "
                "and flag anything the CPA or financial advisor might propose that "
                "you'd want to push back on."
            ),
        }
    ]
    system_blocks = [STUB_HOUSE_METHOD, STUB_SESSION_BLOCK, PERSONA]
    return await _run_with_tools(client, system_blocks, messages, SPECIALIST_DRAFT_SCHEMA)


async def run_rebuttal(client: AsyncAnthropic, own_draft: dict) -> dict:
    # Fabricated tax_cpa position — the specialist sees only this quoted span
    # and its own draft, never the CPA's full draft (isolation rule).
    cpa_quote = (
        "We recommend funding the trust once the letter of intent is signed and "
        "the sale price is fixed, so the gifted shares' value for gift-tax "
        "purposes is certain and defensible."
    )
    messages = [
        {
            "role": "user",
            "content": (
                "A conflict was flagged with tax_cpa.\n\n"
                f"Topic: trust funding timing vs. QSBS eligibility\n"
                f'tax_cpa\'s position (verbatim): "{cpa_quote}"\n\n'
                f"Your own draft:\n{json.dumps(own_draft, indent=2)}\n\n"
                "Question: should the trust be funded after the letter of intent is "
                "signed, as tax_cpa proposes? Respond with your position."
            ),
        }
    ]
    system_blocks = [STUB_HOUSE_METHOD, STUB_SESSION_BLOCK, PERSONA]
    return await _run_with_tools(client, system_blocks, messages, REBUTTAL_SCHEMA)


async def main() -> None:
    client = AsyncAnthropic()

    print("=== DRAFT ===")
    draft = await run_draft(client)
    print(json.dumps(draft, indent=2))

    print("\n=== REBUTTAL ===")
    rebuttal = await run_rebuttal(client, draft)
    print(json.dumps(rebuttal, indent=2))

    if rebuttal["position"] == "concede":
        print(
            "\n[!] WARNING: estate_attorney conceded outright. The Design Document "
            "flags full-draft capitulation as a failure mode this isolation setup "
            "is meant to prevent -- worth a manual read of `reasoning` above."
        )


if __name__ == "__main__":
    asyncio.run(main())
