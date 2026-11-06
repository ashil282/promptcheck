import sys

_COLORS = {"green": "32", "red": "31", "dim": "2", "bold": "1"}


def _c(text: str, color: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{_COLORS[color]}m{text}\033[0m"


def print_case(res: dict) -> None:
    tag = _c("PASS", "green") if res["passed"] else _c("FAIL", "red")
    extra = f"{res['avg_latency_ms']}ms"
    if res["attempts"] > 1:
        n = round(res["pass_rate"] * res["attempts"])
        extra = f"{n}/{res['attempts']} runs, {extra}"
    print(f"{tag}  {res['name']}  {_c('(' + extra + ')', 'dim')}")
    if not res["passed"]:
        for f in res["failures"]:
            print(f"      - {f}")
        if res["sample"]:
            snippet = res["sample"].replace("\n", " ")
            print(_c(f"      output: {snippet[:160]}", "dim"))


def print_summary(record: dict) -> None:
    t = record["totals"]
    line = f"{t['passed']}/{t['cases']} cases passed  [{record['model']}]"
    print()
    print(_c(line, "green" if t["passed"] == t["cases"] else "red"))
    if t["prompt_tokens"] or t["completion_tokens"]:
        print(_c(f"tokens: {t['prompt_tokens']} in, {t['completion_tokens']} out", "dim"))


def print_diff(d: dict, old_name: str, new_name: str) -> None:
    print(f"{old_name}  ->  {new_name}\n")
    if not any(d.values()):
        print("no changes")
        return
    for name in d["regressions"]:
        print(_c(f"REGRESSED  {name}", "red"))
    for name in d["fixed"]:
        print(_c(f"FIXED      {name}", "green"))
    for name, a, b in d["slower"]:
        print(f"SLOWER     {name}  {a}ms -> {b}ms")
    for name in d["added"]:
        print(f"NEW        {name}")
    for name in d["removed"]:
        print(f"REMOVED    {name}")
