"""Declarative fixed panel. Every swarm turn dispatches all of them, in parallel.

PLUG-IN CONTRACT for a new specialist module: export TOOL_SCHEMAS (list[dict]) and TOOL_IMPLS
(dict[name -> fn]) in the shape of tools_financial_advisor.py, plus a persona at
app/prompts/<id>.txt. estate_attorney's merged-in module used a single TOOL_SPEC dict instead —
adapted below rather than editing their file under time pressure.
"""

import sys
from pathlib import Path

import tools_financial_advisor

_APP_DIR = Path(__file__).parent
sys.path.insert(0, str(_APP_DIR / "tools"))
import estate_attorney_tools  # noqa: E402
import tax_cpa_tools  # noqa: E402

SPECIALISTS = [
    {
        "id": "financial_advisor",
        "display_name": "Financial Advisor",
        "persona_file": "prompts/financial_advisor.txt",
        "tool_schemas": tools_financial_advisor.TOOL_SCHEMAS,
        "tool_impls": tools_financial_advisor.TOOL_IMPLS,
    },
    {
        "id": "estate_attorney",
        "display_name": "Estate Attorney",
        "persona_file": "prompts/estate_attorney.txt",
        "tool_schemas": [estate_attorney_tools.TOOL_SPEC],
        "tool_impls": {"get_state_trust_rules": estate_attorney_tools.get_state_trust_rules},
    },
    {
        "id": "tax_cpa",
        "display_name": "Tax CPA",
        "persona_file": "prompts/tax_cpa.txt",
        "tool_schemas": tax_cpa_tools.TAX_TOOLS,
        "tool_impls": tax_cpa_tools.TAX_TOOL_IMPLS,
    },
]
