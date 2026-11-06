import json
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(".promptcheck")


def save(record: dict, directory: Path = DIR) -> Path:
    directory.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"{stamp}.json"
    path.write_text(json.dumps(record, indent=2))
    return path


def list_runs(directory: Path = DIR) -> list[Path]:
    return sorted(directory.glob("*.json")) if directory.exists() else []


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def diff(old: dict, new: dict) -> dict:
    o = {c["name"]: c for c in old["cases"]}
    n = {c["name"]: c for c in new["cases"]}
    out = {"regressions": [], "fixed": [], "added": [], "removed": [], "slower": []}
    for name, c in n.items():
        if name not in o:
            out["added"].append(name)
            continue
        was = o[name]
        if was["passed"] and not c["passed"]:
            out["regressions"].append(name)
        elif not was["passed"] and c["passed"]:
            out["fixed"].append(name)
        a, b = was["avg_latency_ms"], c["avg_latency_ms"]
        if a and b and b > a * 1.5 and b - a > 200:
            out["slower"].append((name, a, b))
    out["removed"] = [name for name in o if name not in n]
    return out
