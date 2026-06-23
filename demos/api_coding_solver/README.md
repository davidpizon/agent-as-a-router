# API Coding Solver Demo

This demo routes one programming task through one or more OpenAI-compatible API
backends. The default config targets OpenRouter, but the same schema works for
any provider that implements `/chat/completions`.

No token is stored in this repository. Put credentials in your shell
environment before a live run:

```bash
export OPENROUTER_API_KEY="<set-this-in-your-shell>"
```

Dry-run the request plan without calling an API:

```bash
python demos/api_coding_solver/solve.py \
  --config demos/api_coding_solver/models.example.json \
  --problem-file demos/api_coding_solver/problems/two_sum.txt \
  --dry-run
```

Run live against the configured model list:

```bash
python demos/api_coding_solver/solve.py \
  --config demos/api_coding_solver/models.example.json \
  --problem-file demos/api_coding_solver/problems/two_sum.txt
```

The script tries candidates in order. For each response it extracts the largest
Python fenced code block into `solution.py`, then runs the configured verifier.
By default that verifier is `python -m py_compile {solution}`. Replace it with a
task-specific test command when you want stronger checks:

```bash
python demos/api_coding_solver/solve.py \
  --problem-file path/to/problem.txt \
  --verify-command "python path/to/tests.py"
```

To add another backend, append an item to `apis`:

```json
{
  "name": "my-compatible-api",
  "base_url": "https://example.com/v1",
  "api_key_env": "MY_PROVIDER_TOKEN",
  "models": [{"name": "provider/model-name"}]
}
```

Run outputs are written under `demos/api_coding_solver/runs/`, which is ignored
by git.
