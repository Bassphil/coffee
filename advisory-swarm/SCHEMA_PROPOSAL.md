# Proposed schema fields — for `app/schemas.py`

Written from the financial_advisor side; these two schemas are shared across all three
specialists, so treat this as a proposal to merge/reconcile against, not a final file.

## `SpecialistDraft`

Output of Phase 1 (parallel drafts). `cross_domain_implications` and `what_id_push_back_on` are
load-bearing, not optional polish — the Design Document's conflict extractor reads these
structured sections directly rather than free prose ("the extractor reads those structured
sections, not free prose"). A specialist that leaves them empty produces zero conflicts
regardless of what its `domain_findings` prose actually says.

```jsonc
{
  "domain_findings": "string, prose, ≤ ~400 tokens",
  "recommendation": "string, prose, single clear action",
  "cross_domain_implications": [
    {"domain": "tax_cpa" | "estate_attorney", "implication": "string"}
  ],
  "what_id_push_back_on": [
    {"domain": "tax_cpa" | "estate_attorney", "concern": "string"}
  ],
  "assumptions": ["string"],
  "open_questions": ["string"]
}
```

Overall draft should target ~600 tokens (Design Document's cap) — enforced by keeping this
schema tight rather than by a separate length check.

## `Rebuttal`

Output of Phase 3, one round, per conflicting specialist. Matches Design Document lines 175-176
verbatim — including here for visibility since it constrains what the rebuttal prompt can ask
the model to produce.

```jsonc
{
  "position": "hold" | "concede" | "qualify",
  "reasoning": "string",
  "condition_under_which_other_is_right": "string",
  "revised_recommendation": "string"
}
```

Per the Design Document, the rebuttal prompt must give the specialist only the conflict
`question` and the counterpart's **verbatim quoted span** — never the counterpart's full draft.
Full drafts cause capitulation (a specialist defers to a confident adjacent expert, the conflict
evaporates, and the demo shows a fake resolution). The financial_advisor persona prompt
(`prompts/financial_advisor.txt`) is written assuming this input shape.
