import pytest

import main as cli


@pytest.fixture
def run(monkeypatch):
    """Run the CLI with report generation and publishing replaced by fakes."""
    calls = {"generated": [], "published": []}

    def install(failing=(), publish_succeeds=True):
        def fake_generate(report, tickers, options):
            calls["generated"].append((report.date, report.scope, options))
            if report.scope in failing:
                raise RuntimeError("boom")
            return True

        monkeypatch.setattr(cli, "generate_report", fake_generate)
        monkeypatch.setattr(cli, "TICKER_SOURCES", {"global": list, "software": list})

        def fake_publish(date, scopes):
            calls["published"].append((date, scopes))
            return publish_succeeds

        monkeypatch.setattr(cli, "build_public", fake_publish)
        return calls

    return install


def test_every_scope_is_generated_by_default(run):
    calls = run()

    assert cli.main(["--date", "2025-12-31"]) == 0
    assert [(date, scope) for date, scope, _ in calls["generated"]] == [
        ("2025-12-31", "global"),
        ("2025-12-31", "software"),
    ]
    assert calls["published"] == []


def test_only_limits_the_scopes(run):
    calls = run()

    assert cli.main(["--date", "2025-12-31", "--only", "software"]) == 0
    assert [scope for _, scope, _ in calls["generated"]] == ["software"]


def test_flags_become_options(run):
    calls = run()

    cli.main(["--date", "2025-12-31", "--only", "global", "--no-llm", "--top-n", "10"])

    options = calls["generated"][0][2]
    assert options == cli.Options(top_n=10, use_llm=False)


def test_invalid_date_is_rejected(run):
    calls = run()

    assert cli.main(["--date", "31/12/2025"]) == 1
    assert calls["generated"] == []


def test_exit_code_is_non_zero_when_nothing_was_generated(run):
    run(failing=("global", "software"))

    assert cli.main(["--date", "2025-12-31"]) == 1


def test_partial_success_publishes_what_worked_but_fails_the_run(run):
    calls = run(failing=("software",))

    assert cli.main(["--date", "2025-12-31", "--publish"]) == 1
    assert calls["published"] == [("2025-12-31", ["global"])]


def test_publish_gets_the_generated_scopes(run):
    calls = run()

    assert cli.main(["--date", "2025-12-31", "--publish"]) == 0
    assert calls["published"] == [("2025-12-31", ["global", "software"])]


def test_failed_publish_fails_the_run(run):
    run(publish_succeeds=False)

    assert cli.main(["--date", "2025-12-31", "--publish"]) == 1
