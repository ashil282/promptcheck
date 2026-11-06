"""Each check takes (arg, reply, ctx) and returns (ok, message).
The message only matters when ok is False."""

import json
import re

from jsonschema import Draft202012Validator

from .client import ClientError, Reply


def _list(v):
    return [v] if isinstance(v, str) else list(v)


def parse_json(text: str):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return json.loads(t)


def c_contains(arg, r: Reply, ctx):
    missing = [s for s in _list(arg) if s not in r.text]
    return not missing, f"missing {missing}"


def c_icontains(arg, r: Reply, ctx):
    low = r.text.lower()
    missing = [s for s in _list(arg) if s.lower() not in low]
    return not missing, f"missing (case-insensitive) {missing}"


def c_not_contains(arg, r: Reply, ctx):
    found = [s for s in _list(arg) if s in r.text]
    return not found, f"should not contain {found}"


def c_equals(arg, r: Reply, ctx):
    return r.text.strip() == str(arg).strip(), f"expected exactly {str(arg)!r}"


def c_regex(arg, r: Reply, ctx):
    return re.search(arg, r.text, re.MULTILINE) is not None, f"no match for /{arg}/"


def c_max_words(arg, r: Reply, ctx):
    n = len(r.text.split())
    return n <= arg, f"{n} words, limit {arg}"


def c_max_chars(arg, r: Reply, ctx):
    n = len(r.text)
    return n <= arg, f"{n} chars, limit {arg}"


def c_is_json(arg, r: Reply, ctx):
    try:
        parse_json(r.text)
        ok = True
    except (ValueError, IndexError):
        ok = False
    return ok == bool(arg), "not valid JSON" if arg else "unexpectedly valid JSON"


def c_json_schema(arg, r: Reply, ctx):
    try:
        data = parse_json(r.text)
    except (ValueError, IndexError):
        return False, "not valid JSON"
    errors = sorted(Draft202012Validator(arg).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        where = "/".join(str(p) for p in e.path) or "(root)"
        return False, f"schema: {where}: {e.message}"
    return True, ""


def c_latency_under_ms(arg, r: Reply, ctx):
    return r.latency_ms <= arg, f"took {r.latency_ms}ms, limit {arg}ms"


JUDGE_SYSTEM = (
    "You are grading an AI response against criteria. "
    "Reply with PASS or FAIL on the first line, then one short sentence explaining why."
)


def c_judge(arg, r: Reply, ctx):
    judge = ctx["judge"]  # (client, model)
    if judge is None:
        return False, "judge check needs a client"
    client, model = judge
    try:
        out = client.chat(
            model,
            [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": f"Criteria: {arg}\n\nResponse to grade:\n{r.text}"},
            ],
            temperature=0.0,
        )
    except ClientError as e:
        return False, f"judge request failed: {e}"
    lines = out.text.strip().splitlines()
    first = lines[0].strip().upper() if lines else ""
    reason = " ".join(lines[1:]).strip() or "no reason given"
    if first.startswith("PASS"):
        return True, ""
    return False, f"judge said fail: {reason}"


REGISTRY = {
    "contains": c_contains,
    "icontains": c_icontains,
    "not_contains": c_not_contains,
    "equals": c_equals,
    "regex": c_regex,
    "max_words": c_max_words,
    "max_chars": c_max_chars,
    "is_json": c_is_json,
    "json_schema": c_json_schema,
    "latency_under_ms": c_latency_under_ms,
    "judge": c_judge,
}


def run_check(spec: dict, reply: Reply, ctx: dict) -> tuple[bool, str]:
    (name, arg), = spec.items()
    return REGISTRY[name](arg, reply, ctx)


def describe(spec: dict) -> str:
    (name, arg), = spec.items()
    return f"{name}: {arg}" if not isinstance(arg, (dict, list)) else name
