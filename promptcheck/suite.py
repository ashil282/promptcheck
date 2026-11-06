import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .checks import REGISTRY

DEFAULT_BASE_URL = "http://localhost:11434/v1"


class SuiteError(Exception):
    pass


@dataclass
class Case:
    name: str
    prompt: str
    checks: list[dict]
    system: str | None = None
    repeat: int = 1
    min_pass_rate: float = 1.0


@dataclass
class Suite:
    path: str
    model: str
    base_url: str
    api_key: str | None
    system: str | None
    temperature: float
    judge_model: str
    concurrency: int
    cases: list[Case] = field(default_factory=list)


def _fill_vars(text: str, variables: dict) -> str:
    def sub(m):
        key = m.group(1)
        if key not in variables:
            raise SuiteError(f"prompt uses {{{{{key}}}}} but it isn't under `vars`")
        return str(variables[key])

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", sub, text)


def load_suite(path: str | Path) -> Suite:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        raise SuiteError(f"{path} not found")
    except yaml.YAMLError as e:
        raise SuiteError(f"{path} isn't valid YAML: {e}")
    if not isinstance(raw, dict):
        raise SuiteError("top level of the suite must be a mapping")
    if "model" not in raw:
        raise SuiteError("`model` is required")
    if not raw.get("cases"):
        raise SuiteError("no cases defined")

    variables = raw.get("vars") or {}
    key_env = raw.get("api_key_env", "OPENAI_API_KEY")

    suite = Suite(
        path=str(path),
        model=raw["model"],
        base_url=os.getenv("PROMPTCHECK_BASE_URL") or raw.get("base_url", DEFAULT_BASE_URL),
        api_key=os.getenv(key_env),
        system=raw.get("system"),
        temperature=float(raw.get("temperature", 0.0)),
        judge_model=raw.get("judge_model", raw["model"]),
        concurrency=int(raw.get("concurrency", 2)),
    )

    seen = set()
    for i, c in enumerate(raw["cases"], 1):
        name = c.get("name") or f"case {i}"
        if name in seen:
            raise SuiteError(f"duplicate case name: {name!r}")
        seen.add(name)
        if "prompt" not in c:
            raise SuiteError(f"{name}: `prompt` is required")
        checks = c.get("checks") or []
        if not checks:
            raise SuiteError(f"{name}: needs at least one check")
        for spec in checks:
            if not isinstance(spec, dict) or len(spec) != 1:
                raise SuiteError(
                    f"{name}: each check must be a single `type: value` pair, got {spec!r}"
                )
            (kind,) = spec
            if kind not in REGISTRY:
                known = ", ".join(sorted(REGISTRY))
                raise SuiteError(f"{name}: unknown check {kind!r} (known: {known})")
        suite.cases.append(
            Case(
                name=name,
                prompt=_fill_vars(c["prompt"], variables),
                checks=checks,
                system=c.get("system"),
                repeat=int(c.get("repeat", 1)),
                min_pass_rate=float(c.get("min_pass_rate", 1.0)),
            )
        )
    return suite
