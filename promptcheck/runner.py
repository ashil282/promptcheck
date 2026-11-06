from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .checks import describe, run_check
from .client import Client, ClientError
from .suite import Case, Suite


def _attempt(client: Client, suite: Suite, case: Case, ctx: dict) -> dict:
    system = case.system if case.system is not None else suite.system
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": case.prompt}
    ]
    try:
        reply = client.chat(suite.model, messages, suite.temperature)
    except ClientError as e:
        return {
            "passed": False,
            "failures": [f"request failed: {e}"],
            "text": "",
            "latency_ms": 0,
            "tokens": [0, 0],
        }

    failures = []
    for spec in case.checks:
        ok, msg = run_check(spec, reply, ctx)
        if not ok:
            failures.append(f"{describe(spec)} -> {msg}")
    return {
        "passed": not failures,
        "failures": failures,
        "text": reply.text,
        "latency_ms": reply.latency_ms,
        "tokens": [reply.prompt_tokens, reply.completion_tokens],
    }


def run_suite(suite: Suite, client: Client, only: str | None = None, on_case=None) -> dict:
    cases = [c for c in suite.cases if not only or only in c.name]
    ctx = {"judge": (client, suite.judge_model)}

    jobs = [(c, i) for c in cases for i in range(max(1, c.repeat))]
    with ThreadPoolExecutor(max_workers=max(1, suite.concurrency)) as pool:
        futures = [pool.submit(_attempt, client, suite, c, ctx) for c, _ in jobs]
        outcomes = [f.result() for f in futures]

    results, p_tok, c_tok = [], 0, 0
    for case in cases:
        attempts = [o for (c, _), o in zip(jobs, outcomes) if c is case]
        passed_n = sum(a["passed"] for a in attempts)
        rate = passed_n / len(attempts)
        failures = []
        for a in attempts:
            for f in a["failures"]:
                if f not in failures:
                    failures.append(f)
        timed = [a["latency_ms"] for a in attempts if a["latency_ms"]]
        for a in attempts:
            p_tok += a["tokens"][0]
            c_tok += a["tokens"][1]
        first_fail = next((a for a in attempts if not a["passed"]), attempts[0])
        res = {
            "name": case.name,
            "passed": rate >= case.min_pass_rate,
            "pass_rate": round(rate, 3),
            "attempts": len(attempts),
            "avg_latency_ms": int(sum(timed) / len(timed)) if timed else 0,
            "failures": failures,
            "sample": first_fail["text"][:400],
        }
        results.append(res)
        if on_case:
            on_case(res)

    return {
        "version": 1,
        "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "suite": suite.path,
        "model": suite.model,
        "cases": results,
        "totals": {
            "cases": len(results),
            "passed": sum(r["passed"] for r in results),
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
        },
    }
