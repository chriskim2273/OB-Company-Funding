# harness

Asks each tool about every company and saves the answers. No grading logic lives here.

- `run.py` — Command-line runner: `run`, `grade`, `selftest` and `list-tools`.
- `runner.py` — Calls each setup for every company, paces requests, and saves the answers. A rerun with the same `--out` skips companies that already have an answer and retries the ones that failed.
- `registry.py` — Reads `tools/<tool>.yaml` and builds each setup's adapter from `adapters/<tool>.py`.
- `tool_base.py` — The `Adapter` base class every adapter extends.
- `adapters/` — The request and response code for each tool, one file per tool.
- `question.py` — The question every research setup is asked, the answer schema, and the helpers that read research answers.
- `models.py` — `Company` and `Answer`, the shapes passed between the runner and the adapters.
- `http_client.py` — Sends HTTP requests with retries and removes API keys before anything is saved.
- `llm.py` — OpenAI extraction for setups whose tool returns search results.
- `config.yaml` — Fields being measured (`latest_stage`, `amount`, `announced_on`) and board groups.

## What a run writes

```text
runs/<run>/
├── <setup>.jsonl        one answer per company: domain, latest_stage, amount, announced_on, status, latency, cost
└── raw/<setup>/<domain>.json   the tool's response, with API keys removed
```

`grade --predictions runs/<run>/<setup>.jsonl` scores one setup's answers.
