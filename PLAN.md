# Implementation Plan: Converting Agent-as-a-Router to C#

This document outlines the plan to port the Python "Agent-as-a-Router" core logic to a .NET 10 C# application.

## 1. Core Objectives
- Port `AgentAsARouter` core logic to C#.
- Use **Microsoft Semantic Kernel** for LLM orchestration.
- Support **C#** as the primary language for code evaluation.
- Implement **Roslyn Scripting** for dynamic test execution.

## 2. Technical Stack
- **Framework**: .NET 10
- **LLM SDK**: Microsoft.SemanticKernel
- **Code Analysis**: Microsoft.CodeAnalysis.CSharp
- **Code Execution**: Microsoft.CodeAnalysis.CSharp.Scripting

## 3. Component Mapping

| Python Component | C# Equivalent | Notes |
| :--- | :--- | :--- |
| `AgentAsARouter` class | `AgentAsARouter` class | Uses Semantic Kernel for its "Loop". |
| `AgentMemory` class | `AgentMemory` class | Stores quality scores in a Dictionary. |
| `check_syntax` | `Tools.CheckSyntax` | Uses Roslyn `CSharpSyntaxTree`. |
| `run_visible_tests` | `Tools.RunVisibleTests` | Uses Roslyn Scripting. |
| `estimate_quality` | `Tools.EstimateQuality` | Heuristics for C# structure. |
| `RoutingDecision` | `RoutingDecision` record | Data contract for routing results. |

## 4. Implementation Steps

1. **Dependency Integration**: Add necessary NuGet packages to `AgenticRouter.csproj`.
2. **Data Model Porting**: Implement `RoutingDecision`, `AgentMemory`, and model constants in `Models.cs`.
3. **Observation Tools**:
   - `CheckSyntax`: Verify C# code validity.
   - `RunVisibleTests`: Extract and run C# assertions from prompts.
   - `EstimateQuality`: Heuristic scoring for C# code.
4. **Router Implementation**:
   - Semantic Kernel setup for the router model.
   - Implementation of `Route` (Step) and `Observe` (Learn) methods.
   - Epsilon-greedy exploration logic.
5. **Demonstration**: Update `Program.cs` to show a sample routing loop.

## 5. Risks & Mitigations
- **Roslyn Performance**: Scripting can be slow; we will keep test snippets minimal.
- **LLM Compatibility**: Prompting might need adjustments for C#-specific context.
