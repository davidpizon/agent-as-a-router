# ACRouter Proxy Conflict Handling and Existing Proxy Interaction

## Short Answer

**No, ACRouter proxy settings will NOT interfere with your existing proxy.** ACRouter uses an intelligent conflict detection and backup/restore system:

1. ✅ **Detects existing system proxies** before making changes
2. ✅ **Backs up** your previous proxy settings automatically
3. ✅ **Seamlessly restores** them when ACRouter is disabled
4. ✅ **Chains proxies** (ACRouter → your upstream proxy) if you already use one
5. ✅ **Detects self-referential loops** (loopback detection) to prevent conflicts

---

## How ACRouter Handles Existing Proxies

### 1. **Pre-Takeover Snapshot (Backup)**

When ACRouter enables its proxy, it first captures the current system proxy state:

```rust
// System Proxy Snapshot captures:
- Current HTTP proxy (if any)
- Current HTTPS proxy (if any)
- SOCKS proxy (if any)
- All proxy bypass rules (NO_PROXY)
- Platform-specific settings (Windows Registry, macOS networksetup, Linux env vars)
```

**Example on Windows:**
```registry
BEFORE ACRouter:
  ProxyServer = http=10.0.0.1:8080;https=10.0.0.1:8080
  ProxyOverride = <local>
  
AFTER ACRouter backup:
  BACKED_UP state stored in database
  
NEW state:
  ProxyServer = http=127.0.0.1:5002;https=127.0.0.1:5002
  (ACRouter's local proxy)
```

### 2. **Conflict Detection**

Before modifying system settings, ACRouter checks:

#### **Loopback Detection:**
```rust
fn system_proxy_points_to_loopback() -> bool {
    // Check if HTTP_PROXY, HTTPS_PROXY, ALL_PROXY point to loopback
    // (127.0.0.1, ::1, localhost, etc.)
    
    // If they do AND point to an ACRouter-known port, it's a self-reference
    // → Skip proxy setup (already configured)
}
```

#### **Placeholder Detection:**
```rust
// Check if Live config has been taken over by proxy
// If backup contains proxy configuration (not user's original config):
//   → Don't restore it (it would lock user into proxy mode)
//   → Fall back to SSOT (Single Source of Truth) rebuild
```

#### **Environment Variable Detection:**
```rust
const KEYS: &[&str] = [
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "ALL_PROXY", "all_proxy"
];

// Scan for existing proxy environment variables
// → Can chain them if needed
```

### 3. **Proxy Chaining (Upstream Proxy Support)**

If you already have a proxy configured, ACRouter can **chain through it**:

```
Your Application
    ↓
ACRouter Proxy (127.0.0.1:5002)
    ↓
Your Existing Upstream Proxy (10.0.0.1:8080)
    ↓
Internet
```

**Configuration:**
```env
HTTP_PROXY=http://10.0.0.1:8080
HTTPS_PROXY=http://10.0.0.1:8080

# ACRouter detects and chains through it
CCR_UPSTREAM_PROXY_URL=http://10.0.0.1:8080
```

**In Node.js/Gateway:**
```typescript
const env: NodeJS.ProcessEnv = {
  ...process.env,
  HTTP_PROXY: upstreamProxyUrl,        // Your existing proxy
  HTTPS_PROXY: upstreamProxyUrl,
  ALL_PROXY: upstreamProxyUrl,
  NO_PROXY: mergeNoProxy(env.NO_PROXY, [
    "127.0.0.1",
    "localhost",
    "::1"
  ])
};
```

### 4. **Graceful Restoration**

When you disable ACRouter, it restores your original proxy settings:

**Windows Example:**
```rust
async fn restoreWindowsSystemProxy(snapshot: WindowsSystemProxySnapshot) {
    // Restore EXACT values from snapshot (not hardcoded defaults)
    await setWindowsRegistryString("ProxyServer", snapshot.original_proxy_server);
    await setWindowsRegistryString("ProxyOverride", snapshot.original_override);
    await setWindowsRegistryDword("ProxyEnable", snapshot.original_enable);
}
```

**macOS Example:**
```typescript
// For each network service, restore original settings
await setMacProxySettings(
  "-setwebproxy",
  serviceName,
  sanitizeMacProxySettingsForRestore(service.web, originalEndpoint)
);
```

---

## Platform-Specific Handling

### **Windows**
- ✅ Backs up: `ProxyServer`, `ProxyOverride`, `ProxyEnable`, `AutoDetect`
- ✅ Sets up: Local loopback proxy via Registry
- ✅ Supports: WinHTTP proxy (netsh.exe) for curl/wget
- ✅ Restores: All original Registry values

### **macOS**
- ✅ Backs up: Web proxy, Secure proxy, SOCKS proxy per network service
- ✅ Sets up: Local proxy via `networksetup` command
- ✅ Detects: Multiple network services (Wi-Fi, Ethernet, VPN, etc.)
- ✅ Restores: All original settings per service

### **Linux**
- ✅ Reads: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` environment variables
- ✅ Chains through: Existing upstream proxy (if set)
- ✅ Fallback: Direct connection (if no proxy)

---

## Failover & Priority System

ACRouter maintains a **provider failover queue** with automatic recovery:

```
Priority Queue (ACRouter uses highest healthy provider):
├── 1. Provider A  [Currently Healthy]  ●
├── 2. Provider B  [Degraded: 2 failures]  ◐
└── 3. Provider C  [Unhealthy: 3+ failures]  ○

If Provider A fails:
  → Try Provider B
  → If B succeeds, health recovers
  → When A recovers, auto-switch back (if higher priority)
```

**Health Status:**
- 🟢 **Green:** 0 consecutive failures
- 🟡 **Yellow:** 1-2 consecutive failures
- 🔴 **Red:** 3+ consecutive failures

---

## Conflict Detection & Prevention

### **Self-Referential Loop Detection**

ACRouter detects if system proxy is already pointing to itself:

```rust
fn system_proxy_points_to_loopback() -> bool {
    // If HTTP_PROXY=http://127.0.0.1:5002 already,
    // don't set it again → avoid double-proxying
}
```

### **Backup Corruption Detection**

If a backup contains proxy configuration (not user's original):

```rust
fn live_has_proxy_placeholder_for_app(app_type: &AppType, config: &Value) -> bool {
    // Check if config contains ACRouter proxy placeholder
    // If true:
    //   - Don't use backup (it's corrupted/proxy-modified)
    //   - Fall back to SSOT rebuild
    //   - Log warning
}
```

### **Provider Priority Recovery**

If a higher-priority provider recovers, ACRouter auto-switches:

```rust
// If restored provider has lower sort_index (higher priority):
if restored < current {
    log::info!(
        "Provider {provider_id} restored and has higher priority (P{} vs P{}), switching",
        restored, current
    );
    // Auto-switch to the recovered provider
}
```

---

## Best Practices When Using Existing Proxy

### ✅ **Recommended Setup**

1. **Let ACRouter detect your proxy:**
   ```bash
   export HTTP_PROXY=http://corp-proxy.example.com:8080
   export HTTPS_PROXY=http://corp-proxy.example.com:8080
   ```

2. **Enable ACRouter** → It will:
   - Back up your proxy settings
   - Set up local routing proxy (127.0.0.1:5002)
   - Chain requests through your corporate proxy

3. **Disable ACRouter** → It will:
   - Automatically restore your original proxy

### ❌ **Things to Avoid**

1. **Don't manually modify Windows Registry while ACRouter is running**
   - ACRouter's backup may become stale
   - Restoration could fail

2. **Don't set `HTTP_PROXY=http://127.0.0.1:5002` manually**
   - Creates self-referential loop
   - ACRouter detects this and skips setup

3. **Don't delete ACRouter config while proxies are active**
   - Loses backup information
   - Settings cannot be restored

### ⚠️ **Troubleshooting**

**If proxy doesn't restore after disabling ACRouter:**

1. Check if backup was corrupted:
   ```bash
   # Windows
   Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
   ```

2. Manually restore:
   ```bash
   # Windows
   netsh winhttp reset proxy
   
   # macOS
   networksetup -setwebproxystate "Wi-Fi" off
   ```

3. Clear ACRouter state and reconfigure

---

## Environment Variable Chaining Example

**Original System Setup:**
```bash
HTTP_PROXY=http://10.0.0.1:8080
HTTPS_PROXY=http://10.0.0.1:8080
```

**When ACRouter Starts:**
```bash
# ACRouter system proxy becomes 127.0.0.1:5002
# But gateway process inherits upstream:
HTTP_PROXY=http://10.0.0.1:8080           # Original upstream
HTTPS_PROXY=http://10.0.0.1:8080
ALL_PROXY=http://10.0.0.1:8080
CCR_UPSTREAM_PROXY_URL=http://10.0.0.1:8080
NO_PROXY=127.0.0.1,localhost,::1,acrouter.local
```

**Request Flow:**
```
IDE/App → (system proxy) → 127.0.0.1:5002 (ACRouter)
                               ↓
                        (checks routing rules)
                               ↓
                        (needs internet)
                               ↓
                 (uses CCR_UPSTREAM_PROXY_URL)
                               ↓
                        10.0.0.1:8080 (your proxy)
                               ↓
                           Internet
```

---

## Summary

| Aspect | ACRouter Behavior |
|--------|-------------------|
| **Pre-existing proxy** | ✅ Backs up automatically |
| **Self-referential loops** | ✅ Detects and prevents |
| **Proxy chaining** | ✅ Chains through upstream proxy |
| **Restoration** | ✅ Restores original settings |
| **Corporate proxies** | ✅ Fully supported |
| **Multiple network services** | ✅ Handles per-service (macOS) |
| **Conflict recovery** | ✅ Automatic failover & recovery |

**Bottom Line:** ACRouter is designed to **coexist peacefully** with your existing proxy infrastructure. It backs up, chains, and restores gracefully.
