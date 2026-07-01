# Electron Usage in ACRouter (Claude Code Router)

## Overview

**Electron is used as the desktop application shell** for Claude Code Router, the TypeScript/Node.js component of ACRouter.

---

## Why Electron Is Used

### 1. **Desktop Application Framework**
- Creates a native desktop application (Windows, macOS, Linux)
- Provides window management, menu system, tray integration
- Bundles Node.js runtime with Chromium browser

### 2. **IPC Bridge Between UI and Backend**
- **Renderer process** (UI): React-based web interface in Chromium
- **Main process** (backend): Node.js services for proxy, gateway, authentication
- **IPC (Inter-Process Communication)**: Secure message passing via preload script

### 3. **System Integration**
- Direct access to file system (reading configs, databases, certificates)
- System proxy manipulation (Windows Registry, macOS networksetup)
- Tray icon and menu integration
- Deep linking (handling URLs like `ccr://...`)
- Platform-specific features (macOS traffic light position, Windows taskbar)

### 4. **Single-Instance Lock**
- Prevents multiple instances of the app running simultaneously
- Directs secondary instance launches to show existing window

### 5. **Background Services**
- Node.js backend runs in the main process (not killed when window closes)
- Proxy server, gateway, authentication services run continuously
- IPC allows renderer to communicate with these services

---

## Architecture: Where Electron Is Used

```
┌─────────────────────────────────────────────────────────┐
│           Electron Application (Desktop)                 │
├─────────────────────┬─────────────────────────────────┤
│   Main Process      │      Renderer Process            │
│  (Node.js Backend)  │    (React Browser)              │
├─────────────────────┼─────────────────────────────────┤
│ • Proxy server      │ • Web UI (React)                 │
│ • Gateway service   │ • User interactions              │
│ • Auth services     │ • Settings management            │
│ • File system I/O   │ • Configuration forms            │
│ • System integration│ • Status dashboards              │
│ • IPC server        │ • IPC client (preload)           │
└─────────────────────┴─────────────────────────────────┘
         ▲                           ▲
         │ Context Isolation         │ Sandboxed
         │ Node Integration OFF      │ Web Security ON
         │ Preload Bridge            │
         └───────────────────────────┘
```

### Main Process Responsibilities
**File:** `src/main/main.ts`

```typescript
// Electron app lifecycle
app.on("second-instance")          // Prevent multiple instances
app.whenReady()                     // Initialize when ready
app.on("activate")                 // macOS app reactivation
app.on("before-quit")              // Cleanup on shutdown

// Windows management
windowsManager.createMainWindow()  // Chromium browser window
windowsManager.showMainWindow()    // Show/focus window

// Backend services (run in main process)
gatewayService.start(config)       // Gateway server
proxyService.start(config)         // Proxy intercept service
appUpdateService.start()           // Update checker
trayController.start()             // System tray

// IPC handlers (registered in ipc.ts)
ipcMain.handle("app:getConfig")    // Config requests
ipcMain.invoke("app:saveConfig")   // Settings save
```

### Renderer Process Responsibilities
**File:** `src/renderer/pages/home/App.tsx`

```typescript
// React UI with Electron bridge
import { ccr } from "window.ccr"  // Preload-exposed API

// IPC calls from renderer
const config = await ccr.getConfig()
await ccr.saveConfig(newConfig)
const status = await ccr.getGatewayStatus()
```

### Security: Context Isolation & Preload Script
**File:** `src/main/windows.ts` (BrowserWindow config)

```typescript
webPreferences: {
  contextIsolation: true,      // Renderer cannot access Node.js
  nodeIntegration: false,      // No direct node require()
  preload: path.join(__dirname, "preload.js"),  // Controlled bridge
  sandbox: true,               // Renderer process is sandboxed
  webSecurity: true            // Same-origin policy enforced
}
```

**File:** `src/main/preload.ts` (IPC Bridge)

```typescript
// Expose only safe APIs to renderer via contextBridge
contextBridge.exposeInMainWorld("ccr", {
  getConfig: () => invoke(IPC_CHANNELS.appGetConfig),
  saveConfig: (config) => invoke(IPC_CHANNELS.appSaveConfig, config),
  getGatewayStatus: () => invoke(IPC_CHANNELS.appGetGatewayStatus),
  // ... ~100 other safe API methods
});
```

---

## Key Electron Features Used

### 1. **BrowserWindow & Window Management**
```typescript
// src/main/windows.ts
new BrowserWindow({
  width: 1180,
  height: 760,
  minWidth: 360,
  minHeight: 420,
  show: false,
  webPreferences: { ... }
})

window.loadURL(rendererUrl)
window.show()
window.minimize() / window.maximize()
```

### 2. **IPC Communication**
```typescript
// Main process: listen for renderer messages
ipcMain.handle("channel-name", async (event, args) => {
  return await someAsyncOperation(args)
})

// Renderer process: send/receive via preload bridge
await ccr.methodName(args)  // Calls main process handler
```

### 3. **Menu System**
```typescript
// src/main/app-menu.ts
setupApplicationMenu()  // Application menu (File, Edit, View, etc.)
```

### 4. **Tray Icon**
```typescript
// src/main/tray-controller.ts
trayController.start()  // System tray with status, quick actions
```

### 5. **Deep Linking**
```typescript
// src/main/deep-link.ts
deepLinkService.register()        // Register ccr:// protocol
deepLinkService.handleArgv()      // Handle incoming URLs
```

### 6. **Dialog & File System**
```typescript
// src/main/ipc.ts
dialog.showOpenDialog()           // File open dialog
dialog.showMessageBox()           // Message dialog
fs.readFileSync() / fs.writeFileSync()  // File I/O
```

### 7. **App Updates**
```typescript
// src/main/update-service.ts
appUpdateService.start()          // Check for updates
appUpdateService.checkForUpdates()
```

### 8. **Native API Access**
```typescript
// System integration
shell.openPath(filePath)          // Open file with default app
shell.openExternal(url)           // Open URL in default browser
screen.getPrimaryDisplay()        // Screen dimensions
```

---

## File Structure: Electron-Related Files

```
claude-code-router/src/
├── main/                         # Main process (Electron backend)
│   ├── main.ts                   # Electron app lifecycle
│   ├── windows.ts                # Window/BrowserWindow management
│   ├── ipc.ts                    # IPC channel handlers (~850 lines)
│   ├── preload.ts                # Context isolation bridge (~170 lines)
│   ├── app-menu.ts               # Application menu
│   ├── tray-controller.ts        # Tray icon
│   ├── deep-link.ts              # ccr:// protocol handling
│   ├── update-service.ts         # App updates
│   ├── constants.ts              # App paths & constants
│   ├── config.ts                 # Configuration management
│   ├── app-config-store.ts       # SQLite config persistence
│   └── ... (40+ other main process files)
│
├── renderer/                      # Renderer process (UI)
│   ├── pages/home/               # Main application UI (React)
│   │   ├── App.tsx               # Root component
│   │   ├── main.tsx              # React entry point
│   │   └── ... (components)
│   └── types/
│       └── electron.d.ts         # Electron type definitions
│
└── shared/                        # Shared types
    ├── app.ts                    # AppConfig, ProxyStatus, etc.
    └── ipc-channels.ts           # IPC channel constants
```

---

## Why Electron vs Alternatives?

### ✅ Advantages Leveraged
1. **Native desktop experience** – Windows, macOS, Linux with platform-specific UI
2. **Full Node.js access** – Backend services run in same process
3. **Easy IPC** – Preload script provides secure communication between UI and services
4. **Single distribution** – Package entire app (Node.js + UI + native modules)
5. **System integration** – Tray, menus, deep links, file dialogs
6. **Auto-updates** – Built-in update framework
7. **Mature ecosystem** – Well-documented, lots of libraries

### ❌ Tradeoffs
1. **Large app size** – Chromium + Node.js bundled (~150MB+)
2. **Memory usage** – Two processes (main + renderer)
3. **Build complexity** – Need platform-specific build steps

---

## Electron Lifecycle in ACRouter

```
1. User launches app (desktop executable)
   ↓
2. Electron loads main.ts
   ↓
3. app.requestSingleInstanceLock() prevents multiple instances
   ↓
4. app.whenReady() event fires
   ↓
5. Create BrowserWindow with React renderer
   ↓
6. Load renderer URL (pages/home/index.html)
   ↓
7. Backend services start (proxy, gateway, auth)
   ↓
8. Renderer loads preload script (context isolation bridge)
   ↓
9. React UI initializes, calls ccr.* methods via IPC
   ↓
10. Main process handles IPC, delegates to services
    ↓
11. Results flow back to renderer via Promise resolution
    ↓
12. On close: cleanup backend services, restore system proxy, exit
```

---

## How Proxy System Integration Works

### Via Electron's Main Process:

1. **System Proxy Capture** → Main process (Node.js)
   ```typescript
   const snapshot = await captureSystemProxySnapshot()  // Windows Registry or macOS networksetup
   ```

2. **Proxy Server** → Main process
   ```typescript
   const server = http.createServer((req, res) => { ... })  // Runs in main process
   ```

3. **UI Control** → Renderer (React) ↔ IPC ↔ Main
   ```typescript
   // Renderer
   await ccr.activateSystemProxy()
   
   // Main (preload bridge routes to ipc.ts)
   ipcMain.handle("app:activateSystemProxy", async () => {
     return await proxyService.activateSystemProxy()
   })
   ```

4. **Persistent Snapshot** → Stored in `~/.acrouter/`
   ```typescript
   // Main process reads/writes snapshot file
   systemProxyManager.persistSnapshot(snapshot)
   ```

---

## Why Electron Is Critical for ACRouter

1. **Proxy Management** – Direct file system and OS API access required
2. **Continuous Service** – Backend runs 24/7 even if UI window closed
3. **System Integration** – System proxy requires elevated/system-level access
4. **Deep Linking** – ccr:// protocol handling requires desktop app
5. **Tray Icon** – Always-available system tray for quick access
6. **Auto-Updates** – Keep proxy service current
7. **Multi-Platform** – Single codebase for Windows/macOS/Linux

Without Electron:
- ❌ Cannot intercept system proxy
- ❌ Cannot run background services
- ❌ Cannot integrate with OS (tray, menus, deep links)
- ❌ Cannot distribute as native application

---

## Summary

**Electron is the foundation of Claude Code Router** because it enables:
- 🖥️ Desktop application UI (React in Chromium)
- 🔧 Backend services (Node.js proxy, gateway, auth)
- 🔌 IPC bridge (secure communication between UI and services)
- 🌐 System proxy interception (file system, Registry/networksetup access)
- 📦 Cross-platform distribution (Windows/macOS/Linux)

The combination of Electron's main process (Node.js) + renderer process (React UI) perfectly suited for building ACRouter's proxy routing capabilities.
