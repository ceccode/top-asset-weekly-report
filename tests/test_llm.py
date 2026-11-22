import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from llm import _parse_llm_response, build_input, generate_llm_sections, is_placeholder
from metrics import calculate_metrics

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"


def test_without_api_key_sections_are_deterministic_placeholders(ranked):
    input_data = {"assets": [a.to_dict() for a in ranked], "metrics": calculate_metrics(ranked)}

    sections = generate_llm_sections(input_data, "", "global", api_key=None)

    assert set(sections) == {"executive_summary", "strategic_reflection", "implications"}
    assert "Alpha Corp, Beta Inc, Gamma Ltd, Delta SA, Epsilon AG" in sections["executive_summary"]
    assert "$1.00T" in sections["executive_summary"]


def test_llm_response_is_split_into_sections():
    response = (
        "### Executive Summary\nA\n\n"
        "### Strategic Reflection\nB\n\n"
        "### Implications\nC"
    )

    assert _parse_llm_response(response, {}, "global") == {
        "executive_summary": "A",
        "strategic_reflection": "B",
        "implications": "C",
    }


def test_missing_llm_sections_fall_back_to_placeholders():
    sections = _parse_llm_response("### Executive Summary\nA", {}, "global")

    assert sections["executive_summary"] == "A"
    assert "will be enhanced" in sections["implications"]


def test_openai_is_a_declared_dependency():
    """Without it the LLM call silently degrades to placeholders in CI."""
    declared = [
        line.split("#")[0].strip().lower()
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    ]

    assert any(line.startswith("openai") for line in declared)


@pytest.fixture
def openai_answers(monkeypatch):
    """Install a fake `openai` package whose response yields the given outcome."""

    class OpenAIError(Exception):
        pass

    def install(outcome):
        class Responses:
            def create(self, **kwargs):
                module.requests.append(kwargs)
                if isinstance(outcome, Exception):
                    raise outcome
                return SimpleNamespace(output_text=outcome)

        class OpenAI:
            def __init__(self, api_key):
                self.responses = Responses()

        module = types.ModuleType("openai")
        module.OpenAI = OpenAI
        module.OpenAIError = OpenAIError
        module.requests = []
        monkeypatch.setitem(sys.modules, "openai", module)
        return module

    return install


def test_llm_answer_becomes_the_sections(openai_answers):
    openai_answers(
        "### Executive Summary\nA\n\n### Strategic Reflection\nB\n\n### Implications\nC"
    )

    sections = generate_llm_sections({}, "", "global", api_key="key")

    assert sections == {"executive_summary": "A", "strategic_reflection": "B", "implications": "C"}


def test_api_failure_falls_back_to_placeholders(openai_answers):
    openai = openai_answers(None)
    openai_answers(openai.OpenAIError("rate limited"))

    sections = generate_llm_sections({}, "", "global", api_key="key")

    assert "will be enhanced" in sections["executive_summary"]


def test_empty_answer_falls_back_to_placeholders(openai_answers):
    openai_answers(None)

    sections = generate_llm_sections({}, "", "global", api_key="key")

    assert "will be enhanced" in sections["executive_summary"]


def test_programming_errors_are_not_mistaken_for_api_failures(openai_answers):
    openai_answers(ValueError("bug in our code"))

    with pytest.raises(ValueError):
        generate_llm_sections({}, "", "global", api_key="key")


ANSWER = "### Executive Summary\nA\n\n### Strategic Reflection\nB\n\n### Implications\nC"


def test_request_names_the_model_and_carries_the_data(openai_answers, monkeypatch, ranked):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    openai = openai_answers(ANSWER)
    input_data = build_input("2025-12-31", ranked, {"asset_count": 6}, ([], [], []))

    generate_llm_sections(input_data, "Earlier commentary.", "global", api_key="key")

    request = openai.requests[0]
    assert request["model"] == "gpt-6.1-terra"
    assert "NEVER provide financial advice" in request["instructions"]
    assert '"date": "2025-12-31"' in request["input"]
    assert '"ticker": "AAA"' in request["input"]
    assert "Earlier commentary." in request["input"]
    assert "### Strategic Reflection\n[content]" in request["input"]


def test_model_can_be_chosen_from_the_environment(openai_answers, monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "some-other-model")
    openai = openai_answers(ANSWER)

    generate_llm_sections({}, "", "global", api_key="key")

    assert openai.requests[0]["model"] == "some-other-model"


def test_llm_input_keeps_the_top_assets_as_plain_data(ranked):
    many = [ranked[0].ranked(i) for i in range(1, 31)]

    input_data = build_input("2025-12-31", many, {}, (["AAA"], ["ZZZ"], []))

    assert len(input_data["assets"]) == 20
    assert input_data["assets"][0] == many[0].to_dict()
    assert (input_data["entries"], input_data["exits"]) == (["AAA"], ["ZZZ"])


def test_placeholders_are_told_apart_from_llm_output():
    placeholders = generate_llm_sections({}, "", "global", api_key=None)

    assert is_placeholder(placeholders)
    assert not is_placeholder({"executive_summary": "A", "strategic_reflection": "B", "implications": "C"})
