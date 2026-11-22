"""LLM integration module for generating editorial sections."""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from asset import Asset
from config import get_openai_model
from metrics import format_market_cap
from report_id import ReportId

logger = logging.getLogger(__name__)

# System prompt that enforces no financial advice
SYSTEM_PROMPT = """You are a financial data analyst writing objective market commentary.

STRICT RULES:
1. NEVER provide financial advice or recommendations
2. NEVER use prescriptive language like "should", "must", "buy", "sell", "invest"
3. NEVER predict future performance
4. Use ONLY observational and analytical language
5. Focus on describing what the data shows, not what actions to take
6. Always maintain a neutral, informational tone
7. Write as of the report date, using ONLY the data provided: never draw on knowledge of later events
8. Write in English

You will receive market data and historical context. Generate the requested sections in Markdown format."""

# Present in every placeholder section, so they can be told apart from real LLM output
PLACEHOLDER_MARKER = "will be enhanced with AI-generated"

# Section key -> heading used both in the LLM answer and in the rendered report
SECTION_HEADINGS = {
    "executive_summary": "Executive Summary",
    "strategic_reflection": "Strategic Reflection",
    "implications": "Implications",
}

# Assets sent to the LLM, to keep the prompt small
LLM_ASSET_LIMIT = 20

# Room for the three sections plus the model's reasoning
MAX_OUTPUT_TOKENS = 6000


def build_input(
    date: str,
    ranked_assets: List[Asset],
    metrics: Dict[str, Any],
    changes: Tuple[List[str], List[str], List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """The data the commentary is written from, as plain JSON-ready values."""
    entries, exits, movers = changes
    return {
        "date": date,
        "assets": [asset.to_dict() for asset in ranked_assets[:LLM_ASSET_LIMIT]],
        "metrics": metrics,
        "entries": entries,
        "exits": exits,
        "movers": movers,
    }


def is_placeholder(sections: Dict[str, str]) -> bool:
    """True when any section is a placeholder rather than LLM output."""
    return any(PLACEHOLDER_MARKER in text for text in sections.values())


def generate_llm_sections(
    input_data: Dict[str, Any],
    rag_context: str,
    report_type: str,
    api_key: Optional[str] = None
) -> Dict[str, str]:
    """
    Generate LLM sections for the report.
    
    Args:
        input_data: Dict with ranked assets and metrics
        rag_context: Historical context from previous reports
        report_type: "global" or "software"
        api_key: OpenAI API key (optional)
    
    Returns:
        Dict with the keys of SECTION_HEADINGS
    """
    if not api_key:
        logger.info("No API key provided, using placeholder sections")
        return _generate_placeholders(input_data, report_type)
    
    return _call_openai(input_data, rag_context, report_type, api_key)


def _scope_label(report_type: str) -> str:
    return ReportId("", report_type).label.lower()


def _generate_placeholders(input_data: Dict[str, Any], report_type: str) -> Dict[str, str]:
    """Generate deterministic placeholder sections when LLM is unavailable."""
    metrics = input_data.get("metrics", {})
    assets = input_data.get("assets", [])
    
    top5_names = ", ".join(a["name"] for a in assets[:5]) if assets else "N/A"
    total_cap = metrics.get("total_market_cap", 0)
    top5_conc = metrics.get("top5_concentration", 0)
    
    scope_label = _scope_label(report_type)
    
    executive_summary = f"""This week's analysis covers the top {scope_label} by market capitalization.

The combined market cap of the tracked assets stands at {format_market_cap(total_cap)}, with the top 5 assets ({top5_names}) representing {top5_conc:.1f}% of the total.

*This section will be enhanced with AI-generated insights when LLM integration is enabled.*"""

    strategic_reflection = f"""The current market structure shows concentration patterns typical of {scope_label}.

Key observations from the data:
- Market leadership remains with established players
- Concentration metrics provide insight into market dynamics

*This section will be enhanced with AI-generated strategic analysis when LLM integration is enabled.*"""

    implications = f"""The data presented reflects current market conditions for {scope_label}.

Observers may note:
- The relative positioning of assets by market capitalization
- Changes in concentration over time (when historical data is available)

*This section will be enhanced with AI-generated implications when LLM integration is enabled.*"""

    return {
        "executive_summary": executive_summary,
        "strategic_reflection": strategic_reflection,
        "implications": implications,
    }


def _build_prompt(input_data: Dict[str, Any], rag_context: str, report_type: str) -> str:
    headings = list(SECTION_HEADINGS.values())
    answer_format = "\n\n".join(f"### {heading}\n[content]" for heading in headings)

    return f"""Generate three sections for a weekly {_scope_label(report_type)} market report.

## Current Data
```json
{json.dumps(input_data, indent=2, default=str)}
```

## Historical Context (Previous Reports)
{rag_context if rag_context else "No historical context available."}

## Required Sections
Generate the following sections in Markdown format. Remember: NO financial advice, NO recommendations, ONLY observations and analysis.

1. **{headings[0]}**: A brief overview of this week's market data (2-3 paragraphs)
2. **{headings[1]}**: Strategic observations about market structure and trends (2-3 paragraphs)
3. **{headings[2]}**: What the data suggests about market dynamics (2-3 paragraphs)

Format your response as:
{answer_format}"""


def _call_openai(
    input_data: Dict[str, Any],
    rag_context: str,
    report_type: str,
    api_key: str
) -> Dict[str, str]:
    """Call OpenAI API to generate sections; API failures fall back to placeholders."""
    try:
        from openai import OpenAI, OpenAIError
    except ImportError:
        logger.warning("openai package not installed, using placeholders")
        return _generate_placeholders(input_data, report_type)
    
    client = OpenAI(api_key=api_key)
    model = get_openai_model()

    try:
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=_build_prompt(input_data, rag_context, report_type),
            reasoning={"effort": "low"},
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except OpenAIError as e:
        logger.error(f"LLM call to {model} failed: {e}")
        return _generate_placeholders(input_data, report_type)
    
    # The API may answer with no text at all (e.g. a refusal)
    content = response.output_text or ""
    return _parse_llm_response(content, input_data, report_type)


def _parse_llm_response(content: str, input_data: Dict[str, Any], report_type: str) -> Dict[str, str]:
    """Parse LLM response into separate sections."""
    sections = {}
    for key, heading in SECTION_HEADINGS.items():
        match = re.search(
            rf"###?\s*{re.escape(heading)}\s*\n(.*?)(?=###|\Z)", content, re.DOTALL | re.IGNORECASE
        )
        sections[key] = match.group(1).strip() if match else ""
    
    # Fallback to placeholders for any missing sections
    if not all(sections.values()):
        placeholders = _generate_placeholders(input_data, report_type)
        for key in sections:
            if not sections[key]:
                sections[key] = placeholders[key]
    
    return sections
