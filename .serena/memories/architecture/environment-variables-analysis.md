# ACRouter Environment Variables Analysis

## Summary
There are **environment variables that CANNOT be represented in appsettings.json** because they control:
1. **Path resolution** at startup (before config is loaded)
2. **Runtime mode selection** (which code paths to execute)
3. **System-level integration** (file paths, registry access)
4. **External process environment** (passed to child processes)

---

## Category 1: ACRouter-Specific Environment Variables
These are ACRouter-specific settings that CAN be moved to appsettings BUT currently use environment variables:

| Env Var | Source File | Purpose | Can Move to appsettings? |
|---------|-------------|---------|--------------------------|
| `CCR_CONFIG_FILE` | cli.ts:25 | Override config.json location | ✅ Yes (but breaks CLI compatibility) |
| `CCR_CONFIG_DB_FILE` | cli.ts:27 | Override database file location | ✅ Yes (but breaks CLI compatibility) |
| `CCR_CODEX_CLI_MIDDLEWARE_LOG` | codex-cli-middleware-runtime.ts:19 | Log file for Codex CLI middleware | ✅ Yes |
| `CCR_NODE_BIN` | profile-launch-service.ts:757 | Override Node.js binary path | ✅ Yes |
| `CCR_CONFIG_DIR` | codex-cli-middleware-runtime.ts:23 | Override config directory | ❌ No (read before app initialization) |
| `CCR_CLAUDE_CODE_BOT_WORKER` | codex-cli-middleware-runtime.ts:42 | Runtime mode flag | ❌ No (runtime feature flag) |
| `CCR_CLAUDE_CODE_WRAPPER` | codex-cli-middleware-runtime.ts:46 | Runtime mode flag | ❌ No (runtime feature flag) |
| `CCR_CLAUDE_APP_DESIGN_CDP` | claude-app-cdp.ts:49 | Chrome DevTools Protocol endpoint | ✅ Yes |
| `CCR_CLAUDE_APP_CDP_PORT` | claude-app-cdp.ts:60 | CDP port override | ✅ Yes |
| `CCR_MODEL_CATALOG_PATH` | provider-model-catalog.ts:95 | Model catalog JSON file path | ✅ Yes (or auto-discover) |
| `CCR_MODELS_JSON_PATH` | provider-model-catalog.ts:96 | Models JSON file path | ✅ Yes (or auto-discover) |
| `CCR_BOT_GATEWAY_SDK_MODULE` | bot-gateway-qr-login-service.ts:245 | SDK module override | ✅ Yes |
| `CCR_UPSTREAM_PROXY_URL` | gateway/service.ts:2268 | Upstream proxy for gateway child process | ❌ No (computed at runtime from snapshot) |
| `CCR_UNDICI_MODULE` | gateway/service.ts:2273 | Undici HTTP client module path | ❌ No (resolved at runtime) |
| `CCR_CLAUDE_APP_SOCKET` | (implied) | Claude app socket path | ✅ Yes |
| `CCR_GATEWAY_RUNTIME_ID` | gateway/service.ts:2260 | Gateway process runtime ID | ❌ No (generated at runtime) |

---

## Category 2: System-Level Environment Variables
These CANNOT be moved to appsettings because they resolve file paths before the app can load configuration:

| Env Var | Source File | Purpose | Why Cannot Move |
|---------|-------------|---------|-----------------|
| `APPDATA` | constants.ts, multiple | Windows application data directory | OS-level, needed at startup |
| `LOCALAPPDATA` | constants.ts, multiple | Windows local app data directory | OS-level, needed at startup |
| `USERPROFILE` | constants.ts, windows-app-discovery.ts | Windows user home directory | OS-level, needed at startup |
| `HOME` | profile-launch-core.ts, constants.ts | Unix/macOS home directory | OS-level, needed at startup |
| `ProgramFiles` | windows-app-discovery.ts | Windows Program Files directory | OS-level, app discovery |
| `PROGRAMFILES` | windows-app-discovery.ts | Windows Program Files directory (variant) | OS-level, app discovery |
| `ProgramW6432` | windows-app-discovery.ts | Windows 64-bit Program Files | OS-level, app discovery |
| `ProgramFiles(x86)` | windows-app-discovery.ts | Windows 32-bit Program Files | OS-level, app discovery |
| `SystemRoot` | windows-system.ts | Windows system root directory | OS-level, system integration |
| `windir` | windows-system.ts | Windows directory (variant) | OS-level, system integration |
| `SHELL` | profile-launch-service.ts, profile-launch-core.ts | Unix/macOS shell executable | OS-level, shell detection |
| `ComSpec` | profile-launch-core.ts | Windows command interpreter | OS-level, Windows integration |
| `COMSPEC` | profile-launch-core.ts | Windows command interpreter (variant) | OS-level, Windows integration |
| `PATH` | profile-launch-service.ts | System executable search path | OS-level, process spawning |

---

## Category 3: Child Process Environment Variables (Passed to Subprocesses)
These are set by ACRouter when spawning child processes and CANNOT be in appsettings because appsettings.json is per-application:

| Env Var | Set In | Purpose | Target Process | Why Cannot Move |
|---------|--------|---------|-----------------|-----------------|
| `HTTP_PROXY` | gateway/service.ts:2269 | HTTP proxy for downstream gateway | Gateway child process | Per-process environment |
| `HTTPS_PROXY` | gateway/service.ts:2270 | HTTPS proxy for downstream gateway | Gateway child process | Per-process environment |
| `ALL_PROXY` | gateway/service.ts:2271 | All protocol proxy | Gateway child process | Per-process environment |
| `NO_PROXY` | gateway/service.ts:2272 | Proxy bypass list | Gateway child process | Per-process environment |
| `NODE_OPTIONS` | gateway/service.ts:2275 | Node.js runtime options | Gateway child process | Per-process environment |
| `ELECTRON_RUN_AS_NODE` | gateway/service.ts:2263 | Run Electron app as Node process | Gateway child process | Per-process environment |
| `AUTH_ENABLED` | gateway/service.ts:2257 | Auth feature flag | Gateway child process | Per-process feature flag |
| `AUTH_MODE` | gateway/service.ts:2258 | Authentication mode | Gateway child process | Per-process configuration |
| `AUTH_REQUIRED` | gateway/service.ts:2259 | Auth requirement | Gateway child process | Per-process configuration |
| `AUTH_STATIC_API_KEY_BEARER_ONLY` | gateway/service.ts:2260 | Auth bearer-only mode | Gateway child process | Per-process configuration |
| `AUTH_STATIC_API_KEY_ENV` | gateway/service.ts:2261 | API key env var name | Gateway child process | Per-process environment |
| `AUTH_STATIC_API_KEY_HEADER` | gateway/service.ts:2262 | API key header name | Gateway child process | Per-process environment |
| `GATEWAY_CONFIG_PATH` | gateway/service.ts:2266 | Gateway config file path | Gateway child process | Per-process file reference |
| `HOST` | gateway/service.ts:2267 | Listen host for gateway | Gateway child process | Per-process configuration |
| `PORT` | gateway/service.ts:2268 | Listen port for gateway | Gateway child process | Per-process configuration |
| `CODEX_HOME` | codex-cli-middleware-runtime.ts, profile-service.ts | Codex home directory | Codex child process | Per-process home directory |
| `ZCODE_HOME` | codex-cli-middleware-runtime.ts, profile-service.ts | Z-Code home directory | Z-Code child process | Per-process home directory |
| `ZCODE_STORAGE_DIR` | codex-cli-middleware-runtime.ts:3860 | Z-Code storage directory | Z-Code child process | Per-process storage location |
| `CODEXL_HOME` | codex-cli-middleware-runtime.ts, profile-service.ts | Codex Language home directory | Codex child process | Per-process home directory |

---

## Category 4: Injected by ACRouter for Config Interpolation
These are only used when referenced in config files via `${VAR_NAME}` or `$VAR_NAME` syntax:

| Env Var | Source File | Purpose | Can Move |
|---------|-------------|---------|----------|
| Any env var | config.ts:2562-2568 | Config file interpolation | ✅ Yes (but breaks flexibility) |

---

## Environment Variables That CAN Be Represented in appsettings.json

These could theoretically be moved to appsettings if we updated the codebase:

1. **Paths:**
   - `CCR_CONFIG_FILE` → `paths.configFile`
   - `CCR_CONFIG_DB_FILE` → `paths.configDatabase`
   - `CCR_CODEX_CLI_MIDDLEWARE_LOG` → `logging.codexMiddlewarePath`
   - `CCR_NODE_BIN` → `runtime.nodeBinPath`

2. **Feature Flags:**
   - `CCR_CLAUDE_APP_DESIGN_CDP` → `features.claudeAppDesignCdp`
   - `CCR_CLAUDE_APP_CDP_PORT` → `ports.claudeAppCdp`

3. **Model Configuration:**
   - `CCR_MODEL_CATALOG_PATH` → `models.catalogPath`
   - `CCR_MODELS_JSON_PATH` → `models.jsonPath`

---

## Environment Variables That CANNOT Be Represented in appsettings.json

### 1. **Runtime Feature Flags** (determined at startup)
- `CCR_CLAUDE_CODE_BOT_WORKER` – Determines which code path to execute
- `CCR_CLAUDE_CODE_WRAPPER` – Runtime behavior flag

These control which code branches execute BEFORE config is loaded.

### 2. **Dynamic Child Process Environment** (computed at runtime)
- `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY` – Set from system proxy snapshot
- `CCR_UPSTREAM_PROXY_URL` – Derived from system proxy state
- `CCR_GATEWAY_RUNTIME_ID` – Generated UUID for this session
- `NODE_OPTIONS` – Constructed from multiple sources
- `AUTH_*` – Set based on gateway requirements

These are set programmatically when spawning subprocesses; they're not static.

### 3. **System-Level Variables** (OS-dependent, pre-app)
- `APPDATA`, `LOCALAPPDATA`, `USERPROFILE`, `HOME`, `SHELL`, etc.
- These are resolved by the OS BEFORE the app loads

### 4. **Path Resolution Variables** (read before config)
- `CCR_CONFIG_DIR` – Used to locate config.json before loading it

Chicken-and-egg problem: can't put in config if config doesn't exist yet.

---

## Summary Table

| Type | Count | Can Move? | Examples |
|------|-------|-----------|----------|
| ACRouter-specific settings | 7 | ✅ Mostly | `CCR_NODE_BIN`, `CCR_MODELS_JSON_PATH` |
| Runtime feature flags | 2 | ❌ No | `CCR_CLAUDE_CODE_BOT_WORKER`, `CCR_CLAUDE_CODE_WRAPPER` |
| System-level paths | 13 | ❌ No | `APPDATA`, `HOME`, `SHELL` |
| Child process env vars | 19 | ❌ No | `HTTP_PROXY`, `AUTH_*`, `HOST`, `PORT` |
| Config interpolation | ∞ | ✅ Always available | Any `${VAR}` in config |
| **Total** | **~41** | **~9 movable** | **~32 must stay as env vars** |

---

## Recommendation

**Keep environment variables for:**
1. System paths (APPDATA, HOME, SHELL, etc.) – OS-level
2. Runtime feature flags – code path selection
3. Child process configuration – per-process environment
4. Config file locations – bootstrap problem
5. Dynamic values – generated at runtime

**Could move to appsettings if needed:**
1. `CCR_NODE_BIN`
2. `CCR_CODEX_CLI_MIDDLEWARE_LOG`
3. `CCR_CLAUDE_APP_CDP_PORT`
4. `CCR_MODEL_CATALOG_PATH`
5. `CCR_MODELS_JSON_PATH`
6. `CCR_CLAUDE_APP_DESIGN_CDP`

But **CLI compatibility** requires `CCR_CONFIG_FILE` and `CCR_CONFIG_DB_FILE` to remain as environment variables.
