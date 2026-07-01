# Plan Update Summary: Router Memory Persistence

## Changes Made

### 1. PLAN.md Updated

#### New Phase 3.5: Router Memory Persistence (JSON + Optional Vector Store)
Added a complete new phase between Core Router Logic (Phase 3) and Tooling (Phase 4):

**Purpose:** Enable router learning across sessions by persisting memory to disk and optionally to a vector database for semantic similarity queries.

**Key Components:**
- **Layer 1: JSON File (Always Enabled)** - Primary persistent storage
  - Structured JSON document with dimension → model → scores history
  - Default path: `./router_memory.json`
  - Includes version, metadata, and per-model statistics

- **Layer 2: Vector Store (Optional)** - Enhanced semantic retrieval
  - Options: In-Memory, Milvus, Weaviate, or SQLite
  - Enables queries like "find models for tasks similar to this one"
  - Configurable via `VectorStoreEnabled` flag

**Implementation Files (new source map entries):**
- `src/AgenticRouter/Router/IRouterMemoryStore.cs` - Storage interface
- `src/AgenticRouter/Router/JsonRouterMemoryStore.cs` - JSON implementation
- `src/AgenticRouter/Router/VectorStoreRouterMemoryStore.cs` - Optional vector DB
- Test files with comprehensive coverage

**Sub-phases (3.5a - 3.5e):**
1. Implement IRouterMemoryStore interface + JsonRouterMemoryStore
2. Integrate into RouterMemory with async save
3. Add JSON schema validation and backup logic
4. (Optional) Implement vector store abstraction + Milvus/Weaviate integration
5. Add persistence tests and load/save verification

#### Updated Configuration (appsettings.json)
Added new `MemorySettings` section with:
- `PersistencePath` - Directory for memory files (default: ./data)
- `JsonMemoryFile` - Filename (default: router_memory.json)
- `AutoSaveIntervalMs` - Periodic save interval (default: 5000ms)
- `CompactThresholdScoresPerModel` - When to compact (default: 100)
- `CompactIntervalHours` - Compaction frequency (default: 24)
- `EnableBackups` - Create timestamped backups (default: true)
- `BackupRetentionDays` - How long to keep backups (default: 7)
- `VectorStoreEnabled` - Optional vector store (default: false)
- `VectorStoreType` - Backend type (Milvus/Weaviate/SQLite)
- `VectorStoreConnection` - Connection string
- `EmbeddingDimension` - Vector size (default: 768)
- `VectorStoreTopK` - Results to retrieve (default: 5)

#### Expanded Risks & Mitigations
Added new risks specific to memory persistence:
- **Memory Persistence Race Conditions** - Use locks and async saves
- **Memory File Corruption** - JSON schema validation with recovery from backups
- **Memory Growth** - Automatic compaction to prevent unbounded disk usage
- **Vector Store Availability** - Optional with graceful degradation
- **Concurrent Load/Save** - Thread-safe access with SemaphoreSlim

#### Updated Phase Numbering
- Phase 3.5: Router Memory Persistence (NEW)
- Phase 4: Tooling and Evaluation Services (was Phase 4)
- Phase 5: System Proxy and IDE Integration (was Phase 5)
- Phase 6: Demo and Workflow Migration (was Phase 6)
- Phase 7: Integration and Regression Validation (was Phase 7)

### 2. New Documentation Files

#### docs/ROUTER_MEMORY_PERSISTENCE.md (Comprehensive Guide)
Detailed architecture document covering:

**JSON File Storage:**
- Complete schema with all fields explained
- Load/Save/Compaction operations with code examples
- Atomic file operations (temp file + rename)
- Backup strategy and rotation
- Configuration options

**Vector Store Integration:**
- Four implementation options compared (In-Memory, Milvus, Weaviate, SQLite)
- Use cases for each approach
- Embedding strategy and semantic similarity queries
- Integration examples in routing logic

**Testing Strategy:**
- Unit tests for JsonRouterMemoryStore
- RouterMemory concurrent operation tests
- Integration tests for persistence across restarts
- Example test code for all scenarios

**Performance Considerations:**
- Save performance (5-50ms non-blocking)
- Memory footprint (~1-10MB for typical router)
- Compaction benefits
- Backup overhead minimization

**Disaster Recovery:**
- Backup file management and rotation
- Recovery from corrupted files
- Fallback to empty memory if needed
- Complete recovery code examples

**Next Steps:**
- Implementation roadmap with file structure
- Integration with router lifecycle
- Periodic compaction as background service
- Configuration binding via Options Pattern

## Architecture Summary

### Storage Layers

```
┌─────────────────────────────────────────────────────┐
│  Application/Router                                 │
│  (in-memory RouterMemory cache)                     │
└────────────┬────────────────────────────────────────┘
			 │
	  ┌──────▼──────────────────────┐
	  │  IRouterMemoryStore          │
	  │  (abstraction layer)         │
	  └──┬───────────────┬───────────┘
		 │               │
	┌────▼─────┐    ┌────▼──────────────────┐
	│   JSON    │    │   Vector Store       │
	│  (Always) │    │   (Optional)         │
	├───────────┤    ├──────────────────────┤
	│ Primary   │    │ In-Memory / Milvus / │
	│ storage   │    │ Weaviate / SQLite    │
	│ on disk   │    │                      │
	│ portable  │    │ Semantic search      │
	│ human-    │    │ similarity queries   │
	│ readable  │    │                      │
	└───────────┘    └──────────────────────┘
```

### Data Flow

```
1. Route Request
   └─> ACRouter.Route(task)
	   ├─ Query in-memory cache
	   ├─ (Optional) Query vector store for similar tasks
	   └─> Return best model

2. Observe Outcome
   └─> RouterMemory.ObserveAsync(dimension, model, score)
	   ├─ Update in-memory cache (fast)
	   ├─ Trigger async save to JSON (non-blocking)
	   └─ Record metric

3. Periodic Maintenance
   └─> MemoryCompactionHostedService
	   └─ Every 24 hours:
		   ├─ Load memory
		   ├─ Compact scores (keep last 100 per model)
		   └─ Save and backup
```

## Configuration Examples

### Development (JSON only)
```json
{
  "MemorySettings": {
	"VectorStoreEnabled": false,
	"AutoSaveIntervalMs": 5000,
	"EnableBackups": true
  }
}
```

### Production (JSON + Milvus)
```json
{
  "MemorySettings": {
	"VectorStoreEnabled": true,
	"VectorStoreType": "Milvus",
	"VectorStoreConnection": "milvus.prod.example.com:19530",
	"AutoSaveIntervalMs": 2000,
	"CompactIntervalHours": 12
  }
}
```

### Environment Override
```bash
export MEMORY_AUTO_SAVE_MS=1000
export VECTOR_STORE_ENABLED=true
export VECTOR_STORE_TYPE=Milvus
```

## Benefits

✅ **Persistent Learning:** Router memory survives application restarts  
✅ **Portable:** JSON format is human-readable and easy to transport  
✅ **Scalable:** Compaction prevents unbounded disk growth  
✅ **Optional Vector Store:** Advanced semantic routing without mandatory external dependency  
✅ **Backup & Recovery:** Automatic backups with recovery mechanism  
✅ **Non-blocking:** Async saves don't block routing decisions  
✅ **Observable:** Full audit trail of routing decisions and observations  
✅ **Testable:** Comprehensive test coverage for all persistence operations  

## Integration with Other Phases

- **Phase 3:** Core Router Logic - Uses RouterMemory as source of truth
- **Phase 3.5:** Memory Persistence - NEW - Enables memory to survive restarts
- **Phase 5:** System Proxy - Calls ObserveAsync after each proxied request
- **Phase 7:** Integration Tests - Validates memory persists across restarts

## Next Actions

1. Implement `IRouterMemoryStore` interface
2. Implement `JsonRouterMemoryStore` with full load/save/compact logic
3. Integrate into `RouterMemory` with async save-on-observe
4. Add unit tests for all storage operations
5. (Optional) Implement vector store abstraction
6. Add integration tests for persistence across application restarts

## Files Modified

- **PLAN.md** - Complete plan with Phase 3.5 added, configuration updated, risks expanded
- **docs/ROUTER_MEMORY_PERSISTENCE.md** - NEW - Comprehensive architecture guide

## Files Created

- `docs/ROUTER_MEMORY_PERSISTENCE.md` - Detailed persistence architecture and implementation guide
