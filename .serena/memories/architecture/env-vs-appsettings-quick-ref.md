# Quick Reference: Environment Variables vs appsettings.json

## Answer to Your Question

**~32 environment variables CANNOT be represented in appsettings.json** because they:

1. **Control startup behavior** before config loads (e.g., `CCR_CONFIG_DIR`)
2. **Set runtime feature flags** that determine which code path executes (e.g., `CCR_CLAUDE_CODE_BOT_WORKER`)
3. **Are passed to child processes** as per-process environment (e.g., `HTTP_PROXY`, `AUTH_*`)
4. **Are OS-level system variables** needed at bootstrap (e.g., `APPDATA`, `HOME`, `SHELL`)
5. **Are dynamically computed** at runtime (e.g., `CCR_GATEWAY_RUNTIME_ID`, `NODE_OPTIONS`)

## The 41 Total Environment Variables Breakdown

### ✅ CAN Move to appsettings (7 vars):
- `CCR_NODE_BIN` – Node binary path
- `CCR_CODEX_CLI_MIDDLEWARE_LOG` – Log file path
- `CCR_CLAUDE_APP_CDP_PORT` – Port number
- `CCR_CLAUDE_APP_DESIGN_CDP` – Feature endpoint
- `CCR_MODEL_CATALOG_PATH` – Model catalog path
- `CCR_MODELS_JSON_PATH` – Models JSON path
- `CCR_BOT_GATEWAY_SDK_MODULE` – SDK module reference

### ❌ MUST Stay as Environment Variables (34 vars):

**Runtime Feature Flags (2):**
- `CCR_CLAUDE_CODE_BOT_WORKER`, `CCR_CLAUDE_CODE_WRAPPER` – Control code path selection

**System Paths (13):**
- `APPDATA`, `LOCALAPPDATA`, `USERPROFILE`, `HOME`, `SHELL`, `ComSpec`, `COMSPEC`, `SystemRoot`, `windir`, `ProgramFiles`, `PROGRAMFILES`, `ProgramW6432`, `ProgramFiles(x86)`

**Child Process Environment (19):**
- `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `NODE_OPTIONS`, `ELECTRON_RUN_AS_NODE`
- `AUTH_ENABLED`, `AUTH_MODE`, `AUTH_REQUIRED`, `AUTH_STATIC_API_KEY_*`
- `GATEWAY_CONFIG_PATH`, `HOST`, `PORT`
- `CODEX_HOME`, `ZCODE_HOME`, `ZCODE_STORAGE_DIR`, `CODEXL_HOME`
- `CCR_UPSTREAM_PROXY_URL`, `CCR_UNDICI_MODULE`, `CCR_GATEWAY_RUNTIME_ID`

**Bootstrap/CLI (2):**
- `CCR_CONFIG_FILE` – **CANNOT move** (breaks CLI; read before config loads)
- `CCR_CONFIG_DB_FILE` – **CANNOT move** (breaks CLI; read before config loads)

## Why These Cannot Move

| Category | Why | Example |
|----------|-----|---------|
| **Bootstrap vars** | Needed to find config.json → can't be in config.json | `CCR_CONFIG_FILE` |
| **Feature flags** | Control which code runs before config loads | `CCR_CLAUDE_CODE_BOT_WORKER` |
| **Child process env** | Each subprocess needs different environment | `HTTP_PROXY` passed to gateway process |
| **System paths** | Determined by OS before app runs | `APPDATA`, `HOME` |
| **Runtime computed** | Generated/derived at execution time | `CCR_GATEWAY_RUNTIME_ID`, `NODE_OPTIONS` |

## Practical Implication

✅ **appsettings.json** – Application configuration (features, endpoints, timeouts)  
❌ **appsettings.json** – Cannot hold: startup paths, feature flags, child process env, system variables

Environment variables will always be needed for proper functioning of ACRouter.
