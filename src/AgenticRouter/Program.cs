using System.ComponentModel.DataAnnotations;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Microsoft.SemanticKernel;

namespace AgenticRouter;

/// <summary>
/// Application entrypoint for the AgenticRouter console host.
/// </summary>
internal static class Program
{
    /// <summary>
    /// Starts the host and prints startup diagnostics.
    /// </summary>
    /// <param name="args">Command-line arguments for host configuration.</param>
    private static void Main(string[] args)
    {
        using var host = Phase1Infrastructure.BuildHost(args);
        var startupProbe = host.Services.GetRequiredService<Phase1StartupProbe>();

        Console.WriteLine(startupProbe.BuildSummary());
    }
}

/// <summary>
/// Builds the DI host and configures phase-1 infrastructure services.
/// </summary>
public static class Phase1Infrastructure
{
    /// <summary>
    /// Builds and returns a configured host instance.
    /// </summary>
    /// <param name="args">Command-line arguments passed to the host builder.</param>
    /// <param name="overrides">Optional in-memory configuration overrides used by tests and local scenarios.</param>
    /// <returns>A configured host instance with routing-related startup services.</returns>
    public static IHost BuildHost(string[] args, IReadOnlyDictionary<string, string?>? overrides = null)
    {
        var builder = Host.CreateApplicationBuilder(args);

        builder.Configuration.AddInMemoryCollection(new Dictionary<string, string?>
        {
            [$"{Phase1Options.SectionName}:ApplicationName"] = "AgenticRouter",
            [$"{Phase1Options.SectionName}:EnablePhase0Summary"] = "true",
            [$"{Phase1Options.SectionName}:DefaultCandidateModel"] = "kimi-k2.5",
            [$"{Phase1Options.SectionName}:MaxNeighborCount"] = "10"
        });

        if (overrides is not null)
        {
            builder.Configuration.AddInMemoryCollection(overrides);
        }

        builder.Logging.ClearProviders();
        builder.Logging.AddSimpleConsole(options =>
        {
            options.SingleLine = true;
            options.TimestampFormat = "HH:mm:ss ";
        });

        builder.Services
            .AddOptions<Phase1Options>()
            .Bind(builder.Configuration.GetSection(Phase1Options.SectionName))
            .ValidateDataAnnotations()
            .Validate(options => options.MaxNeighborCount > 0, "MaxNeighborCount must be greater than zero.")
            .ValidateOnStart();

        builder.Services.AddSingleton(_ => new Kernel());
        builder.Services.AddSingleton<RoslynEnvironmentProbe>();
        builder.Services.AddSingleton<Phase1StartupProbe>();

        return builder.Build();
    }
}

/// <summary>
/// Defines phase-1 startup options bound from configuration.
/// </summary>
public sealed class Phase1Options
{
    /// <summary>
    /// Gets the configuration section name for phase-1 options.
    /// </summary>
    public const string SectionName = "Phase1";

    /// <summary>
    /// Gets the application display name.
    /// </summary>
    [Required]
    public string ApplicationName { get; init; } = "AgenticRouter";

    /// <summary>
    /// Gets a value indicating whether phase-0 summary information is included in startup output.
    /// </summary>
    public bool EnablePhase0Summary { get; init; } = true;

    /// <summary>
    /// Gets the default candidate model identifier.
    /// </summary>
    [Required]
    public string DefaultCandidateModel { get; init; } = "kimi-k2.5";

    /// <summary>
    /// Gets the configured memory neighbor retrieval limit.
    /// </summary>
    [Range(1, 100)]
    public int MaxNeighborCount { get; init; } = 10;
}

/// <summary>
/// Provides Roslyn environment metadata used by startup diagnostics.
/// </summary>
public sealed class RoslynEnvironmentProbe
{
    /// <summary>
    /// Gets the Roslyn language version string used by the runtime probe.
    /// </summary>
    public string RoslynLanguageVersion { get; } = LanguageVersion.Preview.ToDisplayString();
}

/// <summary>
/// Builds a textual startup summary of configured phase-1 services and options.
/// </summary>
/// <param name="options">Phase-1 options accessor.</param>
/// <param name="roslynProbe">Roslyn environment probe service.</param>
/// <param name="kernel">Semantic Kernel singleton service.</param>
public sealed class Phase1StartupProbe(
    IOptions<Phase1Options> options,
    RoslynEnvironmentProbe roslynProbe,
    Kernel kernel)
{
    /// <summary>
    /// Composes the startup summary text shown by the console app.
    /// </summary>
    /// <returns>A multi-line startup summary string.</returns>
    public string BuildSummary()
    {
        var activeOptions = options.Value;
        var lines = new List<string>
        {
            "Phase 1 complete: solution and infrastructure foundation initialized.",
            $"- App name: {activeOptions.ApplicationName}",
            $"- Default candidate model: {activeOptions.DefaultCandidateModel}",
            $"- Max neighbor count: {activeOptions.MaxNeighborCount}",
            $"- Roslyn language probe: {roslynProbe.RoslynLanguageVersion}",
            $"- Semantic Kernel service: {kernel.GetType().Name}"
        };

        if (activeOptions.EnablePhase0Summary)
        {
            lines.Add(Phase0Discovery.BuildSummary());
        }

        return string.Join(Environment.NewLine, lines);
    }
}

/// <summary>
/// Contains phase-0 discovery artifacts for mapping and benchmark constraints.
/// </summary>
public static class Phase0Discovery
{
    /// <summary>
    /// Represents a Python source surface mapped to its target C# location.
    /// </summary>
    /// <param name="SourcePath">Original Python path.</param>
    /// <param name="Category">Mapped capability category.</param>
    /// <param name="TargetPath">Target C# path.</param>
    public sealed record SurfaceArea(string SourcePath, string Category, string TargetPath);

    /// <summary>
    /// Represents a repository-level migration constraint.
    /// </summary>
    /// <param name="Name">Constraint name.</param>
    /// <param name="Detail">Constraint detail text.</param>
    public sealed record RepositoryConstraint(string Name, string Detail);

    /// <summary>
    /// Represents a benchmark expectation captured during migration discovery.
    /// </summary>
    /// <param name="Split">Benchmark split name.</param>
    /// <param name="TaskCount">Task count in the split.</param>
    /// <param name="AveragePerformance">Average performance value for the split.</param>
    /// <param name="CumulativeRegret">Cumulative regret value for the split.</param>
    /// <param name="TotalCost">Total reported cost for the split.</param>
    /// <param name="PerformancePerDollar">Performance-per-dollar metric.</param>
    /// <param name="Notes">Additional benchmark notes.</param>
    public sealed record BenchmarkExpectation(
        string Split,
        int TaskCount,
        decimal AveragePerformance,
        decimal CumulativeRegret,
        decimal TotalCost,
        decimal PerformancePerDollar,
        string Notes);

    /// <summary>
    /// Gets the discovered source-to-target migration surface list.
    /// </summary>
    public static IReadOnlyList<SurfaceArea> SurfaceAreas { get; } =
    [
        new("src/routing/AGENT_ROUTER.py", "Core router", "src/AgenticRouter/Router/AgentAsARouter.cs"),
        new("src/routing/base.py", "Core router", "src/AgenticRouter/Router/IRouterModelClient.cs"),
        new("src/routing/data_manager.py", "Data access", "src/AgenticRouter/Router/RouterMemory.cs"),
        new("src/routing/evaluator.py", "Evaluation tooling", "src/AgenticRouter/Tools/EstimateQuality.cs"),
        new("src/routing/stubs.py", "Tooling", "src/AgenticRouter/Tools/RunVisibleTests.cs"),
        new("src/routing/prompts.py", "Prompt contracts", "src/AgenticRouter/Models/RouterConstants.cs"),
        new("src/routing/baselines.py", "Baselines", "src/AgenticRouter/Router/AgentAsARouter.cs"),
        new("src/routing/trained_routers.py", "Trained policy", "src/AgenticRouter/Router/AgentAsARouter.cs"),
        new("src/routing/routellm_baselines.py", "RouteLLM baselines", "src/AgenticRouter/Router/AgentAsARouter.cs"),
        new("src/routing/cascade_router.py", "Cascade policy", "src/AgenticRouter/Router/AgentAsARouter.cs"),
        new("src/acrouter_repro/id_repro.py", "ID reproduction", "src/AgenticRouter/Program.cs"),
        new("src/acrouter_repro/ood_repro.py", "OOD reproduction", "src/AgenticRouter/Program.cs"),
        new("demos/api_coding_solver/solve.py", "Demo", "src/AgenticRouter/Program.cs"),
        new("demos/commercial_cli_router/router_mvp.py", "Demo", "src/AgenticRouter/Program.cs"),
        new("tests/test_inference_api.py", "Python tests", "src/AgenticRouter.Tests/Router/AgentAsARouterTests.cs"),
        new("tests/test_sandbox_verifier.py", "Python tests", "src/AgenticRouter.Tests/Tools/RunVisibleTestsTests.cs"),
        new("tests/test_custom_pipeline.py", "Python tests", "src/AgenticRouter.Tests/Integration/RouterCompositionTests.cs"),
        new("tests/test_demos.py", "Python tests", "src/AgenticRouter.Tests/ProgramTests.cs")
    ];

    /// <summary>
    /// Gets discovered repository constraints used by the migration plan.
    /// </summary>
    public static IReadOnlyList<RepositoryConstraint> Constraints { get; } =
    [
        new("Self-contained release", "Benchmark replay should run without live API keys or external model calls."),
        new("Current public OOD benchmark", "OOD176 is the active benchmark stream; OOD112/SWE-MiniSandbox remains legacy-only."),
        new("Canonical benchmark tables", "Data includes 9,999 ID tasks x 8 models and 176 OOD tasks x 8 models in long-form CSV."),
        new("Reference reproductions", "Primary Python reproduction commands are scripts/run_id.py, scripts/run_acrouter_ood176.py, and scripts/run_baselines_ood176.py.")
    ];

    /// <summary>
    /// Gets benchmark expectations captured from checked-in summary artifacts.
    /// </summary>
    public static IReadOnlyList<BenchmarkExpectation> Expectations { get; } =
    [
        new("ID", 2919, 50.14m, 202.0m, 22.31m, 2.25m, "policy=hierarchical; tune=train+val; eval=test; leakage=none"),
        new("OOD", 112, 66.96m, 13.7m, 63.43m, 1.06m, "k=2 verify-and-escalate cascade: MiniMax -> Kimi -> GPT-5.4 -> GLM-5, then Opus")
    ];

    /// <summary>
    /// Builds a concise phase-0 discovery summary.
    /// </summary>
    /// <returns>A multi-line summary string.</returns>
    public static string BuildSummary()
    {
        var lines = new List<string>
        {
            "Phase 0 complete: discovery and repository mapping captured.",
            $"- Surface areas inventoried: {SurfaceAreas.Count}",
            $"- Repository constraints captured: {Constraints.Count}",
            $"- Benchmark expectations captured: {Expectations.Count}"
        };

        return string.Join(Environment.NewLine, lines);
    }
}
