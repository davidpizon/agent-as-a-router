# Implementation Plan: Converting Agent-as-a-Router to C#

This document outlines a phased, parity-first migration from the current Python implementation to a .NET 10 C# application. The conversion should cover the core router, shared models, tools, demos, and tests, and every phase should be validated with unit tests before integration-level verification.

**Architectural Goal:** Port the proven **System Proxy Interception** pattern from `cc-switch` (Rust/Tauri) to .NET, enabling transparent integration with GitHub Copilot and other IDE extensions without requiring IDE-specific modifications.

## Guiding Principles
- Preserve current behavior first; refactor only after parity is proven.
- Use dependency injection, async/await, the options pattern, structured logging, nullable reference types, and analyzers.
- Keep public APIs small and explicit.
- Prefer deterministic, testable abstractions around model calls and tool execution.
- Require XML documentation comments for all classes and functions introduced or modified in each phase.
- Validate each phase with unit tests before integration tests.
- **Proxy-first design:** Route all LLM API traffic through a local HTTP proxy (port 5001) before forwarding to providers, eliminating need for IDE-specific integrations.

## Testing Strategy
- Start with unit tests for shared models, router decisions, tool helpers, and configuration binding.
- Keep unit tests deterministic by mocking external model calls, file system access, and Roslyn execution boundaries where practical.
- Add integration tests only after the unit-test layer is stable, then cover composition, end-to-end routing, and regression parity against Python baselines.
- Use test names and fixtures that clearly separate contract tests, behavior tests, and parity checks.
- **Proxy Testing:** Include tests for HTTP request interception, header preservation, request rewriting, and response observation at the proxy layer.

## Source File Map
| Phase | `src/AgenticRouter` files | `src/AgenticRouter.Tests` files |
| --- | --- | --- |
| Phase 0: Discovery and Repository Mapping | `src/AgenticRouter/Program.cs` | `src/AgenticRouter.Tests/UnitTest1.cs` |
| Phase 1: Solution and Infrastructure Foundation | `src/AgenticRouter/AgenticRouter.csproj`, `src/AgenticRouter/Program.cs` | `src/AgenticRouter.Tests/AgenticRouter.Tests.csproj`, `src/AgenticRouter.Tests/UnitTest1.cs` |
| Phase 2: Shared Models and Contracts | `src/AgenticRouter/Models/RoutingDecision.cs`, `src/AgenticRouter/Models/RoutingOptions.cs`, `src/AgenticRouter/Models/RouterConstants.cs` | `src/AgenticRouter.Tests/Models/RoutingDecisionTests.cs`, `src/AgenticRouter.Tests/Models/RoutingOptionsTests.cs` |
| Phase 3: Core Router Logic | `src/AgenticRouter/Router/AgentAsARouter.cs`, `src/AgenticRouter/Router/IRouterModelClient.cs`, `src/AgenticRouter/Router/RouterMemory.cs` | `src/AgenticRouter.Tests/Router/AgentAsARouterTests.cs`, `src/AgenticRouter.Tests/Router/RouterMemoryTests.cs` |
| Phase 3.5: Router Memory Persistence | `src/AgenticRouter/Router/IRouterMemoryStore.cs`, `src/AgenticRouter/Router/JsonRouterMemoryStore.cs`, `src/AgenticRouter/Router/VectorStoreRouterMemoryStore.cs` | `src/AgenticRouter.Tests/Router/JsonRouterMemoryStoreTests.cs`, `src/AgenticRouter.Tests/Router/PersistenceRegressionTests.cs` |
| Phase 4: Tooling and Evaluation Services | `src/AgenticRouter/Tools/CheckSyntax.cs`, `src/AgenticRouter/Tools/RunVisibleTests.cs`, `src/AgenticRouter/Tools/EstimateQuality.cs` | `src/AgenticRouter.Tests/Tools/CheckSyntaxTests.cs`, `src/AgenticRouter.Tests/Tools/RunVisibleTestsTests.cs`, `src/AgenticRouter.Tests/Tools/EstimateQualityTests.cs` |
| Phase 5: System Proxy and IDE Integration | `src/AgenticRouter/Proxy/ProxyServer.cs`, `src/AgenticRouter/Proxy/ProxyMiddleware.cs`, `src/AgenticRouter/Proxy/RequestInterceptor.cs`, `src/AgenticRouter/Hosting/ProxyHostedService.cs` | `src/AgenticRouter.Tests/Proxy/ProxyServerTests.cs`, `src/AgenticRouter.Tests/Proxy/ProxyMiddlewareTests.cs`, `src/AgenticRouter.Tests/Proxy/RequestInterceptorTests.cs` |
| Phase 6: Demo and Workflow Migration | `src/AgenticRouter/Program.cs`, `src/AgenticRouter/Hosting/ServiceCollectionExtensions.cs` | `src/AgenticRouter.Tests/ProgramTests.cs`, `src/AgenticRouter.Tests/Hosting/ServiceCollectionExtensionsTests.cs` |
| Phase 7: Integration and Regression Validation | `src/AgenticRouter/Program.cs` | `src/AgenticRouter.Tests/Integration/RouterCompositionTests.cs`, `src/AgenticRouter.Tests/Integration/ParityRegressionTests.cs`, `src/AgenticRouter.Tests/Integration/ProxyInterceptionTests.cs` |

## 1. Phase 0: Discovery and Repository Mapping
- Inventory the Python modules, demo scripts, and test fixtures that define current behavior.
- Map each surface area to its C# equivalent in `src/AgenticRouter` and `src/AgenticRouter.Tests`.
- Capture current benchmark expectations and repository constraints from the documentation.
- Exit criteria: migration scope and parity targets are documented.

## 2. Phase 1: Solution and Infrastructure Foundation
- Stabilize the .NET 10 solution layout and project references.
- Add the required packages for Semantic Kernel, Roslyn, testing, configuration, and logging.
- Configure nullable reference types, implicit usings, analyzers, and formatting rules.
- Introduce a dependency injection composition root and options-bound configuration.
- Exit criteria: the app starts cleanly and is ready for isolated unit testing.

## 3. Phase 2: Shared Models and Contracts
- Port routing records, settings, result contracts, and constants.
- Keep DTOs immutable where practical and validate their defaults.
- Add unit tests for contract shape, default values, and validation behavior.
- Exit criteria: shared types compile and tests cover contract behavior.

## 4. Phase 3: Core Router Logic
- Port the `AgentAsARouter` decision flow incrementally.
- Implement `Route` and `Observe` with testable interfaces for model access and memory.
- Preserve epsilon-greedy exploration while keeping the logic deterministic under test.
- Add unit tests for routing decisions, learning updates, and failure cases.
- Exit criteria: router behavior matches the intended Python parity model under unit tests.

## 5. Phase 3.5: Router Memory Persistence (JSON + Optional Vector Store)
**Purpose:** Enable router learning across sessions by persisting memory to disk and optionally to a vector database for semantic similarity queries.

### 5.1 Persistent Storage Architecture
The router maintains two complementary storage layers:

#### Layer 1: JSON File (Primary, Always Enabled)
- **Format:** Structured JSON document with dimension → model → scores history
- **Path:** `{MemoryPath}/router_memory.json` (default: `./router_memory.json`)
- **Schema:**
  ```json
  {
    "version": "1.0",
    "lastUpdated": "2025-01-15T14:32:00Z",
    "dimensions": {
      "code_gen": {
        "gpt-4-turbo": {
          "scores": [0.95, 0.92, 0.88, 0.91],
          "count": 4,
          "average": 0.915,
          "lastUpdated": "2025-01-15T14:31:55Z"
        },
        "gpt-4": {
          "scores": [0.88, 0.85, 0.87],
          "count": 3,
          "average": 0.867,
          "lastUpdated": "2025-01-15T14:30:00Z"
        }
      },
      "bug_fix": {
        "claude-3-sonnet": {
          "scores": [0.92, 0.94, 0.93],
          "count": 3,
          "average": 0.933,
          "lastUpdated": "2025-01-15T14:25:00Z"
        }
      }
    },
    "metadata": {
      "totalRoutingDecisions": 47,
      "uniqueDimensions": 2,
      "explorationRate": 0.15,
      "lastMemoryCompaction": "2025-01-15T10:00:00Z"
    }
  }
  ```
- **Operations:**
  - **Write:** Save memory to disk after each observation (async, non-blocking)
  - **Read:** Load memory on startup (blocking, before routing begins)
  - **Compaction:** Periodically summarize scores (keep last N=100 scores per model, compute rolling average)
  - **Backup:** Create timestamped backup before major updates

#### Layer 2: Vector Store (Optional, Enhanced Retrieval)
- **Purpose:** Enable semantic similarity queries ("which models work for tasks similar to this one?")
- **Implementation Options:**
  1. **In-Memory (Development):** Use managed collection (e.g., Cosine similarity over embeddings)
  2. **Milvus (Production):** Distributed vector DB for semantic search
  3. **Weaviate (Alternative):** GraphQL-based vector store
  4. **SQLite + Vector Extension:** Simple, embedded option for moderate scales
- **Content:** Store task embeddings + routing decisions for semantic retrieval
- **Query Example:** "Find best model for tasks similar to 'refactor Python asyncio code'"
- **Configuration:** Enable/disable via `VectorStoreEnabled` flag

### 5.2 Memory Persistence Implementation
**Files:**
- `src/AgenticRouter/Router/IRouterMemoryStore.cs` — interface for storage backends
- `src/AgenticRouter/Router/JsonRouterMemoryStore.cs` — JSON file implementation
- `src/AgenticRouter/Router/VectorStoreRouterMemoryStore.cs` — optional vector DB wrapper
- `src/AgenticRouter/Router/RouterMemory.cs` — in-memory + persistent facade

**Key Methods:**
```csharp
public interface IRouterMemoryStore
{
    // Load from persistent storage (blocking)
    Task<RouterMemoryData> LoadAsync(CancellationToken ct = default);

    // Save to persistent storage (async, non-blocking)
    Task SaveAsync(RouterMemoryData data, CancellationToken ct = default);

    // Compact/summarize old data
    Task CompactAsync(int maxScoresPerModel, CancellationToken ct = default);

    // Optional: semantic search (vector store only)
    Task<IEnumerable<(string Model, double Score)>> FindSimilarAsync(
        string taskDescription, int topK = 5, CancellationToken ct = default);
}

public class RouterMemory
{
    private readonly IRouterMemoryStore _store;
    private RouterMemoryData _cache; // in-memory cache
    private readonly SemaphoreSlim _updateLock; // prevent concurrent writes

    public async Task ObserveAsync(string dimension, string model, double score)
    {
        lock (_updateLock)
        {
            _cache.AddScore(dimension, model, score);
        }

        // Save asynchronously (don't block routing)
        _ = _store.SaveAsync(_cache);
    }

    public double GetBestModel(string dimension, out string chosenModel)
    {
        // Fast in-memory lookup
        return _cache.GetBestModel(dimension, out chosenModel);
    }
}
```

### 5.3 Persistence Configuration
**appsettings.json additions:**
```json
{
  "MemorySettings": {
    "PersistencePath": "./data",
    "JsonMemoryFile": "router_memory.json",
    "AutoSaveIntervalMs": 5000,
    "CompactThresholdScoresPerModel": 100,
    "CompactIntervalHours": 24,
    "EnableBackups": true,
    "BackupRetentionDays": 7,
    "VectorStoreEnabled": false,
    "VectorStoreType": "Milvus|Weaviate|SQLite",
    "VectorStoreConnection": "localhost:19530",
    "EmbeddingDimension": 768,
    "VectorStoreTopK": 5
  }
}
```

**Environment Variables (Optional Overrides):**
```bash
export MEMORY_PERSISTENCE_PATH=/var/lib/acrouter/memory
export MEMORY_AUTO_SAVE_MS=2000
export VECTOR_STORE_ENABLED=true
export VECTOR_STORE_TYPE=Milvus
```

### 5.4 Testing Strategy for Persistence
- **Unit Tests:**
  - `JsonRouterMemoryStoreTests`: load, save, compaction, backup behavior
  - `RouterMemoryTests`: in-memory cache behavior, async save without blocking
  - `MemoryCompactionTests`: score summarization, old data pruning
- **Integration Tests:**
  - `PersistenceRegressionTests`: memory survives application restart
  - `VectorStoreIntegrationTests`: semantic similarity queries (if vector store enabled)
  - `ConcurrentWriteTests`: verify no data loss under concurrent routing + observations
- **Exit criteria:** Memory persists across restarts, compaction works, no data corruption.

### 5.5 Migration Path
1. **Phase 3.5a:** Implement `IRouterMemoryStore` interface + `JsonRouterMemoryStore`
2. **Phase 3.5b:** Integrate into `RouterMemory` with async save
3. **Phase 3.5c:** Add JSON schema validation and backup logic
4. **Phase 3.5d:** (Optional) Implement vector store abstraction + Milvus/Weaviate integration
5. **Phase 3.5e:** Add persistence tests and load/save verification

- Exit criteria: Router memory persists to disk with JSON, supports optional vector store, and passes all persistence tests.

## 6. Phase 4: Tooling and Evaluation Services
- Port syntax checks, quality scoring, and test execution helpers.
- Wrap Roslyn usage behind interfaces so the logic can be unit tested without live compilation where possible.
- Add unit tests for success paths, failure paths, and deterministic scoring.
- Exit criteria: tooling behavior is validated in isolation.

## 7. Phase 5: System Proxy and IDE Integration
**Reference Implementation:** `cc-switch/src-tauri/src/proxy/server.rs` and `cc-switch/src-tauri/src/proxy/acrouter.rs`

### 5.1 Proxy Server Architecture
- Implement `ProxyServer` using ASP.NET Core Kestrel (embedded HTTP server).
- Listen on `localhost:5001` (non-privileged port, matches Rust implementation).
- Preserve original HTTP request headers (case-sensitive) to match wire format of direct (non-proxied) IDE requests.
- Support both HTTP and HTTPS (MITM certificate authority for encrypted provider APIs).

### 5.2 Request Interception and Routing Middleware
- Implement `ProxyMiddleware` to intercept all incoming API requests.
- Extract request body (JSON) before forwarding to determine target provider and model.
- **Call ACRouter** before forwarding: inject routing decision into request.
- Rewrite `body.model` field to selected model based on ACRouter's decision.
- Preserve all other request fields, headers, and metadata (no mutations except model field).

### 5.3 Response Observation and Learning
- Capture response from provider (score, latency, errors, usage tokens).
- **Observe feedback** immediately after response: feed (task_id, model, outcome) into RouterMemory.
- Log all routing decisions, observations, and scores for debugging and audit.

### 5.4 System Proxy Integration (Windows)
- Add `SystemProxyManager` to configure OS-level proxy settings on Windows:
  - Enable: `netsh winhttp set proxy 127.0.0.1:5001`
  - Disable: `netsh winhttp reset proxy`
- Support graceful proxy restoration on app shutdown (with timeout).
- Log proxy state and changes for diagnostic purposes.

### 5.5 Testing Strategy
- **Unit Tests:**
  - `ProxyServerTests`: test startup, shutdown, port binding, error handling.
  - `ProxyMiddlewareTests`: test request rewriting (model field), header preservation, no-op mutations.
  - `RequestInterceptorTests`: test JSON extraction, ACRouter integration, decision injection.
- **Integration Tests:**
  - `ProxyInterceptionTests`: mock provider endpoint, verify interception, routing, and observation.
  - Test HTTPS MITM certificate handling.
  - Test system proxy enable/disable (Windows integration).
  - Verify no latency overhead (expect <5ms added latency).

- Exit criteria: Proxy server intercepts all API traffic, applies ACRouter decisions, and observes outcomes without breaking IDE extensions.

## 8. Phase 6: Demo and Workflow Migration
- Update the demos and CLI entrypoints to call the C# services.
- Keep configuration in appsettings and options classes rather than hard-coded constants.
- Preserve the current repository workflows while moving them onto the C# implementation.
- Exit criteria: demos run against the C# application with equivalent behavior.

## 9. Phase 7: Integration and Regression Validation
- Add integration tests for router, tool, and configuration composition.
- Compare representative outputs against Python baselines and documented benchmark expectations.
- Verify docs, samples, and generated outputs remain consistent.
- **Proxy Integration Tests:** Verify end-to-end interception with mock IDE extension and provider endpoints.
- Exit criteria: parity is confirmed, proxy interception is working, and the migration is ready for release.

## Architectural Decisions

### System Proxy Interception (vs. Direct HTTP API)
**Rationale:** The proven pattern from `cc-switch` (Rust/Tauri implementation) demonstrates that system proxy interception is more efficient and universal than direct HTTP APIs:

| Aspect | System Proxy | Direct HTTP API |
|--------|--------------|-----------------|
| **IDE Support** | All IDEs, all extensions | VS Code only, extension-specific |
| **Installation** | Single service + OS config | Extension modification required |
| **Latency** | 2-5ms (transparent) | 50-200ms (network round-trip) |
| **Maintenance** | Centralized routing logic | Duplicated in each extension |
| **GitHub Copilot** | Automatic (system-wide) | Requires extension hook |
| **Visual Studio** | Works (system proxy) | Limited integration |
| **Test Coverage** | Easier to test centrally | Extension-specific tests needed |

**Decision:** Implement as system proxy on port 5001, matching `cc-switch` architecture.

### Key Proxy Design Constraints
1. **Header Preservation:** Capture and preserve original HTTP header casing (match wire format of direct requests).
2. **Request Integrity:** Mutate only the `body.model` field; leave all other data untouched.
3. **Zero Latency Overhead:** Target <5ms added latency (use async, streaming, no buffering).
4. **HTTPS Support:** Implement MITM certificate authority to intercept encrypted provider APIs.
5. **Graceful Shutdown:** Flush pending requests and restore system proxy before exit.
6. **Observability:** Log all routing decisions and observations for audit and debugging.

### Configuration (appsettings.json)
```json
{
  "ProxySettings": {
    "ListenAddress": "127.0.0.1",
    "ListenPort": 5001,
    "SystemProxyEnabled": true,
    "SystemProxyRestoreTimeoutMs": 10000,
    "PreserveHeaderCase": true,
    "MaxConnectionsPerProvider": 100,
    "RequestTimeoutSeconds": 120
  },
  "MemorySettings": {
    "PersistencePath": "./data",
    "JsonMemoryFile": "router_memory.json",
    "AutoSaveIntervalMs": 5000,
    "CompactThresholdScoresPerModel": 100,
    "CompactIntervalHours": 24,
    "EnableBackups": true,
    "BackupRetentionDays": 7,
    "VectorStoreEnabled": false,
    "VectorStoreType": "Milvus",
    "VectorStoreConnection": "localhost:19530",
    "EmbeddingDimension": 768,
    "VectorStoreTopK": 5
  },
  "ACRouter": {
    "Enabled": true,
    "CheapChain": ["gpt-4-turbo"],
    "EscalateTo": "gpt-4",
    "MaxNeighbors": 10,
    "ExplorationRate": 0.15
  }
}
```

## Risks & Mitigations
- **Roslyn Performance**: keep snippets minimal and cache reusable state where safe.
- **LLM Behavior Drift**: pin prompt contracts and compare outputs in regression tests.
- **Demo Compatibility**: migrate entrypoints incrementally and keep old behavior documented until parity is reached.
- **Proxy Port Conflicts**: ensure port 5001 is available; allow configuration for alternative ports.
- **MITM Certificate Trust**: handle certificate installation gracefully; document Windows system proxy bypass if needed.
- **System Proxy Cleanup**: ensure system proxy is restored on abnormal shutdown (use `finally` blocks and process exit handlers).
- **Header Casing Edge Cases**: test with various API providers (OpenAI, Anthropic, custom) to ensure header preservation doesn't break authentication.
- **Memory Persistence Race Conditions**: protect memory updates with locks; use async save to avoid blocking routing.
- **Memory File Corruption**: validate JSON schema on load; implement recovery from corrupted files (fallback to backup or empty state).
- **Memory Growth**: implement compaction to prevent unbounded disk usage; archive old observations.
- **Vector Store Availability**: make vector store optional; gracefully degrade to JSON-only if unavailable.
- **Concurrent Load/Save**: ensure thread-safe access to memory data; use SemaphoreSlim for update serialization.

## References
- `docs/HANDBOOK.md` — repository scope, benchmark goals, and current reproduction commands.
- `data/README.md` — data layout and legacy/current benchmark boundaries.
- `outputs/current/summary.md` — current release summary and reference metrics.
- `src/AgenticRouter/AgenticRouter.csproj` and `src/AgenticRouter.Tests/AgenticRouter.Tests.csproj` — C# project boundaries for the migration.