"""LLM integration module for generating editorial sections."""

import json
import logging
import os
from typing import Dict, Any, Optional

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

You will receive market data and historical context. Generate the requested sections in Markdown format."""


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
        Dict with keys: executive_summary, riflessione, implicazioni
    """
    if not api_key:
        logger.info("No API key provided, using placeholder sections")
        return _generate_placeholders(input_data, report_type)
    
    try:
        return _call_openai(input_data, rag_context, report_type, api_key)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return _generate_placeholders(input_data, report_type)


def _generate_placeholders(input_data: Dict[str, Any], report_type: str) -> Dict[str, str]:
    """Generate deterministic placeholder sections when LLM is unavailable."""
    metrics = input_data.get("metrics", {})
    assets = input_data.get("assets", [])
    
    top5_names = ", ".join(a["name"] for a in assets[:5]) if assets else "N/A"
    total_cap = metrics.get("total_market_cap", 0)
    top5_conc = metrics.get("top5_concentration", 0)
    
    from metrics import format_market_cap
    
    scope_label = "global assets" if report_type == "global" else "software companies"
    
    executive_summary = f"""This week's analysis covers the top {scope_label} by market capitalization.

The combined market cap of the tracked assets stands at {format_market_cap(total_cap)}, with the top 5 assets ({top5_names}) representing {top5_conc:.1f}% of the total.

*This section will be enhanced with AI-generated insights when LLM integration is enabled.*"""

    riflessione = f"""The current market structure shows concentration patterns typical of {scope_label}.

Key observations from the data:
- Market leadership remains with established players
- Concentration metrics provide insight into market dynamics

*This section will be enhanced with AI-generated strategic analysis when LLM integration is enabled.*"""

    implicazioni = f"""The data presented reflects current market conditions for {scope_label}.

Observers may note:
- The relative positioning of assets by market capitalization
- Changes in concentration over time (when historical data is available)

*This section will be enhanced with AI-generated implications when LLM integration is enabled.*"""

    return {
        "executive_summary": executive_summary,
        "riflessione": riflessione,
        "implicazioni": implicazioni,
    }


def _call_openai(
    input_data: Dict[str, Any],
    rag_context: str,
    report_type: str,
    api_key: str
) -> Dict[str, str]:
    """Call OpenAI API to generate sections."""
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed, using placeholders")
        return _generate_placeholders(input_data, report_type)
    
    client = OpenAI(api_key=api_key)
    
    # Prepare the user prompt
    scope_label = "global assets" if report_type == "global" else "software companies"
    
    user_prompt = f"""Generate three sections for a weekly {scope_label} market report.

## Current Data
```json
{json.dumps(input_data, indent=2, default=str)}
```

## Historical Context (Previous Reports)
{rag_context if rag_context else "No historical context available."}

## Required Sections
Generate the following sections in Markdown format. Remember: NO financial advice, NO recommendations, ONLY observations and analysis.

1. **Executive Summary**: A brief overview of this week's market data (2-3 paragraphs)
2. **Riflessione Strategica**: Strategic observations about market structure and trends (2-3 paragraphs)
3. **Implicazioni**: What the data suggests about market dynamics (2-3 paragraphs)

Format your response as:
### Executive Summary
[content]

### Riflessione Strategica
[content]

### Implicazioni
[content]"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=2000,
    )
    
    content = response.choices[0].message.content
    return _parse_llm_response(content, input_data, report_type)


def _parse_llm_response(content: str, input_data: Dict[str, Any], report_type: str) -> Dict[str, str]:
    """Parse LLM response into separate sections."""
    import re
    
    sections = {
        "executive_summary": "",
        "riflessione": "",
        "implicazioni": "",
    }
    
    # Extract Executive Summary
    match = re.search(r"###?\s*Executive Summary\s*\n(.*?)(?=###|\Z)", content, re.DOTALL | re.IGNORECASE)
    if match:
        sections["executive_summary"] = match.group(1).strip()
    
    # Extract Riflessione Strategica
    match = re.search(r"###?\s*Riflessione Strategica\s*\n(.*?)(?=###|\Z)", content, re.DOTALL | re.IGNORECASE)
    if match:
        sections["riflessione"] = match.group(1).strip()
    
    # Extract Implicazioni
    match = re.search(r"###?\s*Implicazioni\s*\n(.*?)(?=###|\Z)", content, re.DOTALL | re.IGNORECASE)
    if match:
        sections["implicazioni"] = match.group(1).strip()
    
    # Fallback to placeholders for any missing sections
    if not all(sections.values()):
        placeholders = _generate_placeholders(input_data, report_type)
        for key in sections:
            if not sections[key]:
                sections[key] = placeholders[key]
    
    return sections
