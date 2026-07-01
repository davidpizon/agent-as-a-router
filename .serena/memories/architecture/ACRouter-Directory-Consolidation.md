# ACRouter Directory Consolidation - Implementation Complete

## Summary
All SQLite databases and application data have been moved from the Claude Code Router branded directory to a unified, agent-neutral ACRouter directory structure.

## Changes Made

### 1. Updated Constants (claude-code-router/src/main/constants.ts)

**New Primary Directory:**
```typescript
export const ACROUTER_DIR = process.platform === "win32"
  ? path.join(appPath("appData"), "ACRouter")
  : path.join(os.homedir(), ".acrouter");
```

**All databases and data now stored under ACROUTER_DIR:**
- `APP_CONFIG_DB_FILE` → `ACROUTER_DIR/config.sqlite`
- `API_KEYS_DB_FILE` → `ACROUTER_DIR/api-keys.sqlite`
- `REQUEST_LOGS_DB_FILE` → `ACROUTER_DIR/request-logs.sqlite`
- `USAGE_DB_FILE` → `ACROUTER_DIR/usage.sqlite`
- `SYSTEM_PROXY_SNAPSHOT_FILE` → `ACROUTER_DIR/system-proxy-snapshot.json`
- `GATEWAY_CONFIG_FILE` → `ACROUTER_DIR/gateway.config.json`
- `CERTDIR` → `ACROUTER_DIR/certs`
- `PROVIDER_ICON_CACHE_DIR` → `ACROUTER_DIR/provider-icons`
- `RAW_TRACE_SPOOL_DIR` → `ACROUTER_DIR/raw-trace-spool`
- `DATADIR` → `ACROUTER_DIR/data`

### 2. Storage Directory Mapping

**Windows:**
```
%APPDATA%\ACRouter\
├── config.sqlite
├── api-keys.sqlite
├── request-logs.sqlite
├── usage.sqlite
├── system-proxy-snapshot.json
├── gateway.config.json
├── certs/
├── provider-icons/
├── raw-trace-spool/
└── data/
```

**macOS/Linux:**
```
~/.acrouter/
├── config.sqlite
├── api-keys.sqlite
├── request-logs.sqlite
├── usage.sqlite
├── system-proxy-snapshot.json
├── gateway.config.json
├── certs/
├── provider-icons/
├── raw-trace-spool/
└── data/
```

### 3. Documentation Updates

- Updated PROXY_COEXISTENCE.md with complete storage structure
- Clearly separated ACRouter databases from cc-switch databases
- Documented all files and directories within the unified ACRouter structure

## Architecture Benefits

✅ **Agent-Agnostic** – No "Claude Code Router" branding in file paths
✅ **Unified Structure** – All ACRouter data in single, clear directory
✅ **Multi-Agent Ready** – Multiple LLM agents can safely coexist using shared ACRouter directory
✅ **Clear Separation** – cc-switch (`~/.cc-switch/`) remains independent
✅ **Backward Compatible** – LEGACY_CONFIGDIR preserved for migration path
✅ **Build Verified** – All changes compile successfully

## Migration Considerations

- Existing installations in `%APPDATA%\Claude Code Router\` and `~/.claude-code-router/` will need migration script
- Suggest data migration on first launch to new directory structure
- Keep LEGACY_CONFIGDIR constant for identifying old installations
