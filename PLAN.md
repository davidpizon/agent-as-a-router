# Implementation Plan: Converting Agent-as-a-Router to C#

This document outlines a phased, parity-first migration from the current Python implementation to a .NET 10 C# application. The conversion should cover the core router, shared models, tools, demos, and tests, and every phase should be validated with unit tests before integration-level verification.

## Guiding Principles
- Preserve current behavior first; refactor only after parity is proven.
- Use dependency injection, async/await, the options pattern, structured logging, nullable reference types, and analyzers.
- Keep public APIs small and explicit.
- Prefer deterministic, testable abstractions around model calls and tool execution.
- Validate each phase with unit tests before integration tests.

## Testing Strategy
- Start with unit tests for shared models, router decisions, tool helpers, and configuration binding.
- Keep unit tests deterministic by mocking external model calls, file system access, and Roslyn execution boundaries where practical.
- Add integration tests only after the unit-test layer is stable, then cover composition, end-to-end routing, and regression parity against Python baselines.
- Use test names and fixtures that clearly separate contract tests, behavior tests, and parity checks.

## Source File Map
| Phase | `src/AgenticRouter` files | `src/AgenticRouter.Tests` files |
| --- | --- | --- |
| Phase 0: Discovery and Repository Mapping | `src/AgenticRouter/Program.cs` | `src/AgenticRouter.Tests/UnitTest1.cs` |
| Phase 1: Solution and Infrastructure Foundation | `src/AgenticRouter/AgenticRouter.csproj`, `src/AgenticRouter/Program.cs` | `src/AgenticRouter.Tests/AgenticRouter.Tests.csproj`, `src/AgenticRouter.Tests/UnitTest1.cs` |
| Phase 2: Shared Models and Contracts | `src/AgenticRouter/Models/RoutingDecision.cs`, `src/AgenticRouter/Models/RoutingOptions.cs`, `src/AgenticRouter/Models/RouterConstants.cs` | `src/AgenticRouter.Tests/Models/RoutingDecisionTests.cs`, `src/AgenticRouter.Tests/Models/RoutingOptionsTests.cs` |
| Phase 3: Core Router Logic | `src/AgenticRouter/Router/AgentAsARouter.cs`, `src/AgenticRouter/Router/IRouterModelClient.cs`, `src/AgenticRouter/Router/RouterMemory.cs` | `src/AgenticRouter.Tests/Router/AgentAsARouterTests.cs`, `src/AgenticRouter.Tests/Router/RouterMemoryTests.cs` |
| Phase 4: Tooling and Evaluation Services | `src/AgenticRouter/Tools/CheckSyntax.cs`, `src/AgenticRouter/Tools/RunVisibleTests.cs`, `src/AgenticRouter/Tools/EstimateQuality.cs` | `src/AgenticRouter.Tests/Tools/CheckSyntaxTests.cs`, `src/AgenticRouter.Tests/Tools/RunVisibleTestsTests.cs`, `src/AgenticRouter.Tests/Tools/EstimateQualityTests.cs` |
| Phase 5: Demo and Workflow Migration | `src/AgenticRouter/Program.cs`, `src/AgenticRouter/Hosting/ServiceCollectionExtensions.cs` | `src/AgenticRouter.Tests/ProgramTests.cs`, `src/AgenticRouter.Tests/Hosting/ServiceCollectionExtensionsTests.cs` |
| Phase 6: Integration and Regression Validation | `src/AgenticRouter/Program.cs` | `src/AgenticRouter.Tests/Integration/RouterCompositionTests.cs`, `src/AgenticRouter.Tests/Integration/ParityRegressionTests.cs` |

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

## 5. Phase 4: Tooling and Evaluation Services
- Port syntax checks, quality scoring, and test execution helpers.
- Wrap Roslyn usage behind interfaces so the logic can be unit tested without live compilation where possible.
- Add unit tests for success paths, failure paths, and deterministic scoring.
- Exit criteria: tooling behavior is validated in isolation.

## 6. Phase 5: Demo and Workflow Migration
- Update the demos and CLI entrypoints to call the C# services.
- Keep configuration in appsettings and options classes rather than hard-coded constants.
- Preserve the current repository workflows while moving them onto the C# implementation.
- Exit criteria: demos run against the C# application with equivalent behavior.

## 7. Phase 6: Integration and Regression Validation
- Add integration tests for router, tool, and configuration composition.
- Compare representative outputs against Python baselines and documented benchmark expectations.
- Verify docs, samples, and generated outputs remain consistent.
- Exit criteria: parity is confirmed and the migration is ready for release.

## Risks & Mitigations
- **Roslyn Performance**: keep snippets minimal and cache reusable state where safe.
- **LLM Behavior Drift**: pin prompt contracts and compare outputs in regression tests.
- **Demo Compatibility**: migrate entrypoints incrementally and keep old behavior documented until parity is reached.

## References
- `docs/HANDBOOK.md` — repository scope, benchmark goals, and current reproduction commands.
- `data/README.md` — data layout and legacy/current benchmark boundaries.
- `outputs/current/summary.md` — current release summary and reference metrics.
- `src/AgenticRouter/AgenticRouter.csproj` and `src/AgenticRouter.Tests/AgenticRouter.Tests.csproj` — C# project boundaries for the migration.