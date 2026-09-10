"""
Tax-track eval fixtures for advisory-swarm.

Consumed by the Phase 0/1 aggregator (app/evals/tasks.py) and the Layer 1/2/3
graders. Pure data + a smoke-print; imports nothing from the app.

Shapes follow Design Document.md:

- ROUTER_LABELS  -> Layer 1. {"turn", "gold_tier", "why"}. The doc weights a
  false `direct` far heavier than a false `swarm`; the `high_liability` flag
  marks the turns where a miss is worst.

- PLANTED_CONFLICTS -> Layer 2 ground truth. The seeded scenario
  (`tax_liquidity_event`) is built so these are structurally guaranteed. Recall
  is scored by topic match against this list; precision by the extractor's
  quote-validation drop rate + a materiality judge. `expected_position` is a
  paraphrase of what each agent's draft should assert -- not a verbatim quote,
  since the drafts don't exist yet.

- GOLD_MEMO_POINTS -> Layer 3. Per conflict, what the memo judge should see:
  grounding (numbers trace to a tool) and direction, not a single right answer.
"""

SCENARIO_ID = "tax_liquidity_event"          # tax-track canned scenario
SCENARIO_ID_PRE_LOI = "business_sale_pre_loi"  # estate-track scenario, folded into scenarios.json


ROUTER_LABELS = [
    # direct: enumerated allowlist only (greeting / definition / restate /
    # answerable-from-standing-memo)
    {"turn": "What is a Roth conversion?", "gold_tier": "direct",
     "why": "definition of a term"},
    {"turn": "Remind me what the QSBS five-year holding rule is.", "gold_tier": "direct",
     "why": "definition; no client-specific analysis"},
    {"turn": "Can you restate the action plan as a dated checklist?", "gold_tier": "direct",
     "why": "reformat request against the standing memo"},
    {"turn": "What's the 2026 annual gift tax exclusion amount?", "gold_tier": "direct",
     "why": "single lookup, no cross-domain reasoning"},

    # swarm: everything else defaults up; these are the high-liability misses
    {"turn": "I'm selling my company for about $22M next quarter. Should I set up a "
             "trust before it closes?", "gold_tier": "swarm", "high_liability": True,
     "why": "sequencing + estate + tax; changes action"},
    {"turn": "Should I establish residency in Nevada before I sell my company?",
     "gold_tier": "swarm", "high_liability": True,
     "why": "state tax vs. residency-audit risk vs. timeline; changes number"},
    {"turn": "My advisor says diversify out of the founder stock now. Is that right?",
     "gold_tier": "swarm", "high_liability": True,
     "why": "realized-gain tax vs. concentration risk; the C2 tension"},
    {"turn": "Should I gift the appreciated shares to my kids this year to use the "
             "exclusion?", "gold_tier": "swarm", "high_liability": True,
     "why": "carryover basis vs. step-up vs. transfer-tax saving; the C3 tension"},
    {"turn": "$2M of my RSUs vest next month and I want to fund 529s and a trust for "
             "the kids -- what's the tax-smart sequence?", "gold_tier": "swarm",
     "why": "income timing + gifting + trust; multi-domain"},
    {"turn": "What about California -- how does the state treat all of this?",
     "gold_tier": "swarm",
     "why": "follow-up that needs the full analysis re-run against state rules, "
            "not a Haiku answer off the standing memo"},
    {"turn": "A buyer is interested in my business but we haven't signed an LOI. "
             "Should I move stock into a trust now or wait until the price is set?",
     "gold_tier": "swarm", "high_liability": True,
     "why": "step-transaction timing vs. gift-tax valuation certainty; the C4 tension"},
]


PLANTED_CONFLICTS = [
    {
        "id": "c1",
        "scenario_id": SCENARIO_ID,
        "topic": "funding the irrevocable trust before the sale closes",
        "type": "sequencing",
        "materiality": "changes_action",
        "positions": [
            {"agent": "estate_attorney",
             "expected_position": "Move a large block of Meridian founder shares into "
             "the irrevocable trust before close to freeze ~$22M of value (and its "
             "future growth) outside the taxable estate, which is over the $30M "
             "married exclusion."},
            {"agent": "tax_cpa",
             "expected_position": "Funding the trust with the appreciated shares "
             "forfeits the death-time basis step-up, and the transfer interacts with "
             "the pre-2025 QSBS holding period (5-year mark 2027-03-10) and the "
             "per-issuer cap. If the shares are simply held to the 5-year mark the "
             "federal gain may be fully excluded anyway -- the trust move must be "
             "measured against that baseline, and sequenced around the close date."},
        ],
        "question": "Should founder shares go into the irrevocable trust before the "
                    "acquisition closes, or should the sale timing (QSBS 5-year mark) "
                    "and basis step-up drive the sequence instead?",
        "tool_grounding_required": ["get_tax_brackets", "get_state_trust_rules"],
    },
    {
        "id": "c2",
        "scenario_id": SCENARIO_ID,
        "topic": "selling down the concentrated position to diversify, now vs. staged",
        "type": "recommendation",
        "materiality": "changes_number",
        "positions": [
            {"agent": "financial_advisor",
             "expected_position": "Sell most of the founder-stock proceeds and trim "
             "the $8M public book to hit target allocation as soon as the cash lands; "
             "the concentration risk (56% of net worth in one name) outweighs the tax."},
            {"agent": "tax_cpa",
             "expected_position": "A 2026 sale of the founder stock at the 4-year mark "
             "gets no QSBS exclusion: ~$21.4M gain x 23.8% federal is ~$5.1M, plus "
             "~13.3% California is ~$2.85M. Waiting to the 2027 five-year mark can "
             "take the federal portion toward zero; a pre-sale domicile change can "
             "remove the California portion (subject to audit risk). Diversify the "
             "already-liquid $8M over 2-3 years with loss harvesting; hedge the "
             "founder position rather than sell it early."},
        ],
        "question": "Does the concentration risk justify realizing the founder-stock "
                    "gain in 2026, given the QSBS timing and state-tax cost of doing so?",
        "tool_grounding_required": ["get_tax_brackets", "get_state_trust_rules"],
    },
    {
        "id": "c3",
        "scenario_id": SCENARIO_ID,
        "topic": "lifetime gift of appreciated stock vs. holding to death for step-up",
        "type": "recommendation",
        "materiality": "changes_action",
        "positions": [
            {"agent": "estate_attorney",
             "expected_position": "Gift appreciated shares now to use the $30M married "
             "exclusion and move future appreciation out of the estate."},
            {"agent": "tax_cpa",
             "expected_position": "A lifetime gift carries over the $600K basis; assets "
             "held to death get a full step-up that erases ~$21.4M of built-in gain "
             "(~$5M+ of eventual income tax). With this much embedded gain and a "
             "54-year-old donor, model the income-tax cost of carryover basis against "
             "the transfer-tax saving before gifting -- consider gifting cash or "
             "post-sale proceeds instead."},
        ],
        "question": "For assets with a very low basis, does the transfer-tax saving "
                    "from a lifetime gift beat the income tax the heirs save from a "
                    "step-up at death?",
        "tool_grounding_required": ["get_tax_brackets"],
    },
    {
        # Estate track's seeded conflict (ESTATE_ATTORNEY_HANDOFF.md), for the
        # business_sale_pre_loi scenario. tax_cpa's instinct to wait for a fixed
        # price collides with the step-transaction doctrine.
        "id": "c4",
        "scenario_id": SCENARIO_ID_PRE_LOI,
        "topic": "trust funding timing relative to the letter of intent",
        "type": "sequencing",
        "materiality": "changes_action",
        "positions": [
            {"agent": "tax_cpa",
             "expected_position": "Fund the trust after the LOI is signed and the sale "
             "price is fixed, so the gifted stock's value for gift-tax purposes is "
             "certain and defensible with a qualified appraisal. A Nevada or Delaware "
             "situs trust could also shelter trust-level income from California tax."},
            {"agent": "estate_attorney",
             "expected_position": "Fund the trust before any LOI or agreement in "
             "principle exists. Under the step-transaction / assignment-of-income "
             "doctrine the IRS can collapse a gift made after a near-binding sale "
             "agreement, taxing the gain to the grantor. Separately, California taxes "
             "DING/NING trust income back to a California-resident grantor regardless "
             "of situs, so a Nevada trust does not save state income tax here."},
        ],
        "question": "Is trust funding timed to the gift-tax valuation (after the LOI) "
                    "or to step-transaction risk (before any LOI)?",
        "tool_grounding_required": ["get_state_trust_rules"],
        "note": "For this conflict to fire, tax_cpa must actually propose the "
                "after-LOI timing and/or the Nevada situs -- both fall out of the "
                "persona's 'don't rush appreciated property into a trust' and 'a "
                "non-grantor trust has its own situs' reflexes.",
    },
]


GOLD_MEMO_POINTS = [
    {"conflict_id": "c1",
     "must_resolve": "Memo picks a sequence: it does not leave 'set up a trust' and "
     "'time the sale for QSBS' as unreconciled parallel advice.",
     "grounding": "The $30M exclusion, the 40% rate, and the 2027-03-10 QSBS date "
     "each trace to a get_tax_brackets / portfolio value.",
     "open_question_routing": "Trust drafting and QSBS-qualification opinion -> "
     "'consult a licensed estate attorney / tax attorney'."},
    {"conflict_id": "c2",
     "must_resolve": "Memo states an explicit realize-now vs. stage decision with the "
     "dollar tax figure attached, and a concrete hedge/stage alternative if it "
     "recommends waiting.",
     "grounding": "23.8% federal and 13.3% California both trace to tool results; the "
     "~$8M / ~$2.85M figures are shown, not asserted.",
     "open_question_routing": "Hedging instrument selection and target allocation -> "
     "'consult a licensed CFP'."},
    {"conflict_id": "c3",
     "must_resolve": "Memo weighs carryover basis vs. step-up in dollar terms and "
     "gives a recommendation (e.g. gift cash / post-sale proceeds, not the low-basis "
     "shares).",
     "grounding": "Carryover-basis rule and step-up rule cited from get_tax_brackets "
     "(estate_and_gift.lifetime_gift_basis_rule / basis_step_up_at_death) or "
     "get_state_trust_rules('federal').",
     "open_question_routing": "Estate-plan structure -> 'consult a licensed estate "
     "attorney'."},
    {"conflict_id": "c4",
     "must_resolve": "Memo lands on funding the trust BEFORE any LOI, using a "
     "qualified appraisal for the not-yet-fixed value -- step-transaction risk wins "
     "over valuation certainty. It also notes the Nevada-situs idea does not help a "
     "California resident.",
     "grounding": "step_transaction_risk_note and the California DING/NING carve-out "
     "both cited from get_state_trust_rules; the ~$3.95M gain is within the $10M "
     "single-holder QSBS exclusion, so multiplied/stacked exclusion is unnecessary.",
     "open_question_routing": "Trust drafting and the qualified appraisal -> "
     "'consult a licensed estate attorney' and 'a qualified appraiser'."},
]


if __name__ == "__main__":
    n_direct = sum(1 for t in ROUTER_LABELS if t["gold_tier"] == "direct")
    n_swarm = len(ROUTER_LABELS) - n_direct
    print(f"router labels: {len(ROUTER_LABELS)} ({n_direct} direct, {n_swarm} swarm, "
          f"{sum(1 for t in ROUTER_LABELS if t.get('high_liability'))} high-liability)")
    by_scenario: dict[str, list[str]] = {}
    for c in PLANTED_CONFLICTS:
        by_scenario.setdefault(c["scenario_id"], []).append(c["id"])
    for sid, ids in by_scenario.items():
        print(f"planted conflicts: {ids} for scenario {sid!r}")
    print(f"gold memo points: {[g['conflict_id'] for g in GOLD_MEMO_POINTS]}")
    agents = {p["agent"] for c in PLANTED_CONFLICTS for p in c["positions"]}
    print(f"agents referenced: {sorted(agents)}")
    assert {g["conflict_id"] for g in GOLD_MEMO_POINTS} == {c["id"] for c in PLANTED_CONFLICTS}
