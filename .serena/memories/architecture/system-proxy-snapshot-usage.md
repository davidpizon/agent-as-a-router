# system-proxy-snapshot.json Usage Analysis

## Status: ✅ **ACTIVELY USED**

The `system-proxy-snapshot.json` file is **actively and critically** used by ACRouter's proxy system for capturing and restoring system proxy state.

## Usage Flow

### 1. **Enable Proxy** (captures snapshot)
```typescript
// claude-code-router/src/server/proxy/system-proxy.ts, line 119
async enable(endpoint: string) {
  // ... capture current system proxy state
  const snapshot = process.platform === "win32"
    ? await captureWindowsSystemProxySnapshot(managedEndpoint)
    : await captureMacSystemProxySnapshot(managedEndpoint);
  
  // ... store snapshot to disk for recovery
  persistSnapshot(snapshot);  // → writes to system-proxy-snapshot.json
  
  // ... apply ACRouter's proxy configuration
  await applySystemProxy(snapshot, managedEndpoint);
}
```

**Purpose:** Before ACRouter takes over system proxy settings, it saves a snapshot of the current configuration for later restoration.

### 2. **Restore Proxy** (reads and uses snapshot)
```typescript
// claude-code-router/src/server/proxy/system-proxy.ts, line 150
async restore() {
  const activeSnapshot = this.snapshot;
  const snapshot = activeSnapshot ?? readPersistedSnapshot();  // → reads from system-proxy-snapshot.json
  
  if (snapshot) {
    // ... restore original system proxy settings from snapshot
    await restoreSystemProxy(snapshot);
    removePersistedSnapshot();  // → deletes file after successful restore
  }
}
```

**Purpose:** When ACRouter shuts down or is disabled, it uses the snapshot to restore the exact original system proxy configuration.

### 3. **Conflict Detection** (checks if current proxy matches managed endpoint)
```typescript
// claude-code-router/src/server/proxy/system-proxy.ts, line 208
private async restorePersistedSnapshotIfCurrentProxyIsManaged(): Promise<void> {
  const snapshot = readPersistedSnapshot();  // → reads from system-proxy-snapshot.json
  if (snapshot) {
    // ... check if system proxy points to ACRouter's endpoint
    // ... if yes, restore the snapshot (handle cleanup scenarios)
  }
}
```

**Purpose:** Detects if a previous ACRouter instance crashed or was forcefully terminated, and automatically restores the saved proxy state.

## File Functions

| Function | Purpose | Called From |
|----------|---------|-------------|
| `persistSnapshot(snapshot)` | Write snapshot to disk (JSON format, pretty-printed) | `enable()` method |
| `readPersistedSnapshot()` | Read snapshot from disk with validation | `restore()` and `restorePersistedSnapshotIfCurrentProxyIsManaged()` |
| `removePersistedSnapshot()` | Delete snapshot file after successful restore | `restore()` method |
| `isSystemProxySnapshot(value)` | Validate snapshot structure (version check, platform check) | `readPersistedSnapshot()` validation |

## Snapshot Data Structure

### Windows
```json
{
  "version": 1,
  "platform": "win32",
  "createdAt": "2024-01-15T10:30:00.000Z",
  "managedEndpoint": "127.0.0.1:5002",
  "settings": {
    "proxyServer": "http://corporate-proxy.com:8080",
    "proxyOverride": "*.internal.local",
    "proxyEnable": 1,
    "autoDetect": 0,
    "hadProxyServer": true,
    "hadProxyOverride": true,
    "hadProxyEnable": true,
    "hadAutoDetect": false,
    "winHttp": { ... }
  }
}
```

### macOS
```json
{
  "version": 1,
  "platform": "darwin",
  "createdAt": "2024-01-15T10:30:00.000Z",
  "managedEndpoint": "127.0.0.1:5002",
  "services": [
    {
      "name": "Wi-Fi",
      "web": { "enabled": true, "server": "...", "port": 8080, "authenticated": false },
      "secureWeb": { ... },
      "socks": { ... }
    },
    ...
  ]
}
```

## Critical Scenarios Where Snapshot Is Used

1. **Normal Shutdown:** Restore → Read Snapshot → Delete File
2. **App Crash Recovery:** On restart, detects managed endpoint in system proxy → Restores from snapshot
3. **Multi-Session Support:** If multiple ACRouter instances run, snapshot ensures clean state handoff
4. **Proxy Chaining:** Upstream proxy info extracted from snapshot when ACRouter enables
5. **Enable Error Recovery:** If ACRouter enable fails, snapshot is used to rollback system proxy state

## File Location
- **Windows:** `%APPDATA%\ACRouter\system-proxy-snapshot.json`
- **macOS/Linux:** `~/.acrouter/system-proxy-snapshot.json`

## Lifecycle

1. **Created:** When `SystemProxyManager.enable()` is called
2. **Persisted:** Written to disk immediately for crash recovery
3. **Read:** Used during `restore()` or conflict detection
4. **Deleted:** Removed after successful proxy restoration (or platform mismatch detected)

## Conclusion

✅ **The file is essential** – Without it, ACRouter cannot safely restore system proxy settings after shutdown or crash.
✅ **Must be preserved** – Should not be removed or moved to a different location without corresponding code changes.
✅ **Documented location** – Current location in `~/.acrouter/` is correct and agent-neutral.
