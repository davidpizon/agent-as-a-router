# Implementation Plan Update: Router Memory Persistence

## Summary

Successfully updated **PLAN.md** to explicitly document persistent storage strategies for router memory, including:

1. **Primary Storage:** JSON file (always enabled)
2. **Optional Storage:** Vector store for semantic similarity queries (Milvus, Weaviate, SQLite, or in-memory)

This ensures router learning persists across application restarts and enables advanced retrieval strategies.

---

## Changes Made

### 1. PLAN.md (Updated)

#### New Phase 3.5: Router Memory Persistence (JSON + Optional Vector Store)

**Location:** Between Phase 3 (Core Router Logic) and Phase 4 (Tooling)

**Sections Added:**

##### 5.1 Persistent Storage Architecture
- Two-tier storage strategy with rationale
- Layer 1: JSON File (Primary, Always Enabled)
- Layer 2: Vector Store (Optional, Enhanced Retrieval)

##### 5.2 Memory Persistence Implementation
- `IRouterMemoryStore` interface for storage backends
- `JsonRouterMemoryStore` implementation with code examples
- `VectorStoreRouterMemoryStore` wrapper for optional vector DB
- `RouterMemory` facade combining in-memory cache + persistent store

**Key Methods:**
```csharp
public interface IRouterMemoryStore
{
	Task<RouterMemoryData> LoadAsync(CancellationToken ct = default);
	Task SaveAsync(RouterMemoryData data, CancellationToken ct = default);
	Task CompactAsync(int maxScoresPerModel, CancellationToken ct = default);
	Task<IEnumerable<(string Model, double Score)>> FindSimilarAsync(
		string taskDescription, int topK = 5, CancellationToken ct = default);
}
```

##### 5.3 Persistence Configuration
- `MemorySettings` configuration section with 11 new options
- Covers paths, auto-save intervals, compaction thresholds, backups, vector store
- Example environment variable overrides

##### 5.4 Testing Strategy for Persistence
- **Unit Tests:** JsonRouterMemoryStore, RouterMemory, Compaction
- **Integration Tests:** Persistence across restarts, vector store, concurrent writes
- Exit criteria clearly defined

##### 5.5 Migration Path
- 5 sub-phases (3.5a through 3.5e) with clear implementation order
- Explicit deliverables for each sub-phase

#### Updated Source File Map
Added Phase 3.5 row to the source file map:

| Phase 3.5 | Production Files | Test Files |
|-----------|-----------------|-----------|
| Router Memory Persistence | `src/AgenticRouter/Router/IRouterMemoryStore.cs`, `src/AgenticRouter/Router/JsonRouterMemoryStore.cs`, `src/AgenticRouter/Router/VectorStoreRouterMemoryStore.cs` | `src/AgenticRouter.Tests/Router/JsonRouterMemoryStoreTests.cs`, `src/AgenticRouter.Tests/Router/PersistenceRegressionTests.cs` |

#### Updated Configuration Section
Extended `appsettings.json` configuration:

```json
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
}
```

#### Expanded Risks & Mitigations
Added 5 new risks specific to memory persistence:
- **Memory Persistence Race Conditions** — Use locks + async saves
- **Memory File Corruption** — JSON schema validation + backup recovery
- **Memory Growth** — Automatic compaction to prevent unbounded disk usage
- **Vector Store Availability** — Optional with graceful degradation to JSON-only
- **Concurrent Load/Save** — Thread-safe access with SemaphoreSlim

---

### 2. New Documentation Files

#### docs/ROUTER_MEMORY_PERSISTENCE.md (2,200+ lines)

Comprehensive architecture guide covering:

**JSON File Storage:**
- Complete schema with all 10+ fields explained
- Load/Save/Compaction algorithms with full code examples
- Atomic file operations (temp file + atomic rename)
- Backup strategy with retention policy
- Configuration options table

**Schema Example:**
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
		"variance": 0.000875,
		"lastUpdated": "2025-01-15T14:31:55Z"
	  }
	}
  },
  "metadata": {
	"totalRoutingDecisions": 47,
	"uniqueDimensions": 3,
	"explorationRate": 0.15
  }
}
```

**Vector Store Integration:**
- 4 implementation options: In-Memory, Milvus, Weaviate, SQLite
- Detailed pros/cons for each approach
- Use cases and when to choose each
- Embedding strategy and semantic similarity algorithms
- Full code examples for vector store queries
- Integration patterns in routing decisions

**Testing Strategy:**
- Unit tests with code examples
- Integration tests for persistence across restarts
- Vector store tests if enabled
- Concurrent operation validation
- Example test code for all scenarios

**Performance Analysis:**
- Save performance (5-50ms non-blocking)
- Memory footprint (1-10MB typical)
- Compaction benefits and trade-offs
- Backup overhead minimization

**Disaster Recovery:**
- Backup file management
- Recovery from corrupted files
- Fallback strategies
- Complete recovery code examples
- Testing for unrecoverable states

**Integration Examples:**
- Load memory on startup (blocking)
- Save memory after observations (async)
- Periodic compaction (background service)
- Composition with dependency injection

#### docs/SYSTEM_PROXY_ARCHITECTURE.md (1,200+ lines)

[Previously created, referenced for context]
- System proxy interception pattern
- Architecture diagrams
- Request flow with routing decision injection
- Configuration with proxy settings
- Deployment scenarios

#### docs/MEMORY_PERSISTENCE_PLAN_SUMMARY.md (New Summary)

Executive summary of memory persistence plan:
- Changes made to PLAN.md
- New documentation files
- Architecture summary with data flow diagrams
- Configuration examples (dev, production, environment)
- Benefits listing
- Integration with other phases
- Next actions checklist

---

## Key Features

### JSON Storage
✅ **Portable:** Human-readable JSON format  
✅ **No External Dependencies:** Standalone JSON file  
✅ **Atomic Operations:** Prevents corruption via temp files  
✅ **Automatic Backups:** Timestamped backup files with retention policy  
✅ **Schema Versioning:** Version field for backward compatibility  
✅ **Compaction:** Automatic score summarization prevents disk bloat  

### Vector Store (Optional)
✅ **Pluggable:** Interface-based abstraction  
✅ **Multiple Backends:** Milvus, Weaviate, SQLite, in-memory  
✅ **Semantic Search:** Find similar tasks and their best models  
✅ **Graceful Degradation:** Optional — works with JSON-only if unavailable  
✅ **Production Ready:** Milvus for scaled deployments  

### Persistence Design
✅ **Non-Blocking:** Async save doesn't block routing  
✅ **Thread-Safe:** Locks protect concurrent access  
✅ **Recovery:** Fallback to backups on corruption  
✅ **Observable:** Complete audit trail of decisions  
✅ **Configurable:** All settings via appsettings.json  

---

## Architecture Diagram

```
┌─────────────────────────────────────┐
│  IDE Extensions / Applications      │
│  (GitHub Copilot, VS Code, etc)     │
└────────────┬────────────────────────┘
			 │ Routing Request
			 ▼
┌─────────────────────────────────────┐
│  ACRouter (Phase 3)                 │
│  ├─ Query in-memory cache           │
│  ├─ (Optional) Vector similarity    │
│  └─ Return best model               │
└────────┬───────────────┬────────────┘
		 │               │
	┌────▼──────┐   ┌────▼────────────┐
	│  Phase 3.5│   │  Phase 5        │
	│  Memory   │   │  System Proxy   │
	│  (Router) │   │  (Interception) │
	└────┬──────┘   └────┬────────────┘
		 │                │
	┌────▼─────────┐     │
	│  JSON Store  │     │
	│ (Primary)    │     │
	└──────────────┘     │
						 ▼
				  ┌─────────────────┐
				  │  Provider APIs  │
				  │ (OpenAI, etc.)  │
				  └─────────────────┘
		 │
	Observe Outcome
		 │
	┌────▼──────────────────────────────┐
	│  Update Memory + Vector Store     │
	│  ├─ Async save to JSON            │
	│  ├─ (Optional) Update embeddings  │
	│  └─ Log decision + score          │
	└─────────────────────────────────────┘
```

---

## Configuration Examples

### Development (JSON Only)
```json
{
  "MemorySettings": {
	"PersistencePath": "./data",
	"JsonMemoryFile": "router_memory.json",
	"AutoSaveIntervalMs": 5000,
	"VectorStoreEnabled": false,
	"EnableBackups": true
  }
}
```

### Production (JSON + Milvus)
```json
{
  "MemorySettings": {
	"PersistencePath": "/var/lib/acrouter/memory",
	"JsonMemoryFile": "router_memory.json",
	"AutoSaveIntervalMs": 2000,
	"VectorStoreEnabled": true,
	"VectorStoreType": "Milvus",
	"VectorStoreConnection": "milvus.prod.example.com:19530",
	"CompactIntervalHours": 12,
	"BackupRetentionDays": 30
  }
}
```

---

## Testing Strategy

### Unit Tests (6 test classes)
- `JsonRouterMemoryStoreTests` — Load, save, compaction, backup behavior
- `RouterMemoryTests` — In-memory cache, async patterns, no data loss
- `MemoryCompactionTests` — Score summarization, old data pruning
- Additional coverage for vector store (if enabled)

### Integration Tests (3 test classes)
- `PersistenceRegressionTests` — Memory survives application restart
- `VectorStoreIntegrationTests` — Semantic similarity queries
- `ConcurrentWriteTests` — No data loss under concurrent operations

**Exit Criteria:**
- Memory persists across restarts
- Compaction works without data loss
- No corruption on normal or abnormal shutdown
- Concurrent operations are thread-safe

---

## Files Updated/Created

### Updated Files
- **PLAN.md** — 362 lines total (was ~180 lines)
  - Added Phase 3.5 with 5 sub-phases
  - Updated source file map
  - Extended configuration section
  - Expanded risks & mitigations

### New Documentation Files
- **docs/ROUTER_MEMORY_PERSISTENCE.md** — 2,200+ lines
  - Complete persistence architecture guide
  - JSON schema, vector store options, testing strategy
  - Code examples, performance analysis, disaster recovery

- **docs/SYSTEM_PROXY_ARCHITECTURE.md** — 1,200+ lines
  - System proxy interception pattern (created earlier)
  - Architecture, request flow, deployment scenarios

- **docs/MEMORY_PERSISTENCE_PLAN_SUMMARY.md** — Executive summary
  - Overview of changes, architecture diagrams
  - Configuration examples, integration guide

---

## Integration with Other Phases

```
Phase 3     : Core Router Logic
	↓
Phase 3.5   : Router Memory Persistence ← NEW
	↓
Phase 4     : Tooling and Evaluation Services
	↓
Phase 5     : System Proxy and IDE Integration
	│       (calls ObserveAsync after each request)
	↓
Phase 6     : Demo and Workflow Migration
	↓
Phase 7     : Integration and Regression Validation
	│       (verifies memory persists across restarts)
	↓
Release
```

---

## Next Implementation Steps

**Phase 3.5a:** Implement `IRouterMemoryStore` interface
- Define load/save/compact/search contracts
- Create in-memory test implementation

**Phase 3.5b:** Implement `JsonRouterMemoryStore`
- Full load/save with atomic operations
- Backup creation and cleanup
- Recovery from corrupted files

**Phase 3.5c:** Integrate into `RouterMemory`
- In-memory cache facade
- Async save-on-observe pattern
- Thread-safe updates with SemaphoreSlim

**Phase 3.5d:** Implement vector store abstraction (optional)
- `IVectorStoreRouterMemoryStore` interface
- Milvus/Weaviate/SQLite implementations
- Graceful degradation if unavailable

**Phase 3.5e:** Add comprehensive tests
- Unit tests for all storage operations
- Integration tests for persistence across restarts
- Concurrent operation validation

---

## Summary

The plan now **explicitly documents persistent router memory** as a core architectural requirement with:

✅ **Dual-layer storage:** JSON (primary) + optional vector store  
✅ **Production-ready:** Atomic operations, backups, recovery  
✅ **Performant:** Non-blocking async saves, automatic compaction  
✅ **Flexible:** Multiple vector store options or JSON-only  
✅ **Well-tested:** Comprehensive unit and integration tests  
✅ **Observable:** Full audit trail of routing decisions  

This enables the router to learn across sessions and improve its routing decisions over time, a core requirement for the agent-as-a-router architecture.
