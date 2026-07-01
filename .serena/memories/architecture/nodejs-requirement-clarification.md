# Is Node.js a Requirement for ACRouter?

## Short Answer
**No. Node.js is NOT a requirement for the core ACRouter routing logic.**

ACRouter has **three separate implementations/integrations**, each with different runtime requirements:

---

## The Three Components

### 1. **Core ACRouter Router Logic** (.NET 10 / C#) ✅
**Location:** `src/AgenticRouter/`
**Runtime:** .NET 10 / C#
**Required?** YES

This is the heart of ACRouter - the decision-making engine that routes tasks to different backend models.

- Implements `AgentAsARouter` routing algorithm
- Core components: `Route()` and `Observe()` decision flows
- Memory management with epsilon-greedy exploration
- Persistence via JSON or vector stores
- Runs in a Docker container (`dotnet` runtime)
- **No Node.js dependency**

---

### 2. **claude-code-router Integration** (TypeScript / Node.js / Electron)
**Location:** `claude-code-router/`
**Runtime:** Node.js + Electron
**Required?** NO - Optional runtime integration

This is a **desktop application** that integrates ACRouter into Claude Code Router's architecture.

- Adds gateway-level routing (before requests hit backend models)
- Written in TypeScript/Node.js
- Uses Electron for desktop UI
- Hosts an HTTP gateway server that:
  - Accepts requests from Claude Code
  - Calls the router to decide which model to use
  - Forwards request to selected backend
- **Requires Node.js** (bundled with Electron)

---

### 3. **cc-switch Integration** (Rust / Tauri)
**Location:** `cc-switch/src-tauri/`
**Runtime:** Rust + Tauri
**Required?** NO - Optional runtime integration

This is a **desktop proxy application** that integrates ACRouter into cc-switch's architecture.

- Adds proxy-level routing (intercepts traffic before provider/model mapping)
- Written in Rust
- Uses Tauri for desktop UI (lightweight alternative to Electron)
- **Does NOT require Node.js**

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│         ACRouter: Agent-as-a-Router                          │
│  (Research Paper Implementation & Routing Algorithm)         │
└────────────────────┬─────────────────────────────────────────┘
                     │
          ┌──────────┴───────────┐
          │                      │
    ┌─────▼─────────┐    ┌──────▼────────────┐
    │  AgenticRouter │    │  Runtime Integrations
    │  (.NET 10 / C#)│    │
    ├─────────────┤    ├────────────────────┤
    │ • Router    │    │ • claude-code-     │
    │   logic     │    │   router           │
    │ • Models    │    │   (Node.js/        │
    │ • Decision  │    │    Electron)       │
    │   flow      │    │                    │
    │ • Memory    │    │ • cc-switch        │
    │ • Docker    │    │   (Rust/Tauri)     │
    └─────────────┘    └────────────────────┘
         .NET 10          Optional Integrations
         Required         Not Required
```

---

## When You Need Node.js

### ✅ You need Node.js IF:
- You want to run **claude-code-router** desktop app
- You want to integrate routing at the Claude Code gateway level
- You want the Electron-based UI for managing routing

### ❌ You don't need Node.js IF:
- You only use **AgenticRouter** (.NET 10 CLI or library)
- You use **cc-switch** integration (Rust/Tauri, not Node.js)
- You embed ACRouter's routing logic into your own .NET application

---

## File Structure Clarity

```
agent-as-a-router/
├── src/AgenticRouter/                    ← CORE ROUTER (.NET 10)
│   ├── Router/                           ← Routing logic
│   │   ├── AgentAsARouter.cs
│   │   ├── RouterMemory.cs
│   │   └── ...
│   ├── Models/                           ← Routing data structures
│   ├── Program.cs                        ← .NET CLI entry point
│   └── Dockerfile                        ← Runs on .NET runtime
│
├── claude-code-router/                   ← OPTIONAL INTEGRATION (Node.js)
│   ├── package.json                      ← Node.js dependencies
│   ├── src/main/                         ← Electron main process
│   ├── src/renderer/                     ← React UI
│   └── src/server/gateway/               ← HTTP gateway (integrates router)
│
├── cc-switch/                            ← OPTIONAL INTEGRATION (Rust)
│   ├── src-tauri/                        ← Rust + Tauri code
│   ├── Cargo.toml                        ← Rust dependencies
│   └── src/services/                     ← Proxy service logic
│
└── docs/
    └── HANDBOOK.md, PROXY_COEXISTENCE.md ← Architecture docs
```

---

## Key Distinction

| Aspect | AgenticRouter | claude-code-router | cc-switch |
|--------|--------------|-------------------|-----------|
| **Technology** | C# / .NET 10 | TypeScript / Node.js | Rust |
| **UI** | CLI / programmatic | Desktop (Electron) | Desktop (Tauri) |
| **Purpose** | Core routing logic | Gateway integration | Proxy integration |
| **Node.js?** | ❌ No | ✅ Yes | ❌ No |
| **Essential?** | ✅ Yes (core) | ❌ Optional | ❌ Optional |

---

## Typical Use Cases

### Use Case 1: Research / Benchmarking
```bash
# Run ACRouter router logic only (no Node.js needed)
$ dotnet run --project src/AgenticRouter/AgenticRouter.csproj
# Runs routing algorithm against benchmark data
```

### Use Case 2: Claude Code Integration
```bash
# Run claude-code-router with embedded routing (Node.js required)
$ cd claude-code-router
$ npm install
$ npm run build
# Launches Electron app with routing at gateway level
```

### Use Case 3: cc-switch Integration
```bash
# Run cc-switch with proxy-level routing (Rust/Tauri, no Node.js)
$ cd cc-switch/src-tauri
$ cargo build
# Launches proxy with routing decisions
```

---

## Summary

**Node.js is NOT a requirement for ACRouter itself**, but it IS a requirement for the **claude-code-router** integration.

- **AgenticRouter** (.NET 10) = Core router logic, standalone, no Node.js
- **claude-code-router** (TypeScript/Node.js) = Optional desktop gateway with routing
- **cc-switch** (Rust/Tauri) = Optional proxy application with routing, no Node.js

You can use ACRouter's routing logic in any .NET application without Node.js. You only need Node.js if you specifically want the claude-code-router desktop integration.
