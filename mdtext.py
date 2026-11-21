"""Small helpers for reading and trimming Markdown text."""

import re


def extract_section(md_text: str, heading: str) -> str:
    """Return the body of the `## heading` section, or "" when it is missing."""
    pattern = rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, md_text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def strip_inline_formatting(text: str) -> str:
    """Remove bold, italic and inline-code markers, keeping the text inside."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return re.sub(r"`([^`]+)`", r"\1", text)


def truncate_at_word(text: str, max_chars: int) -> str:
    """Cut text to max_chars, preferably at a word boundary, and add an ellipsis."""
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.7:
        truncated = truncated[:last_space]

    return truncated.rstrip(".,;:") + "…"
