from promptcheck.checks import run_check
from promptcheck.client import Reply


def r(text, ms=100):
    return Reply(text=text, latency_ms=ms)


def check(spec, text, ms=100):
    return run_check(spec, r(text, ms), {"judge": None})


def test_contains_and_not_contains():
    assert check({"contains": "Paris"}, "It's Paris.")[0]
    assert not check({"contains": ["Paris", "Rome"]}, "It's Paris.")[0]
    assert not check({"not_contains": "sorry"}, "sorry, no")[0]
    assert check({"icontains": "paris"}, "PARIS")[0]


def test_equals_ignores_outer_whitespace():
    assert check({"equals": "51"}, " 51\n")[0]
    assert not check({"equals": "51"}, "It is 51")[0]


def test_regex_and_limits():
    assert check({"regex": r"^\d+$"}, "42")[0]
    assert not check({"max_words": 2}, "one two three")[0]
    assert not check({"max_chars": 3}, "abcd")[0]
    assert not check({"latency_under_ms": 50}, "x", ms=80)[0]


def test_json_handles_code_fences():
    assert check({"is_json": True}, '```json\n{"a": 1}\n```')[0]
    assert not check({"is_json": True}, "here you go: {}")[0]


def test_json_schema_reports_the_path():
    schema = {"type": "object", "properties": {"total": {"type": "number"}}, "required": ["total"]}
    assert check({"json_schema": schema}, '{"total": 3}')[0]
    ok, msg = check({"json_schema": schema}, '{"total": "3"}')
    assert not ok and "total" in msg
