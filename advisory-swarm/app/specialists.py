"""Declarative fixed panel. Every swarm turn dispatches all of them, in parallel.

PLUG-IN CONTRACT for tax_cpa / estate_attorney (or anyone merging in a new specialist module):
each specialist needs a Python module exporting exactly two names in the same shape as
tools_financial_advisor.py:

    TOOL_SCHEMAS: list[dict]   # Anthropic tool-use schemas: [{"name", "description", "input_schema"}, ...]
    TOOL_IMPLS:   dict[str, Callable[..., dict]]   # name -> pure function returning a JSON-able dict

...plus a persona prompt at app/prompts/<id>.txt. Register both below and the orchestrator picks
it up automatically — no other file needs to change.
"""

import tools_financial_advisor

SPECIALISTS = [
    {
        "id": "financial_advisor",
        "display_name": "Financial Advisor",
        "persona_file": "prompts/financial_advisor.txt",
        "tool_schemas": tools_financial_advisor.TOOL_SCHEMAS,
        "tool_impls": tools_financial_advisor.TOOL_IMPLS,
    },
    # --- tax_cpa: uncomment once merged ---
    # import tools_tax_cpa
    # {
    #     "id": "tax_cpa",
    #     "display_name": "Tax CPA",
    #     "persona_file": "prompts/tax_cpa.txt",
    #     "tool_schemas": tools_tax_cpa.TOOL_SCHEMAS,
    #     "tool_impls": tools_tax_cpa.TOOL_IMPLS,
    # },
    # --- estate_attorney: uncomment once merged ---
    # import tools_estate_attorney
    # {
    #     "id": "estate_attorney",
    #     "display_name": "Estate Attorney",
    #     "persona_file": "prompts/estate_attorney.txt",
    #     "tool_schemas": tools_estate_attorney.TOOL_SCHEMAS,
    #     "tool_impls": tools_estate_attorney.TOOL_IMPLS,
    # },
]
