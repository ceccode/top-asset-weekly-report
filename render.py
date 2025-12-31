"""Markdown report rendering."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

from config import DISCLAIMER, DISCLAIMER_SHORT
from metrics import format_market_cap

logger = logging.getLogger(__name__)


def render_frontmatter(
    title: str,
    date: str,
    scope: str,
) -> str:
    """Render YAML frontmatter."""
    return f"""---
title: "{title}"
date: {date}
source: Yahoo Finance
scope: {scope}
disclaimer: "{DISCLAIMER}"
---

"""


def render_ranking_table(ranked_assets: List[Dict[str, Any]]) -> str:
    """Render the ranking table in Markdown."""
    if not ranked_assets:
        return "*Nessun dato disponibile*\n"
    
    lines = [
        "| Pos. | Ticker | Nome | Tipo | Cap. Mercato | Valuta |",
        "|------|--------|------|------|--------------|--------|",
    ]
    
    for asset in ranked_assets:
        rank = asset.get("rank", "-")
        ticker = asset.get("ticker", "-")
        name = asset.get("name", "-")[:40]  # Truncate long names
        quote_type = asset.get("quote_type", "-")
        market_cap = format_market_cap(asset.get("market_cap", 0))
        currency = asset.get("currency", "-")
        
        lines.append(f"| {rank} | {ticker} | {name} | {quote_type} | {market_cap} | {currency} |")
    
    return "\n".join(lines) + "\n"


def render_metrics_section(metrics: Dict[str, Any]) -> str:
    """Render key metrics as bullet list."""
    if not metrics:
        return "*Nessuna metrica disponibile*\n"
    
    lines = [
        f"- **Capitalizzazione Totale (Top {metrics.get('asset_count', 'N')})**: {format_market_cap(metrics.get('total_market_cap', 0))}",
        f"- **Concentrazione Top 5**: {metrics.get('top5_concentration', 0):.1f}%",
        f"- **Concentrazione Top 10**: {metrics.get('top10_concentration', 0):.1f}%",
        f"- **Asset Monitorati**: {metrics.get('asset_count', 0)}",
    ]
    
    return "\n".join(lines) + "\n"


def render_changes_section(
    entries: List[str],
    exits: List[str],
    movers: List[Dict[str, Any]]
) -> str:
    """Render entries, exits, and movers."""
    lines = []
    
    if entries:
        lines.append(f"**Nuove Entrate**: {', '.join(entries)}")
    else:
        lines.append("**Nuove Entrate**: Nessuna")
    
    if exits:
        lines.append(f"**Uscite**: {', '.join(exits)}")
    else:
        lines.append("**Uscite**: Nessuna")
    
    if movers:
        lines.append("\n**Movimenti Rilevanti (per variazione posizione)**:")
        for m in movers[:5]:
            direction = "↑" if m["rank_delta"] > 0 else "↓"
            cap_change = f" ({m['cap_delta_pct']:+.1f}% cap)" if abs(m["cap_delta_pct"]) > 1 else ""
            lines.append(f"- {m['ticker']} ({m['name'][:20]}): {direction}{abs(m['rank_delta'])} posizioni{cap_change})")
    
    return "\n".join(lines) + "\n"


def render_observations(
    ranked_assets: List[Dict[str, Any]],
    metrics: Dict[str, Any]
) -> str:
    """Render quantitative observations."""
    if not ranked_assets or not metrics:
        return "*Dati insufficienti per le osservazioni*\n"
    
    lines = []
    
    # Top 5 dominance
    top5_conc = metrics.get("top5_concentration", 0)
    lines.append(f"- I Top 5 asset rappresentano il **{top5_conc:.1f}%** della capitalizzazione totale monitorata")
    
    # Top 10 dominance
    top10_conc = metrics.get("top10_concentration", 0)
    lines.append(f"- I Top 10 asset rappresentano il **{top10_conc:.1f}%** della capitalizzazione totale monitorata")
    
    # Largest asset
    if ranked_assets:
        largest = ranked_assets[0]
        largest_pct = (largest.get("market_cap", 0) / metrics.get("total_market_cap", 1)) * 100
        lines.append(f"- **{largest['name']}** ({largest['ticker']}) guida con {format_market_cap(largest.get('market_cap', 0))} ({largest_pct:.1f}% del totale)")
    
    # Asset type breakdown
    type_counts: Dict[str, int] = {}
    for asset in ranked_assets:
        qt = asset.get("quote_type", "UNKNOWN")
        type_counts[qt] = type_counts.get(qt, 0) + 1
    
    if type_counts:
        type_str = ", ".join(f"{k}: {v}" for k, v in sorted(type_counts.items(), key=lambda x: -x[1]))
        lines.append(f"- Distribuzione per tipologia: {type_str}")
    
    return "\n".join(lines) + "\n"


def render_methodology() -> str:
    """Render methodology and limitations section."""
    return """### Fonte Dati
- Dati di mercato da Yahoo Finance API
- I valori di capitalizzazione sono aggiornati al momento della generazione del report

### Metodologia
- Asset ordinati per capitalizzazione di mercato (decrescente)
- Metriche di concentrazione calcolate come percentuale della capitalizzazione totale monitorata
- Variazioni settimanali confrontate con lo snapshot precedente disponibile

### Limitazioni
- La disponibilità dei dati dipende dalla copertura di Yahoo Finance
- Alcuni asset potrebbero essere esclusi per mancanza di dati sulla capitalizzazione
- Conversioni valutarie non applicate; valori mostrati nella valuta nativa
- Questa analisi copre una lista curata di asset, non l'intero mercato
"""


def render_report(
    date: str,
    scope: str,
    ranked_assets: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    changes: Tuple[List[str], List[str], List[Dict[str, Any]]],
    llm_sections: Dict[str, str],
) -> str:
    """Render complete Markdown report."""
    entries, exits, movers = changes
    
    # Determine title based on scope
    if scope == "global":
        title = f"Report Settimanale Asset Globali - {date}"
        scope_label = "Asset Globali"
    else:
        title = f"Report Settimanale Aziende Software - {date}"
        scope_label = "Aziende Software"
    
    # Build report
    parts = []
    
    # Frontmatter
    parts.append(render_frontmatter(title, date, scope_label))
    
    # Title
    parts.append(f"# {title}\n\n")
    
    # Executive Summary
    parts.append("## Executive Summary\n\n")
    parts.append(llm_sections.get("executive_summary", "*Summary pending*") + "\n\n")
    
    # Ranking Table
    parts.append("## Classifica\n\n")
    parts.append(render_ranking_table(ranked_assets) + "\n")
    
    # Key Metrics
    parts.append("## Metriche Chiave\n\n")
    parts.append(render_metrics_section(metrics) + "\n")
    
    # Week-over-Week Changes
    parts.append("## Variazioni Settimanali\n\n")
    parts.append(render_changes_section(entries, exits, movers) + "\n")
    
    # Quantitative Observations
    parts.append("## Osservazioni Quantitative\n\n")
    parts.append(render_observations(ranked_assets, metrics) + "\n")
    
    # Methodology
    parts.append("## Metodologia e Limitazioni\n\n")
    parts.append(render_methodology() + "\n")
    
    # Strategic Reflection (LLM)
    parts.append("## Riflessione Strategica\n\n")
    parts.append(llm_sections.get("riflessione", "*Analysis pending*") + "\n\n")
    
    # Implications (LLM)
    parts.append("## Implicazioni\n\n")
    parts.append(llm_sections.get("implicazioni", "*Implications pending*") + "\n\n")
    
    # Footer
    parts.append("---\n\n")
    parts.append(f"*{DISCLAIMER_SHORT}*\n")
    
    return "".join(parts)


def save_report(content: str, filepath: Path) -> None:
    """Save report to file."""
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Saved report: {filepath}")
