import argparse
import json
import sys
from pathlib import Path

from . import __version__, history, report
from .client import Client
from .runner import run_suite
from .suite import SuiteError, load_suite

STARTER = """\
# point this at any OpenAI-compatible server. default is a local Ollama.
model: llama3.2:3b
base_url: http://localhost:11434/v1
temperature: 0
system: Answer as briefly as you can.

cases:
  - name: capital of france
    prompt: What is the capital of France? One word.
    checks:
      - contains: Paris
      - max_words: 3

  - name: refuses to invent a fact
    prompt: What was the population of Atlantis in 2019?
    checks:
      - judge: The response says Atlantis isn't real and does not make up a number.
"""


def cmd_run(args) -> int:
    suite = load_suite(args.suite)
    if args.model:
        suite.model = args.model
        suite.judge_model = args.model
    client = Client(suite.base_url, suite.api_key)

    print(f"{suite.path}: {len(suite.cases)} cases, model {suite.model}\n")
    on_case = None if args.json else report.print_case
    record = run_suite(suite, client, only=args.only, on_case=on_case)
    if not record["cases"]:
        print("no cases matched --only", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        report.print_summary(record)
    if not args.no_save:
        path = history.save(record)
        if not args.json:
            print(f"saved {path}")
    t = record["totals"]
    return 0 if t["passed"] == t["cases"] else 1


def cmd_diff(args) -> int:
    if args.old and args.new:
        old_p, new_p = Path(args.old), Path(args.new)
    else:
        runs = history.list_runs()
        if len(runs) < 2:
            print("need at least two saved runs in .promptcheck/", file=sys.stderr)
            return 2
        old_p, new_p = runs[-2], runs[-1]
    d = history.diff(history.load(old_p), history.load(new_p))
    report.print_diff(d, old_p.name, new_p.name)
    return 1 if d["regressions"] else 0


def cmd_init(args) -> int:
    p = Path(args.path)
    if p.exists():
        print(f"{p} already exists, not overwriting", file=sys.stderr)
        return 2
    p.write_text(STARTER)
    print(f"wrote {p}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="promptcheck", description="test cases for LLM prompts")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a suite")
    r.add_argument("suite")
    r.add_argument("--only", help="only run cases whose name contains this")
    r.add_argument("--model", help="override the model in the suite file")
    r.add_argument("--json", action="store_true", help="print the full result as JSON")
    r.add_argument("--no-save", action="store_true", help="don't write to .promptcheck/")
    r.set_defaults(fn=cmd_run)

    d = sub.add_parser("diff", help="compare two saved runs (default: the last two)")
    d.add_argument("old", nargs="?")
    d.add_argument("new", nargs="?")
    d.set_defaults(fn=cmd_diff)

    i = sub.add_parser("init", help="write a starter suite")
    i.add_argument("path", nargs="?", default="promptcheck.yaml")
    i.set_defaults(fn=cmd_init)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except SuiteError as e:
        print(f"suite error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
