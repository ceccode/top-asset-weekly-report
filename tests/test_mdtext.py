from mdtext import extract_section, strip_inline_formatting, truncate_at_word


def test_extract_section_stops_at_the_next_heading():
    markdown = "## One\n\nfirst\n\n## Two\n\nsecond\n"

    assert extract_section(markdown, "One") == "first"
    assert extract_section(markdown, "Two") == "second"


def test_extract_section_is_empty_when_the_heading_is_missing():
    assert extract_section("## One\n\nfirst\n", "Three") == ""


def test_strip_inline_formatting():
    assert strip_inline_formatting("**bold** *it* `code`") == "bold it code"


def test_truncate_keeps_short_text_untouched():
    assert truncate_at_word("short", 10) == "short"


def test_truncate_cuts_at_a_word_boundary():
    assert truncate_at_word("one two three four five", 15) == "one two three…"
