# SQLite Database Usage Map

## Overview
The agent-as-a-router repository uses SQLite extensively across multiple applications for persistent data storage. There are **7 distinct SQLite databases** managed by different components.

---

## 1. **cc-switch** (Tauri Rust Application)

### Primary Database: `cc-switch.db`
- **Location:** `~/.cc-switch/cc-switch.db` (or `%APPDATA%\.cc-switch\` on Windows with legacy fallback)
- **Schema Version:** 11 (defined in `cc-switch/src-tauri/src/database/schema.rs`)
- **Purpose:** Core application state, provider configuration, proxy settings, request logs, and health tracking

### Tables in `cc-switch.db`:

| Table | Purpose |
|-------|---------|
| **providers** | Provider configurations (Claude, Codex, Gemini, etc.) with settings, metadata, failover state |
| **provider_endpoints** | URLs/endpoints for each provider |
| **mcp_servers** | Model Context Protocol server configurations with per-app enablement |
| **prompts** | System prompts and instruction sets per app type |
| **skills** | Installed skills/tools with GitHub repo info and per-app enablement |
| **skill_repos** | GitHub repositories tracked for skill updates |
| **settings** | Generic key-value configuration store |
| **proxy_config** | Proxy settings per app (claude, codex, gemini) with timeouts, circuit breaker, cost multipliers |
| **provider_health** | Health metrics for each provider (consecutive failures, last success/failure, error tracking) |
| **proxy_request_logs** | Complete request logging with token counts, costs, latency, status codes |
| **proxy_live_backup** | Live backup of system proxy state before takeover (implied from code references) |

### Key Files:
- `cc-switch/src-tauri/src/database/mod.rs` – Main Database struct and initialization
- `cc-switch/src-tauri/src/database/schema.rs` – Table definitions and schema migrations (2595 lines)
- `cc-switch/src-tauri/src/database/backup.rs` – Export/import and backup support
- `cc-switch/src-tauri/src/config.rs` – Determines config directory location
- `cc-switch/src-tauri/src/database/dao/` – Data access objects (providers, proxy, MCP, prompts, settings, skills)

---

## 2. **Claude Code Router** (TypeScript/Electron Application)

### Database 1: `config.sqlite`
- **Location:** 
  - **Windows:** `%APPDATA%\ACRouter\config.sqlite`
  - **macOS/Linux:** `~/.acrouter/config.sqlite`
- **Purpose:** Application configuration and state persistence
- **File Location Code:** `APP_CONFIG_DB_FILE` in `claude-code-router/src/main/constants.ts`

### Database 2: `api-keys.sqlite`
- **Location:** 
  - **Windows:** `%APPDATA%\ACRouter\api-keys.sqlite`
  - **macOS/Linux:** `~/.acrouter/api-keys.sqlite`
- **Purpose:** Encrypted API key storage with optional rotation/expiration
- **File Location Code:** `API_KEYS_DB_FILE` in `claude-code-router/src/main/constants.ts`
- **Tables:**
  - `api_keys` – Stores encrypted keys with metadata (id, name, encryption type, created_at, expires_at, limits_json)

### Database 3: `request-logs.sqlite`
- **Location:** 
  - **Windows:** `%APPDATA%\ACRouter\request-logs.sqlite`
  - **macOS/Linux:** `~/.acrouter/request-logs.sqlite`
- **Purpose:** Request logging for audit trail and analytics
- **File Location Code:** `REQUEST_LOGS_DB_FILE` in `claude-code-router/src/main/constants.ts`

### Database 4: `usage.sqlite`
- **Location:** 
  - **Windows:** `%APPDATA%\ACRouter\usage.sqlite`
  - **macOS/Linux:** `~/.acrouter/usage.sqlite`
- **Purpose:** Usage statistics and tracking
- **File Location Code:** `USAGE_DB_FILE` in `claude-code-router/src/main/constants.ts`

### Key Files:
- `claude-code-router/src/main/constants.ts` – All database file paths defined here
- `claude-code-router/src/main/api-key-store.ts` – API key database initialization and encryption
- `claude-code-router/src/main/app-config-store.ts` – Application config database handling
- `claude-code-router/src/main/sqlite-native.ts` – Better-sqlite wrapper for performance

---

## Path Resolution

### Windows:
```
ACRouter Config:  %APPDATA%\ACRouter\config.sqlite
API Keys:         %APPDATA%\ACRouter\api-keys.sqlite
Request Logs:     %APPDATA%\ACRouter\request-logs.sqlite
Usage DB:         %APPDATA%\ACRouter\usage.sqlite
Proxy Snapshot:   %APPDATA%\ACRouter\system-proxy-snapshot.json
cc-switch:        %APPDATA%\.cc-switch\cc-switch.db
```

### macOS/Linux:
```
ACRouter Config:  ~/.acrouter/config.sqlite
API Keys:         ~/.acrouter/api-keys.sqlite
Request Logs:     ~/.acrouter/request-logs.sqlite
Usage DB:         ~/.acrouter/usage.sqlite
Proxy Snapshot:   ~/.acrouter/system-proxy-snapshot.json
cc-switch:        ~/.cc-switch/cc-switch.db
```

### DATADIR Variable:
- **Definition:** `path.join(ACROUTER_DIR, "data")`
- **Resolves to:**
  - **Windows:** `%APPDATA%\ACRouter\data\`
  - **macOS/Linux:** `~/.acrouter/data/`

---

## Additional Storage (Non-SQL)

### Proxy Snapshot (JSON):
- **Location:** `DATADIR/system-proxy-snapshot.json`
- **Managed by:** `claude-code-router/src/server/proxy/system-proxy.ts`
- **Purpose:** Backs up current system proxy configuration before takeover

### Certificate Store:
- **Location:** `DATADIR/certs/` (ca.pem, ca.cer, key.pem)

### Provider Icon Cache:
- **Location:** `DATADIR/provider-icons/`

### Raw Trace Spool:
- **Location:** `DATADIR/raw-trace-spool/`

### Configuration Files (JSON):
- **config.json:** Main application configuration
- **gateway.config.json:** Gateway/proxy configuration

---

## Backup & Migration

### cc-switch:
- **Pre-Migration Backup:** Automatic backup before schema changes
- **Migration Support:** `cc-switch/src-tauri/src/database/migration.rs` handles JSON → SQLite data migration
- **Auto-Vacuum:** Configured as `PRAGMA auto_vacuum = INCREMENTAL` for new databases

### Claude Code Router:
- **API Key Encryption:** Keys stored with configurable encryption (plaintext fallback for testing)
- **File Permissions:** Secured to `0o600` (read/write owner only) on Unix; equivalent on Windows

---

## Summary Table

| Database | Location | Purpose | Records |
|----------|----------|---------|---------|
| `cc-switch.db` | `~/.cc-switch/` | Provider config, proxy state, health, request logs | 10+ tables |
| `config.sqlite` | `%APPDATA%\ACRouter\` (Windows) / `~/.acrouter/` (Unix) | App configuration | 1 (variable schema) |
| `api-keys.sqlite` | `%APPDATA%\ACRouter\` (Windows) / `~/.acrouter/` (Unix) | Encrypted API keys | api_keys table |
| `request-logs.sqlite` | `%APPDATA%\ACRouter\` (Windows) / `~/.acrouter/` (Unix) | Request audit trail | request logs |
| `usage.sqlite` | `%APPDATA%\ACRouter\` (Windows) / `~/.acrouter/` (Unix) | Usage statistics | usage data |

---

## Integration Points

1. **Proxy Coexistence:** `system-proxy-snapshot.json` + `proxy_config` table in `cc-switch.db` = seamless chaining
2. **Provider Health:** `provider_health` table tracks failover eligibility
3. **Cost Tracking:** `proxy_request_logs` with `cost_multiplier` and token counts
4. **API Security:** Encrypted storage in `api-keys.sqlite` with per-app limits
5. **Configuration Management:** JSON config files + SQLite state provides flexibility + persistence
