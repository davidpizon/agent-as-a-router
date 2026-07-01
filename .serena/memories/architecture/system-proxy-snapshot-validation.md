# System Proxy Snapshot Validation - Implementation Complete

## Overview
Implemented comprehensive validation of the `system-proxy-snapshot.json` file on ACRouter initialization to ensure data integrity and prevent crashes from corrupted or stale snapshots.

## Implementation Details

### 1. New Validation Function
**File:** `claude-code-router/src/server/proxy/system-proxy.ts`
**Function:** `validatePersistedSnapshot()`

```typescript
export function validatePersistedSnapshot(): { valid: boolean; reason?: string }
```

**Validation Checks:**
1. **File Existence** – No file is valid (initialization scenario)
2. **File Content** – Not empty
3. **JSON Format** – Valid JSON parsing
4. **Root Structure** – Must be an object
5. **Version Check** – Must be version 1
6. **Required Fields:**
   - `managedEndpoint` – Non-empty string (the proxy endpoint)
   - `createdAt` – Non-empty timestamp string
7. **Platform Match** – Snapshot OS must match current OS
8. **Platform-Specific Validation:**
   - **macOS:** services array must exist and be non-empty
   - **Windows:** settings object must exist
9. **Type Validation** – Final schema check via `isSystemProxySnapshot()`

**Return Values:**
- `{ valid: true }` – Snapshot is valid or doesn't exist
- `{ valid: false, reason: string }` – Validation failed with specific error message

### 2. Integration into Startup Flow
**File:** `claude-code-router/src/main/main.ts`

**Changes:**
1. Added import: `import { validatePersistedSnapshot } from "../server/proxy/system-proxy";`
2. Added validation call in `startPrimaryInstance()` at app startup:

```typescript
app.whenReady().then(() => {
  // Validate system proxy snapshot on startup
  const snapshotValidation = validatePersistedSnapshot();
  if (!snapshotValidation.valid) {
    console.warn(`[init] System proxy snapshot validation failed: ${snapshotValidation.reason}`);
  } else {
    console.info("[init] System proxy snapshot is valid or does not exist");
  }
  
  // ... rest of initialization
});
```

**Timing:** Validation runs immediately after `app.whenReady()` and before all other services start

### 3. Error Handling
- **Non-blocking:** Validation failure does not prevent application startup
- **Informative Logging:** Specific reason logged for debugging
- **Graceful Degradation:** Invalid snapshots are logged but ignored; existing `readPersistedSnapshot()` function already returns `undefined` for invalid data
- **Automatic Cleanup:** On next restore cycle, invalid snapshots are removed

### 4. Documentation Updates
**File:** `docs/PROXY_COEXISTENCE.md`

Updated to include:
- Note about snapshot validation on startup
- List of validation checks performed
- Automatic recovery behavior for corrupted files

## Validation Error Scenarios

| Scenario | Error Message | Resolution |
|----------|---------------|-----------|
| File doesn't exist | (skipped) | Valid - no snapshot needed |
| Empty file | "Snapshot file is empty" | Logged as warning; ignored |
| Invalid JSON | "Snapshot file contains invalid JSON: ..." | Logged; file ignored on next startup |
| Platform mismatch | "Snapshot platform mismatch: snapshot is for darwin, but running on win32" | Logged; file removed; original proxy settings intact |
| Missing managedEndpoint | "Snapshot missing or invalid managedEndpoint field" | Logged; file ignored |
| Missing createdAt | "Snapshot missing or invalid createdAt field" | Logged; file ignored |
| macOS: empty services | "macOS snapshot has empty services array" | Logged; file ignored |
| Windows: missing settings | "Windows snapshot missing or invalid settings object" | Logged; file ignored |
| Unsupported version | "Unsupported snapshot version: 2" | Logged; file ignored (future-proofing) |
| File read error | "Failed to read snapshot file: Permission denied" | Logged; system continues |

## Benefits

✅ **Data Integrity** – Validates snapshot structure before use
✅ **Crash Prevention** – Corrupted files don't break proxy restoration
✅ **Platform Safety** – Detects cross-platform snapshots and prevents misapplication
✅ **Debugging** – Specific error messages identify exact validation failures
✅ **Non-Blocking** – Validation failure doesn't prevent application startup
✅ **Automatic Recovery** – Invalid snapshots are cleaned up on next startup
✅ **Backward Compatible** – No changes to snapshot format or existing functionality

## Testing Checklist

- [ ] Valid snapshot file is accepted
- [ ] Missing snapshot file is accepted (returns valid: true)
- [ ] Empty file is rejected
- [ ] Invalid JSON is rejected
- [ ] Platform mismatch is detected and rejected
- [ ] Missing required fields are detected
- [ ] Application starts successfully despite validation failures
- [ ] Validation messages appear in application logs
- [ ] System proxy is correctly restored even if snapshot validation fails (existing `readPersistedSnapshot` fallback)

## Code References

- **Validation function:** `claude-code-router/src/server/proxy/system-proxy.ts:827-905`
- **Initialization call:** `claude-code-router/src/main/main.ts:40-48`
- **Existing snapshot reading:** `claude-code-router/src/server/proxy/system-proxy.ts:911-923`
- **Documentation:** `docs/PROXY_COEXISTENCE.md:56-94`

## Future Enhancements

- Add telemetry/metrics for validation failures
- Implement snapshot file backup before first use
- Add UI notification for validation warnings
- Implement snapshot self-healing for minor corruptions
