# promptcheck

A small command line tool for testing LLM prompts the way you'd test code. You write cases in a YAML file, it runs them against a model, and it exits non-zero if something broke.

I wrote it because every time I changed a system prompt or swapped to a different model I was re-typing the same five questions into a chat window and eyeballing the answers. That doesn't scale past about a week.

It talks to anything that implements `/v1/chat/completions`: Ollama, llama.cpp's server, LM Studio, vLLM, or a hosted API. The default is Ollama on localhost, so you can run the whole thing offline on a laptop.

## Install

Python 3.10+.

```bash
git clone https://github.com/<you>/promptcheck.git
cd promptcheck
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

If you want to try it locally you'll also need [Ollama](https://ollama.com) and a model:

```bash
ollama pull llama3.2:3b
```

## Quick start

```bash
promptcheck init            # writes promptcheck.yaml
promptcheck run promptcheck.yaml
```

A suite looks like this:

```yaml
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

  - name: invoice extraction
    prompt: "Extract vendor and total as JSON: Northwind Traders, 1,240.50 EUR"
    checks:
      - is_json: true
      - json_schema:
          type: object
          required: [vendor, total]
```

Output:

```
promptcheck.yaml: 3 cases, model llama3.2:3b

PASS  capital of france  (412ms)
FAIL  banana colour  (388ms)
      - icontains: yellow -> missing (case-insensitive) ['yellow']
      output: It is blue
PASS  invoice extraction  (903ms)

2/3 cases passed  [llama3.2:3b]
tokens: 164 in, 71 out
saved .promptcheck/20261106T115112167068Z.json
```

More suites are in `examples/`.

## Checks

| check | passes when |
|---|---|
| `contains: str or [str]` | all of them appear (case-sensitive) |
| `icontains` | same, ignoring case |
| `not_contains` | none of them appear |
| `equals` | whole reply equals the value after trimming whitespace |
| `regex` | `re.search` finds a match (multiline) |
| `max_words`, `max_chars` | reply is short enough |
| `is_json: true` | reply parses as JSON (a code fence around it is tolerated) |
| `json_schema: {...}` | parsed JSON validates against the schema |
| `latency_under_ms` | the request was fast enough |
| `judge: "criteria"` | a second model call says PASS (see below) |

## Other suite options

- `vars:` at the top, used as `{{name}}` in prompts.
- `repeat: 5` and `min_pass_rate: 0.8` on a case, for prompts where the model isn't consistent. The case passes if at least 80% of runs do.
- `system:` can be set per case to override the suite one.
- `judge_model:` if you want a different model grading than the one being tested.
- `concurrency:` parallel requests, default 2. Small local models don't love more than that.
- `api_key_env:` which env var holds the key, default `OPENAI_API_KEY`. `PROMPTCHECK_BASE_URL` overrides `base_url`, handy for CI.

## Catching regressions

Every run is saved in `.promptcheck/`. After you change a prompt:

```bash
promptcheck run promptcheck.yaml
promptcheck diff
```

```
20261106T115112167068Z.json  ->  20261106T115112206583Z.json

REGRESSED  invoice extraction
SLOWER     capital of france  410ms -> 1180ms
FIXED      banana colour
```

`diff` exits 1 if anything regressed. You can pass two files to compare any pair.

Other flags: `--only <text>` runs matching cases, `--model` swaps the model without editing the file, `--json` prints the full result, `--no-save` skips writing history.

## Exit codes

`0` everything passed, `1` a case failed, `2` the suite file or arguments were wrong. So in CI it's just:

```yaml
- run: promptcheck run suite.yaml
```

## Caveats

- The `judge` check is a model grading a model. It's useful for fuzzy things like "doesn't make up a number", but it's noisy, especially with a 3B judge. Prefer a hard check where you can, and use a stronger `judge_model` if it matters.
- Temperature 0 helps but doesn't make outputs identical across runs or hardware. That's what `repeat` is for.
- Token counts only include the prompts under test, not judge calls.
- Only single-turn prompts for now. No multi-turn conversations or tool calls.
- Results are plain JSON files, not a database. Fine for one person, awkward for a team.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The tests run against a fake OpenAI-style server that lives in `tests/conftest.py`, so no model is needed.

## Layout

```
promptcheck/
  cli.py       arguments and exit codes
  suite.py     loading and validating the YAML
  checks.py    one function per check type
  runner.py    runs cases, handles repeats and concurrency
  client.py    the HTTP client
  history.py   saved runs and diffing
  report.py    terminal output
examples/
tests/
```

## Maybe later

- multi-turn cases
- a `--baseline` flag so CI can compare against a committed run
- cost estimates for hosted APIs

## License

MIT
