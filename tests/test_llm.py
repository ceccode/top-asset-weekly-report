from pathlib import Path

from llm import _parse_llm_response, generate_llm_sections
from metrics import calculate_metrics

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"


def test_without_api_key_sections_are_deterministic_placeholders(ranked):
    input_data = {"assets": ranked, "metrics": calculate_metrics(ranked)}

    sections = generate_llm_sections(input_data, "", "global", api_key=None)

    assert set(sections) == {"executive_summary", "riflessione", "implicazioni"}
    assert "Alpha Corp, Beta Inc, Gamma Ltd, Delta SA, Epsilon AG" in sections["executive_summary"]
    assert "$1.00T" in sections["executive_summary"]


def test_llm_response_is_split_into_sections():
    response = (
        "### Executive Summary\nA\n\n"
        "### Riflessione Strategica\nB\n\n"
        "### Implicazioni\nC"
    )

    assert _parse_llm_response(response, {}, "global") == {
        "executive_summary": "A",
        "riflessione": "B",
        "implicazioni": "C",
    }


def test_missing_llm_sections_fall_back_to_placeholders():
    sections = _parse_llm_response("### Executive Summary\nA", {}, "global")

    assert sections["executive_summary"] == "A"
    assert "will be enhanced" in sections["implicazioni"]


def test_openai_is_a_declared_dependency():
    """Without it the LLM call silently degrades to placeholders in CI."""
    declared = [
        line.split("#")[0].strip().lower()
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    ]

    assert any(line.startswith("openai") for line in declared)
