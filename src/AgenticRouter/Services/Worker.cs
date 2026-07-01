using AgenticRouter.Models;
using AgenticRouter.Router;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace AgenticRouter.Services;

/// <summary>
/// A background service that demonstrates the loading and validation of routing options.
/// </summary>
public class Worker : BackgroundService
{
    private readonly ILogger<Worker> _logger;
    private readonly AgentAsARouter _router;

    /// <summary>
    /// Initializes a new instance of the <see cref="Worker"/> class.
    /// </summary>
    /// <param name="logger">The logger.</param>
    /// <param name="router">The agent router.</param>
    public Worker(ILogger<Worker> logger, AgentAsARouter router)
    {
        _logger = logger;
        _router = router;
    }

    /// <summary>
    /// Executes the background service task.
    /// </summary>
    /// <param name="stoppingToken">The stopping token.</param>
    /// <returns>A task that represents the asynchronous operation.</returns>
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("AgenticRouter worker running.");

        // Simulate some routing decisions
        var prompt = "Write a C# function to sort a list of integers.";
        var dimension = "code_generation";

        // First route, likely explores or uses default
        var result1 = await _router.RouteAsync(prompt, dimension, stoppingToken);
        _logger.LogInformation("Decision 1: Chose {Model} with rationale: {Rationale}", result1.Decision.SelectedModel, result1.Decision.Rationale);
        _router.Observe(dimension, result1.Decision.SelectedModel, 0.9); // Simulate good response

        // Second route, should exploit the learned information
        var result2 = await _router.RouteAsync(prompt, dimension, stoppingToken);
        _logger.LogInformation("Decision 2: Chose {Model} with rationale: {Rationale}", result2.Decision.SelectedModel, result2.Decision.Rationale);
        _router.Observe(dimension, result2.Decision.SelectedModel, 0.95); // Simulate even better response

        // Explore a different dimension
        var result3 = await _router.RouteAsync("Translate 'hello' to French", "translation", stoppingToken);
        _logger.LogInformation("Decision 3: Chose {Model} with rationale: {Rationale}", result3.Decision.SelectedModel, result3.Decision.Rationale);
        _router.Observe("translation", result3.Decision.SelectedModel, 0.8);
    }
}
