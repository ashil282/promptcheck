import textwrap

import pytest

from promptcheck import history
from promptcheck.cli import main
from promptcheck.client import Client
from promptcheck.runner import run_suite
from promptcheck.suite import SuiteError, load_suite


def write_suite(tmp_path, llm, body):
    p = tmp_path / "s.yaml"
    p.write_text(f"model: fake\nbase_url: {llm.url}\n" + textwrap.dedent(body))
    return p


def test_pass_and_fail(tmp_path, llm):
    llm.replies = {"capital": "Paris", "colour": "blue"}
    p = write_suite(tmp_path, llm, """
        cases:
          - name: a
            prompt: capital?
            checks: [{contains: Paris}]
          - name: b
            prompt: colour of banana?
            checks: [{icontains: yellow}]
    """)
    suite = load_suite(p)
    rec = run_suite(suite, Client(suite.base_url))
    by = {c["name"]: c for c in rec["cases"]}
    assert by["a"]["passed"] and not by["b"]["passed"]
    assert "yellow" in by["b"]["failures"][0]


def test_repeat_and_min_pass_rate(tmp_path, llm):
    llm.replies = {"x": "ok"}
    p = write_suite(tmp_path, llm, """
        cases:
          - name: r
            prompt: x
            repeat: 4
            min_pass_rate: 0.5
            checks: [{contains: ok}]
    """)
    suite = load_suite(p)
    rec = run_suite(suite, Client(suite.base_url))
    assert rec["cases"][0]["attempts"] == 4 and rec["cases"][0]["pass_rate"] == 1.0


def test_judge_fail_is_reported(tmp_path, llm):
    llm.replies = {"x": "anything", "__judge__": "FAIL\ninvented a number"}
    p = write_suite(tmp_path, llm, """
        cases:
          - name: j
            prompt: x
            checks: [{judge: no invented numbers}]
    """)
    suite = load_suite(p)
    rec = run_suite(suite, Client(suite.base_url))
    assert not rec["cases"][0]["passed"]
    assert "invented a number" in rec["cases"][0]["failures"][0]


def test_server_error_becomes_failure_not_crash(tmp_path, llm):
    llm.replies = {"x": "__500__"}
    p = write_suite(tmp_path, llm, """
        cases:
          - name: e
            prompt: x
            checks: [{contains: a}]
    """)
    suite = load_suite(p)
    rec = run_suite(suite, Client(suite.base_url))
    assert "request failed" in rec["cases"][0]["failures"][0]


def test_vars_and_validation(tmp_path, llm):
    p = write_suite(tmp_path, llm, """
        vars: {city: Lisbon}
        cases:
          - prompt: "tram in {{city}}"
            checks: [{contains: a}]
    """)
    assert load_suite(p).cases[0].prompt == "tram in Lisbon"

    bad = write_suite(tmp_path, llm, """
        cases:
          - name: z
            prompt: hi
            checks: [{containz: a}]
    """)
    with pytest.raises(SuiteError, match="unknown check"):
        load_suite(bad)


def test_cli_exit_codes_and_diff(tmp_path, llm, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    p = write_suite(tmp_path, llm, """
        cases:
          - name: a
            prompt: capital?
            checks: [{contains: Paris}]
    """)
    llm.replies = {"capital": "Paris"}
    assert main(["run", str(p)]) == 0
    llm.replies = {"capital": "Lyon"}
    assert main(["run", str(p)]) == 1
    assert len(history.list_runs()) == 2
    capsys.readouterr()
    assert main(["diff"]) == 1
    assert "REGRESSED  a" in capsys.readouterr().out
