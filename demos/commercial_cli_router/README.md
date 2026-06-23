# Commercial CLI Router MVP

This MVP routes a user prompt into one of three mature coding-agent products:
Codex, Claude Code, or opencode. It is a wrapper around local command-line
tools, so users keep their normal product login, billing, workspace trust, and
permission settings.

Dry-run the routing decision:

```bash
python demos/commercial_cli_router/router_mvp.py \
  --prompt "Patch this repository so pytest passes" \
  --dry-run
```

Force a backend:

```bash
python demos/commercial_cli_router/router_mvp.py \
  --tool codex \
  --workdir /path/to/project \
  --prompt "Run the tests and fix the failing parser case"
```

The default templates are in `tools.example.json`:

- `codex`: `codex exec --sandbox workspace-write --cd {workdir} <prompt>`
- `claude-code`: `claude --print --permission-mode acceptEdits <prompt>`
- `opencode`: `opencode run <prompt>`

Edit those templates if your installed CLI uses a different non-interactive
form. `router_mvp.py --dry-run` writes the exact rendered command to
`demos/commercial_cli_router/runs/`.

## ccswitch Or Other Wrappers

Each tool supports an optional `command_prefix` list and a `command_prefix_env`.
This lets you wrap the selected product CLI without changing router code:

```bash
ACROUTER_CODEX_PREFIX="ccswitch" \
python demos/commercial_cli_router/router_mvp.py \
  --tool codex \
  --prompt "Patch this repository so pytest passes" \
  --dry-run
```

The rendered command becomes `ccswitch codex exec ... <prompt>`. If your local
wrapper uses a different syntax, either set a longer prefix such as
`ACROUTER_CODEX_PREFIX="ccswitch run --"` or copy
`tools.ccswitch.example.json` and edit `command_prefix` directly.

## Local npm Wrapper

The `npm/` folder is a ready-to-link local package. It is private by default so
that publishing requires an intentional maintainer step.

```bash
cd demos/commercial_cli_router/npm
npm link

acrouter-cli-router --prompt "Review this repo for failing tests" --dry-run
```

To publish a real public npm package later, choose a package name, remove
`"private": true`, log in with `npm login`, and run `npm publish --access public`.
Codex and Claude Code plugin marketplaces require maintainer account approval
and product-specific packaging, so this repository ships the product-agnostic
CLI integration first.
