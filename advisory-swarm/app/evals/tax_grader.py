"""
Tax-advisor-perspective grader for a tax_cpa draft (or the tax portions of the
synthesized memo).

Two rubric dimensions:

  completion        -- did the tax analysis actually get done? recognition events
                       named, tax quantified with real numbers, the levers that
                       matter here covered (timing / basis / state), planted
                       conflicts engaged, actions sequenced, assumptions stated.

  subject_integrity -- did it stay a grounded tax analysis? every finding cites a
                       tool result, nothing contradicts the fixtures, it stays in
                       the tax lane (legal-validity and portfolio-design calls
                       routed to open_questions, not answered), and it holds a tax
                       position instead of capitulating to the other seats.

Design Document.md, Layer 3: "Judge structure and grounding, not correctness."
Every judge check below is structural / grounding and returns PASS or FAIL. The
"is this good tax advice?" question is deliberately not asked.

Draft shape: the estate track's SPECIALIST_DRAFT_SCHEMA
(app/schemas/estate_attorney.py), which Phase 0 should adopt into the shared
schemas.py -- headline, domain_findings[{finding, basis}], recommendation,
cross_domain_implications[{domain, implication}], what_id_push_back_on[{domain,
concern}], assumptions[str], open_questions[str]. `basis` names the tool result a
finding rests on.

Phase 0 seam
------------
`grade_tax_response(draft, scenario_id, judge=...)` takes a `judge` callable:

    judge(system: str, user: str, schema: dict) -> dict   # wraps client.py FAST_MODEL

If `judge` is None the judge checks are reported as "skipped" and only the
deterministic checks score. `tax_response_grader(result, check, context)` is the
GRADER_REGISTRY-compatible wrapper.

Run `python3 app/evals/tax_grader.py` for the discrimination smoke test.
"""

from __future__ import annotations

import json
import re

try:  # runnable both as a module and as a script
    from .tax_cases import PLANTED_CONFLICTS
except ImportError:  # pragma: no cover
    from tax_cases import PLANTED_CONFLICTS

KNOWN_TOOLS = {"get_tax_brackets", "get_state_trust_rules", "get_portfolio",
               "get_client_profile", "get_prior_finding"}

PASS_THRESHOLDS = {"completion": 0.70, "subject_integrity": 0.85}


# --- the test case ---------------------------------------------------------- --

TAX_RESPONSE_GRADER_CASE = {
    "id": "tax_cpa_draft_quality/tax_liquidity_event",
    "layer": 3,
    "scenario_id": "tax_liquidity_event",
    "grader": "grade_tax_response",
    "dimensions": ["completion", "subject_integrity"],
    "pass_thresholds": PASS_THRESHOLDS,
    "num_runs": 3,  # nondeterministic swarm -> report a rate, not a pass
    "sample_pass": "SAMPLE_DRAFTS['strong']",
    "sample_fail": "SAMPLE_DRAFTS['weak']",
}


# --- rubric ---------------------------------------------------------------- --

RUBRIC = [
    {"id": "completion.conflicts_engaged", "dimension": "completion", "kind": "deterministic",
     "desc": "what_id_push_back_on domains cover the agents this scenario plants a conflict with"},
    {"id": "completion.actions_sequenced", "dimension": "completion", "kind": "deterministic",
     "desc": "the draft gives an ordered / time-anchored set of actions, not a single lump"},
    {"id": "completion.assumptions_stated", "dimension": "completion", "kind": "deterministic",
     "desc": "assumptions[] is non-empty"},
    {"id": "completion.recognition_events", "dimension": "completion", "kind": "judge",
     "q": "Does the draft identify the points in this scenario where the client would "
          "recognize income or gain (at minimum: the sale of the founder stock, and any "
          "transfer of shares to a trust or to the children as its own event)?"},
    {"id": "completion.quantified", "dimension": "completion", "kind": "judge",
     "q": "Is the tax cost of the central decision expressed as specific dollar or "
          "percentage figures rather than vague words like 'significant' or 'a lot'?"},
    {"id": "completion.levers_covered", "dimension": "completion", "kind": "judge",
     "q": "Does the draft address all three levers that matter here -- the timing of the "
          "sale against the QSBS holding period, basis (carryover vs. step-up), and state "
          "tax / residency?"},

    {"id": "subject_integrity.findings_grounded", "dimension": "subject_integrity", "kind": "deterministic",
     "desc": "every domain_findings[] entry names a real tool in its `basis`"},
    {"id": "subject_integrity.out_of_lane_routed", "dimension": "subject_integrity", "kind": "deterministic",
     "desc": "open_questions[] is non-empty and at least one routes the client to a licensed professional"},
    {"id": "subject_integrity.no_antifacts", "dimension": "subject_integrity", "kind": "deterministic",
     "desc": "the draft does not repeat a known-false statement for this scenario"},
    {"id": "subject_integrity.no_floating_figures", "dimension": "subject_integrity", "kind": "judge",
     "q": "Is every numeric claim in the draft tied to a tool result (via a domain_finding's "
          "`basis` or an inline citation), with no free-floating figures?"},
    {"id": "subject_integrity.stays_out_of_law", "dimension": "subject_integrity", "kind": "judge",
     "q": "Does the draft avoid asserting legal conclusions about the validity, enforceability, "
          "or drafting of a trust or other instrument, routing those to open_questions instead?"},
    {"id": "subject_integrity.stays_out_of_portfolio", "dimension": "subject_integrity", "kind": "judge",
     "q": "Does the draft avoid prescribing a specific portfolio allocation or investment "
          "product, routing that to open_questions instead?"},
    {"id": "subject_integrity.holds_position", "dimension": "subject_integrity", "kind": "judge",
     "q": "Where the tax analysis supports a different course than the estate attorney or "
          "financial advisor, does the draft hold that tax position rather than simply agreeing?"},
]

# statements that contradict the fixtures for tax_liquidity_event
KNOWN_ANTIFACTS = {
    "tax_liquidity_event": [
        (r"california.{0,40}(conform|exempt).{0,20}(qsbs|1202)",
         "California does not conform to section 1202 (state_rules California.tax_detail)."),
        (r"(100\s*%|fully)\s*exclu.{0,60}202[56]",
         "The pre-2025 lot needs a 5-year hold (2027-03-10) for the 100% exclusion; a 2026 sale gets 0%."),
        (r"airtight|bulletproof|guaranteed to (protect|work)",
         "Overstated certainty about a legal instrument -- out of lane and not supported."),
        (r"qsbs.{0,20}(40\s*%|forty percent)",
         "Section 1202 tiers are 50/75/100%, not 40% (tax_brackets_2026 qsbs_section_1202)."),
    ],
}


# --- draft access -------------------------------------------------------- --

def _render(draft) -> str:
    return draft if isinstance(draft, str) else json.dumps(draft, indent=2, sort_keys=True)


def _get(draft, key, default=None):
    return draft.get(key, default) if isinstance(draft, dict) else default


# --- deterministic checks ---------------------------------------------- --

def _expected_pushback_domains(scenario_id: str) -> set[str]:
    out = set()
    for c in PLANTED_CONFLICTS:
        if c.get("scenario_id") != scenario_id:
            continue
        for p in c["positions"]:
            if p["agent"] != "tax_cpa":
                out.add(p["agent"])
    return out


def deterministic_checks(draft, scenario_id: str) -> dict[str, dict]:
    text = _render(draft).lower()
    out: dict[str, dict] = {}

    pushbacks = _get(draft, "what_id_push_back_on", []) or []
    got = {p.get("domain") for p in pushbacks if isinstance(p, dict)}
    want = _expected_pushback_domains(scenario_id)
    out["completion.conflicts_engaged"] = {
        "verdict": "PASS" if want and want.issubset(got) else "FAIL",
        "evidence": f"pushback domains {sorted(d for d in got if d)} vs expected {sorted(want)}",
    }

    actions = _get(draft, "recommended_actions") or _get(draft, "action_plan")
    seq_lang = bool(re.search(r"\b(first,|then |next,|before close|after close|step 1|"
                              r"sequence:|by (year-end|20\d\d)|q[1-4]\s*20\d\d)\b", text))
    out["completion.actions_sequenced"] = {
        "verdict": "PASS" if (actions and len(actions) >= 2) or seq_lang else "FAIL",
        "evidence": "explicit action list" if actions else ("sequencing language present"
                    if seq_lang else "no ordered actions found"),
    }

    assumptions = _get(draft, "assumptions", []) or []
    out["completion.assumptions_stated"] = {
        "verdict": "PASS" if len(assumptions) >= 1 else "FAIL",
        "evidence": f"{len(assumptions)} assumption(s)",
    }

    findings = _get(draft, "domain_findings", []) or []
    ungrounded = [f for f in findings if not any(t in str(f.get("basis", "")) for t in KNOWN_TOOLS)]
    out["subject_integrity.findings_grounded"] = {
        "verdict": "PASS" if findings and not ungrounded else "FAIL",
        "evidence": "every finding cites a tool in `basis`" if findings and not ungrounded
                    else (f"{len(ungrounded)} finding(s) with no tool in `basis`"
                          if findings else "no domain_findings"),
    }

    oqs = _get(draft, "open_questions", []) or []
    referred = [q for q in oqs if re.search(r"attorney|counsel|\bcpa\b|\bcfp\b|advisor|licensed",
                                            str(q), re.I)]
    out["subject_integrity.out_of_lane_routed"] = {
        "verdict": "PASS" if referred else "FAIL",
        "evidence": f"{len(referred)} of {len(oqs)} open question(s) route to a professional",
    }

    hits = [msg for pat, msg in KNOWN_ANTIFACTS.get(scenario_id, []) if re.search(pat, text)]
    out["subject_integrity.no_antifacts"] = {
        "verdict": "PASS" if not hits else "FAIL",
        "evidence": "clean" if not hits else "; ".join(hits),
    }
    return out


# --- judge checks ----------------------------------------------------- --

_JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
                    "evidence": {"type": "string"},
                },
                "required": ["id", "verdict", "evidence"],
            },
        }
    },
    "required": ["checks"],
}

_JUDGE_SYSTEM = (
    "You grade a Tax CPA's draft on structure and grounding only -- never on whether the "
    "tax advice is correct. For each check answer PASS or FAIL and quote or point to the "
    "part of the draft that decides it. A check with no supporting evidence in the draft "
    "is a FAIL."
)


def judge_checks(draft, judge) -> dict[str, dict]:
    items = [c for c in RUBRIC if c["kind"] == "judge"]
    if judge is None:
        return {c["id"]: {"verdict": "SKIPPED", "evidence": "no judge provided"} for c in items}
    user = "DRAFT:\n" + _render(draft) + "\n\nCHECKS:\n" + "\n".join(
        f"- {c['id']}: {c['q']}" for c in items)
    resp = judge(_JUDGE_SYSTEM, user, _JUDGE_SCHEMA)
    by_id = {r["id"]: {"verdict": r["verdict"], "evidence": r.get("evidence", "")}
             for r in resp.get("checks", [])}
    for c in items:  # a check the judge dropped is a FAIL, not a gap
        by_id.setdefault(c["id"], {"verdict": "FAIL", "evidence": "judge returned no verdict"})
    return by_id


# --- scoring -------------------------------------------------------- --

def grade_tax_response(draft, scenario_id: str = "tax_liquidity_event", judge=None) -> dict:
    results = {**deterministic_checks(draft, scenario_id), **judge_checks(draft, judge)}
    by_dim: dict[str, list[int]] = {"completion": [], "subject_integrity": []}
    for c in RUBRIC:
        v = results[c["id"]]["verdict"]
        if v == "SKIPPED":
            continue
        by_dim[c["dimension"]].append(1 if v == "PASS" else 0)

    dim_scores = {d: (sum(xs) / len(xs) if xs else None) for d, xs in by_dim.items()}
    scored = [s for s in dim_scores.values() if s is not None]
    overall = sum(scored) / len(scored) if scored else None
    gate = all(dim_scores.get(d) is not None and dim_scores[d] >= t
               for d, t in PASS_THRESHOLDS.items())
    fails = [cid for cid, r in results.items() if r["verdict"] == "FAIL"]

    return {
        "score": overall,
        "by_dimension": dim_scores,
        "gate_pass": gate,
        "checks": results,
        "reason": ("all checks pass" if not fails
                   else f"{len(fails)} check(s) failed: " + ", ".join(fails)),
    }


def tax_response_grader(result, check, context) -> dict:
    """GRADER_REGISTRY-compatible: fn(result, check, context) -> {score, reason}."""
    draft = result.get("tax_cpa_draft") if isinstance(result, dict) else result
    scenario_id = (context or {}).get("scenario_id", "tax_liquidity_event")
    judge = (context or {}).get("judge")
    graded = grade_tax_response(draft, scenario_id, judge=judge)
    return {"score": graded["score"] or 0.0, "reason": graded["reason"],
            "detail": {"by_dimension": graded["by_dimension"], "gate_pass": graded["gate_pass"]}}


# --- sample drafts (fixtures + discrimination smoke test) ------------ --
# shape: estate track's SPECIALIST_DRAFT_SCHEMA

SAMPLE_DRAFTS = {
    "strong": {
        "headline": "Hold the founder stock to the 2027 QSBS mark; fund any trust with cash, not shares.",
        "domain_findings": [
            {"finding": "The founder lot was acquired 2022-03, so pre-2025 section 1202 rules apply: "
             "a five-year hold (reached 2027-03-10) excludes 100% of gain up to the greater of $10M "
             "or 10x basis. A 2026 sale at the four-year mark gets 0% exclusion.",
             "basis": "get_tax_brackets(2026, ...).qsbs_section_1202 + get_portfolio acquisition date"},
            {"finding": "Gain is ~$21.4M ($22M less $600K basis). At 23.8% federal that is ~$5.1M; "
             "California adds 13.3% (no preferential rate, no section 1202 conformity), ~$2.85M, for "
             "~$7.95M total on a 2026 sale.",
             "basis": "get_tax_brackets top_combined_ltcg_rate_federal + get_state_trust_rules('California')"},
            {"finding": "Transferring the shares to an irrevocable trust forfeits the death-time basis "
             "step-up on ~$21.4M of gain and can disturb the QSBS holding period.",
             "basis": "get_state_trust_rules('federal').lifetime_gift_basis_rule + step_transaction_risk_note"},
            {"finding": "The estate is ~$40M against a $30M married exclusion, so ~$10M is exposed at "
             "40% (~$4M) -- smaller than the income-tax cost of gifting the low-basis shares now.",
             "basis": "get_tax_brackets(2026, 'married_filing_jointly').estate_and_gift + get_portfolio"},
        ],
        "recommendation": "Do not fund the trust with the shares or sell the founder stock before "
        "close. Sequence: first, before close, test whether a genuine domicile change to a "
        "no-income-tax state is realistic given California's residency-audit posture; then at close, "
        "if the buyer requires a sale, negotiate rollover / installment terms that push gain past the "
        "2027-03-10 QSBS mark; next, hold the founder shares to 2027-03-10 so the 100% exclusion "
        "applies; fund the trust with cash or post-sale proceeds, not the shares; and diversify the "
        "existing $8M public book over 2026-2028 with loss harvesting.",
        "cross_domain_implications": [
            {"domain": "estate_attorney", "implication": "The 2027-03-10 QSBS date should drive the "
             "sale timeline; trust funding of the shares should wait until after the exclusion is "
             "secured and should use proceeds, not shares."},
            {"domain": "financial_advisor", "implication": "Reduce concentration by hedging the "
             "founder position until it can be sold QSBS-free, not by an early taxable sale."},
        ],
        "what_id_push_back_on": [
            {"domain": "estate_attorney",
             "concern": "Moving founder shares into the irrevocable trust before close forfeits the "
             "death-time step-up on ~$21.4M of gain and can reset the QSBS holding period; the ~$4M "
             "estate-tax saving is smaller than the income-tax cost. Fund the trust with cash or "
             "post-sale proceeds instead."},
            {"domain": "financial_advisor",
             "concern": "Selling most of the position to diversify at close costs ~$7.95M in tax that "
             "largely disappears if the shares are held to the 2027 QSBS mark. Hedge the concentration "
             "in the interim and stage the sale of the already-diversified public book instead."},
        ],
        "assumptions": [
            "The founder lot meets the section 1202 qualified-small-business tests -- not verified here.",
            "The deal is structured as a sale of stock (not assets) with timing flexibility.",
            "No prior gifting has used the married exclusion.",
        ],
        "open_questions": [
            "Consult a licensed tax attorney: whether the Meridian shares qualify as QSBS and whether "
            "the deal structure preserves that treatment.",
            "Consult a licensed estate attorney: trust type, situs, and drafting to reach the "
            "estate-tax goal without a completed gift of the low-basis shares.",
            "Consult a licensed financial advisor: the hedging instrument and the target allocation "
            "for the public book.",
        ],
    },
    "weak": {
        "headline": "Set up the trust now and diversify.",
        "domain_findings": [
            {"finding": "Selling the company will trigger significant capital gains tax.", "basis": "general knowledge"},
            {"finding": "QSBS might give a break of around 40% if it applies.", "basis": ""},
        ],
        "recommendation": "Setting up the irrevocable trust before the sale is a smart move and you "
        "should transfer most of the shares into it now -- the trust is airtight and removes them "
        "from your estate. Then sell and put 60% in equities and 40% in municipal bonds.",
        "cross_domain_implications": [],
        "what_id_push_back_on": [],
        "assumptions": [],
        "open_questions": [],
    },
}


def _keyword_judge(system: str, user: str, schema: dict) -> dict:
    """Stand-in judge for the smoke test -- keyword heuristics, no model call.
    Looks only at the DRAFT half of the prompt, never the check questions."""
    t = user.split("CHECKS:")[0].lower()
    verdicts = {
        "completion.recognition_events": "sale" in t and ("transfer" in t or "gift" in t or "fund the trust" in t),
        "completion.quantified": bool(re.search(r"\$\s?\d|\d\s?%", t)) and "significant capital gains tax" not in t,
        "completion.levers_covered": "qsbs" in t and ("step-up" in t or "basis" in t) and ("california" in t or "state" in t),
        "subject_integrity.no_floating_figures": '"basis": ""' not in user and "around 40%" not in t,
        "subject_integrity.stays_out_of_law": "airtight" not in t and "bulletproof" not in t,
        "subject_integrity.stays_out_of_portfolio": not re.search(r"\d{2}\s?%\s?(in|to)\s?(equit|bond|stock)", t),
        "subject_integrity.holds_position": '"what_id_push_back_on": []' not in user and "what_id_push_back_on" in user,
    }
    return {"checks": [{"id": k, "verdict": "PASS" if v else "FAIL", "evidence": "keyword heuristic"}
                       for k, v in verdicts.items()]}


if __name__ == "__main__":
    for name in ("strong", "weak"):
        g = grade_tax_response(SAMPLE_DRAFTS[name], "tax_liquidity_event", judge=_keyword_judge)
        print(f"\n=== {name} ===")
        print(f"  score            {g['score']:.2f}")
        print(f"  by_dimension     {{ {', '.join(f'{k}: {v:.2f}' for k, v in g['by_dimension'].items())} }}")
        print(f"  gate_pass        {g['gate_pass']}")
        print(f"  {g['reason']}")

    strong = grade_tax_response(SAMPLE_DRAFTS["strong"], "tax_liquidity_event", judge=_keyword_judge)
    weak = grade_tax_response(SAMPLE_DRAFTS["weak"], "tax_liquidity_event", judge=_keyword_judge)
    assert strong["score"] > weak["score"], "grader failed to rank strong over weak"
    assert strong["gate_pass"] and not weak["gate_pass"], "gate failed to discriminate"
    assert strong["by_dimension"]["subject_integrity"] >= PASS_THRESHOLDS["subject_integrity"]
    print("\nOK - grader discriminates strong vs weak and gates on subject_integrity")
