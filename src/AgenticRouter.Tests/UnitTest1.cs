using AgenticRouter;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using Microsoft.SemanticKernel;

namespace AgenticRouter.Tests;

public class UnitTest1
{
    [Fact]
    public void Phase0Inventory_IncludesCoreRouterAndDemoSurfaces()
    {
        var sourcePaths = Phase0Discovery.SurfaceAreas.Select(item => item.SourcePath).ToHashSet(StringComparer.OrdinalIgnoreCase);

        Assert.Contains("src/routing/AGENT_ROUTER.py", sourcePaths);
        Assert.Contains("src/routing/evaluator.py", sourcePaths);
        Assert.Contains("demos/api_coding_solver/solve.py", sourcePaths);
        Assert.Contains("tests/test_demos.py", sourcePaths);
    }

    [Fact]
    public void Phase0Constraints_CaptureCurrentBenchmarkBoundary()
    {
        var constraintsText = string.Join("\n", Phase0Discovery.Constraints.Select(item => item.Detail));

        Assert.Contains("OOD176", constraintsText, StringComparison.Ordinal);
        Assert.Contains("legacy", constraintsText, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("9,999 ID tasks x 8 models", constraintsText, StringComparison.Ordinal);
    }

    [Fact]
    public void Phase0Expectations_MatchCheckedInReleaseSummary()
    {
        var idExpectation = Phase0Discovery.Expectations.Single(item => item.Split == "ID");
        var oodExpectation = Phase0Discovery.Expectations.Single(item => item.Split == "OOD");

        Assert.Equal(2919, idExpectation.TaskCount);
        Assert.Equal(50.14m, idExpectation.AveragePerformance);
        Assert.Equal(202.0m, idExpectation.CumulativeRegret);

        Assert.Equal(112, oodExpectation.TaskCount);
        Assert.Equal(66.96m, oodExpectation.AveragePerformance);
        Assert.Contains("verify-and-escalate", oodExpectation.Notes, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Phase1BuildHost_RegistersOptionsAndCoreServices()
    {
        using var host = Phase1Infrastructure.BuildHost([]);

        var options = host.Services.GetRequiredService<IOptions<Phase1Options>>().Value;
        var kernel = host.Services.GetRequiredService<Kernel>();
        var startupProbe = host.Services.GetRequiredService<Phase1StartupProbe>();

        Assert.Equal("AgenticRouter", options.ApplicationName);
        Assert.Equal("kimi-k2.5", options.DefaultCandidateModel);
        Assert.Equal(10, options.MaxNeighborCount);
        Assert.NotNull(kernel);
        Assert.NotNull(startupProbe);
    }

    [Fact]
    public void Phase1BuildHost_BindsConfigurationOverrides()
    {
        var overrides = new Dictionary<string, string?>
        {
            [$"{Phase1Options.SectionName}:ApplicationName"] = "AgenticRouter.Tests",
            [$"{Phase1Options.SectionName}:DefaultCandidateModel"] = "glm-5",
            [$"{Phase1Options.SectionName}:MaxNeighborCount"] = "12",
            [$"{Phase1Options.SectionName}:EnablePhase0Summary"] = "false"
        };

        using var host = Phase1Infrastructure.BuildHost([], overrides);
        var options = host.Services.GetRequiredService<IOptions<Phase1Options>>().Value;

        Assert.Equal("AgenticRouter.Tests", options.ApplicationName);
        Assert.Equal("glm-5", options.DefaultCandidateModel);
        Assert.Equal(12, options.MaxNeighborCount);
        Assert.False(options.EnablePhase0Summary);
    }
}
