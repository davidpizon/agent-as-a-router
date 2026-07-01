# ACRouter Configuration Strategy

## ConfigurationHierarchy

ACRouter uses a three-tier configuration strategy:

### Tier 1: Bootstrap Environment Variables (Non-Negotiable)
These MUST be environment variables because they're needed before any configuration system initializes:

```
CCR_CONFIG_FILE          → Points to config.json location
CCR_CONFIG_DB_FILE       → Points to SQLite database
CCR_CONFIG_DIR           → Directory search for config files
```

**Why:** Chicken-and-egg problem – you can't read from a config file to find the config file.

### Tier 2: Feature Flags & Runtime Behavior (Should Be Environment Variables)
These determine code paths and process modes:

```
CCR_CLAUDE_CODE_BOT_WORKER    → Execute as bot worker
CCR_CLAUDE_CODE_WRAPPER       → Run wrapper mode
CCR_CLAUDE_APP_DESIGN_CDP     → CDP endpoint
CCR_CLAUDE_APP_CDP_PORT       → CDP port
```

**Why:** Needed at startup to select which code to execute before config system initializes.

### Tier 3: Application Configuration (Should Be appsettings.json)
These are stable settings that apply to the running instance:

```json
{
  "proxy": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 5002,
    "systemProxy": true
  },
  "gateway": {
    "port": 3000,
    "host": "127.0.0.1"
  },
  "models": {
    "default": "claude-3-opus-20250219"
  }
}
```

### Tier 4: Dynamic Runtime Environment (Always Environment Variables)
These are computed/derived at runtime and passed to child processes:

```
HTTP_PROXY, HTTPS_PROXY, ALL_PROXY    → From system proxy snapshot
CCR_UPSTREAM_PROXY_URL                → Derived from proxy snapshot
CCR_GATEWAY_RUNTIME_ID                → Generated UUID
NODE_OPTIONS                          → Constructed at runtime
AUTH_*, CODEX_HOME, etc.              → Set when spawning processes
```

---

## Configuration Philosophy

**ACRouter Configuration = appsettings.json + Environment Variables**

Neither alone is sufficient:
- **appsettings.json alone** → Cannot bootstrap, cannot set per-process env, cannot select runtime modes
- **Environment variables alone** → Unwieldy, hard to manage, doesn't scale to dozens of settings

## Best Practice: What Goes Where

### Use appsettings.json for:
✅ Application state (enable/disable features)  
✅ Network configuration (hosts, ports, timeouts)  
✅ Provider settings (API endpoints, model selections)  
✅ Logging configuration (levels, targets)  
✅ Feature toggles (non-critical runtime behavior)  

### Use Environment Variables for:
✅ File paths (config, database, logs) – needed at bootstrap  
✅ Feature flags (code path selection) – needed before config loads  
✅ Child process environment – per-process isolation  
✅ System integration – proxy, auth, SDKs  
✅ Dynamic/generated values – runtime IDs, computed proxies  
✅ Secrets – never in config files  

---

## Environment Variable Categories in ACRouter

### Category A: Path Bootstrap (READ FIRST)
```
CCR_CONFIG_FILE         (→ find config.json)
CCR_CONFIG_DB_FILE      (→ find SQLite DB)
CCR_CONFIG_DIR          (→ search for configs)
```
**These block everything else.**

### Category B: Mode Selection (READ SECOND)
```
CCR_CLAUDE_CODE_BOT_WORKER    (→ select code path)
CCR_CLAUDE_CODE_WRAPPER       (→ select wrapper)
NODE_ENV                      (→ dev/prod mode)
```
**These determine which features/code execute.**

### Category C: Configuration Override (READ THIRD)
```
CCR_NODE_BIN            → Override Node binary
CCR_MODEL_CATALOG_PATH  → Model data location
CCR_MODELS_JSON_PATH    → Models JSON location
```
**These override config file settings.**

### Category D: System Integration (RUNTIME)
```
APPDATA, HOME, SHELL           → OS-level paths
SystemRoot, windir             → Windows system
ProgramFiles, PROGRAMFILES     → App discovery
```
**These are read as needed.**

### Category E: Child Process Environment (SPAWN TIME)
```
HTTP_PROXY, HTTPS_PROXY        → Gateway process
CODEX_HOME, ZCODE_HOME         → Codex process
AUTH_*, NODE_OPTIONS           → Process-specific
```
**These are set when spawning subprocess.**

---

## Implementation Status

### Currently Using:
- ✅ appsettings.json for main application config
- ✅ Environment variables for bootstrap, feature flags, child process env
- ✅ System proxy snapshot for upstream proxy info
- ✅ Config file interpolation for `${VAR}` substitution

### Not Yet Implemented (Could Be):
- ❓ Environment variable substitution in appsettings.json
- ❓ Profile-based appsettings (dev/staging/prod)
- ❓ Hierarchical config override (env → config → defaults)

---

## Answer: Settings NOT in appsettings.json

**34 settings CANNOT be in appsettings.json:**

| Why | Count | Examples |
|-----|-------|----------|
| Bootstrap/CLI requirements | 2 | `CCR_CONFIG_FILE`, `CCR_CONFIG_DB_FILE` |
| Feature flags (code path selection) | 2 | `CCR_CLAUDE_CODE_BOT_WORKER`, `CCR_CLAUDE_CODE_WRAPPER` |
| System-level OS variables | 13 | `APPDATA`, `HOME`, `SHELL`, `SystemRoot`, etc. |
| Child process environment | 15 | `HTTP_PROXY`, `AUTH_*`, `CODEX_HOME`, `NODE_OPTIONS`, etc. |
| Runtime computed values | 2 | `CCR_GATEWAY_RUNTIME_ID`, `NODE_OPTIONS` (computed) |

**7 settings COULD theoretically move to appsettings:**
- `CCR_NODE_BIN`, `CCR_CODEX_CLI_MIDDLEWARE_LOG`, `CCR_CLAUDE_APP_CDP_PORT`, `CCR_CLAUDE_APP_DESIGN_CDP`, `CCR_MODEL_CATALOG_PATH`, `CCR_MODELS_JSON_PATH`, `CCR_BOT_GATEWAY_SDK_MODULE`

But **CLI compatibility** requires `CCR_CONFIG_FILE` and `CCR_CONFIG_DB_FILE` to remain as environment variables.
