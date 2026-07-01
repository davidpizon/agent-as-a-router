using System.ComponentModel.DataAnnotations;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Microsoft.SemanticKernel;

namespace AgenticRouter;

internal static class Program
{
    private static void Main(string[] args)
    {
        using var host = Phase1Infrastructure.BuildHost(args);
        var startupProbe = host.Services.GetRequiredService<Phase1StartupProbe>();

        Console.WriteLine(startupProbe.BuildSummary());
    }
}

public static class Phase1Infrastructure
{
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

public sealed class Phase1Options
{
    public const string SectionName = "Phase1";

    [Required]
    public string ApplicationName { get; init; } = "AgenticRouter";

    public bool EnablePhase0Summary { get; init; } = true;

    [Required]
    public string DefaultCandidateModel { get; init; } = "kimi-k2.5";

    [Range(1, 100)]
    public int MaxNeighborCount { get; init; } = 10;
}

public sealed class RoslynEnvironmentProbe
{
    public string RoslynLanguageVersion { get; } = LanguageVersion.Preview.ToDisplayString();
}

public sealed class Phase1StartupProbe(
    IOptions<Phase1Options> options,
    RoslynEnvironmentProbe roslynProbe,
    Kernel kernel)
{
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

public static class Phase0Discovery
{
    public sealed record SurfaceArea(string SourcePath, string Category, string TargetPath);

    public sealed record RepositoryConstraint(string Name, string Detail);

    public sealed record BenchmarkExpectation(
        string Split,
        int TaskCount,
        decimal AveragePerformance,
        decimal CumulativeRegret,
        decimal TotalCost,
        decimal PerformancePerDollar,
        string Notes);

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

    public static IReadOnlyList<RepositoryConstraint> Constraints { get; } =
    [
        new("Self-contained release", "Benchmark replay should run without live API keys or external model calls."),
        new("Current public OOD benchmark", "OOD176 is the active benchmark stream; OOD112/SWE-MiniSandbox remains legacy-only."),
        new("Canonical benchmark tables", "Data includes 9,999 ID tasks x 8 models and 176 OOD tasks x 8 models in long-form CSV."),
        new("Reference reproductions", "Primary Python reproduction commands are scripts/run_id.py, scripts/run_acrouter_ood176.py, and scripts/run_baselines_ood176.py.")
    ];

    public static IReadOnlyList<BenchmarkExpectation> Expectations { get; } =
    [
        new("ID", 2919, 50.14m, 202.0m, 22.31m, 2.25m, "policy=hierarchical; tune=train+val; eval=test; leakage=none"),
        new("OOD", 112, 66.96m, 13.7m, 63.43m, 1.06m, "k=2 verify-and-escalate cascade: MiniMax -> Kimi -> GPT-5.4 -> GLM-5, then Opus")
    ];

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
