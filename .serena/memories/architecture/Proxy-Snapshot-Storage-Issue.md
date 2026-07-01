# Proxy Snapshot Storage Architecture Issue

## Problem
The proxy snapshot is currently stored in `DATADIR` which resolves to Claude Code Router's application data directory:
- Windows: `%APPDATA%\Claude Code Router\`
- macOS/Linux: `~/.claude-code-router/`

**File:** `claude-code-router/src/server/proxy/system-proxy.ts` line 89
```typescript
const systemProxySnapshotFile = path.join(DATADIR, "system-proxy-snapshot.json");
```

## Issue
ACRouter is supposed to be **agent-agnostic** and work with any LLM provider (Claude, Codex, Gemini, etc.). However, storing the proxy snapshot in a "Claude Code Router" branded directory violates this principle and creates confusion about what the system actually does.

## Impact
1. **Architectural Clarity:** Users expect ACRouter to be provider-neutral, but the file paths suggest Claude-specific behavior
2. **Multi-Agent Support:** If multiple agents manage the same system proxy, they need a shared, neutral location
3. **Documentation:** PROXY_COEXISTENCE.md now explicitly references `%APPDATA%\Claude Code Router\` for the snapshot, reinforcing the brand confusion

## Solution Options

### Option 1: Create Shared ACRouter Directory (Recommended)
- **Location:** `~/.acrouter/` or `%APPDATA%\ACRouter\`
- **Contents:** `system-proxy-snapshot.json`
- **Benefit:** Clear separation of concerns, brand-neutral, discoverable
- **Change Required:** 
  1. Create new path constant in constants.ts: `ACROUTER_SNAPDIR`
  2. Update system-proxy.ts to use `ACROUTER_SNAPDIR` instead of `DATADIR`
  3. Update PROXY_COEXISTENCE.md documentation

### Option 2: Use System-Level Temp Directory
- **Location:** `%TEMP%\acrouter-proxy-snapshot.json` or `/tmp/acrouter-proxy-snapshot.json`
- **Benefit:** Doesn't clutter user directories
- **Drawback:** Survives only current session, not restarts

### Option 3: Standardized XDG Base Directory (Linux-focused)
- **Location:** `$XDG_CONFIG_HOME/acrouter/` or `~/.config/acrouter/`
- **Benefit:** Follows Linux standards
- **Drawback:** Not portable to Windows/macOS conventions

## Implementation ✅ COMPLETED

Created new `ACROUTER_SNAPDIR` constant that:
- **Windows:** `%APPDATA%\ACRouter\`
- **macOS/Linux:** `~/.acrouter/`

### Changes Made:

1. **claude-code-router/src/main/constants.ts**
   - Added `ACROUTER_SNAPDIR` constant
   - Added `SYSTEM_PROXY_SNAPSHOT_FILE` constant pointing to `ACROUTER_SNAPDIR`

2. **claude-code-router/src/server/proxy/system-proxy.ts**
   - Updated import to include `SYSTEM_PROXY_SNAPSHOT_FILE`
   - Changed `systemProxySnapshotFile` to use the new constant

3. **docs/PROXY_COEXISTENCE.md**
   - Updated database storage table to reference `%APPDATA%\ACRouter\` (Windows) and `~/.acrouter/` (macOS/Linux)
   - Changed description to "agent-neutral directory"
   - Maintains clarity about separate cc-switch database

### Result
✅ Build successful
✅ Proxy snapshot now stored in brand-neutral location
✅ Architectural clarity: ACRouter is truly agent-agnostic
✅ Documentation updated to reflect new paths
