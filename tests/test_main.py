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


@pytest.fixture
def workspace(tmp_path, monkeypatch, ranked):
    """Empty data folders, and Yahoo replaced by the `ranked` fixture's assets."""
    for name in ["REPORTS_DIR", "SNAPSHOTS_DIR", "RAG_DIR"]:
        folder = tmp_path / name.lower()
        folder.mkdir()
        monkeypatch.setattr(cli, name, folder)
    fetched = [{k: v for k, v in asset.items() if k != "rank"} for asset in ranked]
    monkeypatch.setattr(cli, "fetch_all_tickers", lambda tickers: fetched)
    return tmp_path


REPORT = cli.ReportId("2025-12-31", "global")
OFFLINE = cli.Options(use_llm=False)


def test_generate_report_writes_report_snapshots_telegram_and_rag(workspace):
    assert cli.generate_report(REPORT, ["AAA"], OFFLINE) is True

    assert "| 1 | AAA |" in (workspace / "reports_dir/2025-12-31.global.md").read_text("utf-8")
    assert (workspace / "snapshots_dir/2025-12-31.global.csv").exists()
    assert (workspace / "snapshots_dir/2025-12-31.global.json").exists()
    assert (workspace / "snapshots_dir/2025-12-31.telegram.global.txt").exists()
    assert (workspace / "rag_dir/rag_context_global.txt").exists()


def test_generate_report_fails_when_yahoo_returns_nothing(workspace, monkeypatch):
    monkeypatch.setattr(cli, "fetch_all_tickers", lambda tickers: [])

    assert cli.generate_report(REPORT, ["AAA"], OFFLINE) is False
    assert list((workspace / "reports_dir").iterdir()) == []


def test_rag_file_is_left_alone_without_the_rag_check(workspace):
    (workspace / "reports_dir/2025-12-24.global.md").write_text(
        "## Executive Summary\n\nEarlier analysis.\n", encoding="utf-8"
    )

    cli.generate_report(REPORT, ["AAA"], cli.Options(use_llm=False, rag_check=False))

    assert list((workspace / "rag_dir").iterdir()) == []


def test_telegram_file_error_does_not_fail_the_report(workspace, monkeypatch):
    def unwritable(content, path):
        raise OSError("disk full")

    monkeypatch.setattr(cli, "save_telegram_txt", unwritable)

    assert cli.generate_report(REPORT, ["AAA"], OFFLINE) is True


def test_bug_in_an_extra_step_is_not_swallowed(workspace, monkeypatch):
    def buggy(*args):
        raise KeyError("bug in our code")

    monkeypatch.setattr(cli, "generate_telegram_txt", buggy)

    with pytest.raises(KeyError):
        cli.generate_report(REPORT, ["AAA"], OFFLINE)
