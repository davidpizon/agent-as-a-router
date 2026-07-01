using AgenticRouter.Models;
using AgenticRouter.Router;
using AgenticRouter.Services;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Serilog;

namespace AgenticRouter;

/// <summary>
/// Application entrypoint for the AgenticRouter console host.
/// </summary>
internal static class Program
{
    /// <summary>
    /// Main entry point for the application.
    /// </summary>
    /// <param name="args">Command-line arguments.</param>
    /// <returns>A task that represents the asynchronous operation.</returns>
    public static async Task Main(string[] args)
    {
        Log.Logger = new LoggerConfiguration()
            .MinimumLevel.Debug()
            .WriteTo.Console()
            .CreateBootstrapLogger();

        try
        {
            var host = CreateHostBuilder(args).Build();
            Log.Information("AgenticRouter host created.");
            await host.RunAsync();
        }
        catch (Exception ex)
        {
            Log.Fatal(ex, "AgenticRouter host terminated unexpectedly.");
        }
        finally
        {
            await Log.CloseAndFlushAsync();
        }
    }

    /// <summary>
    /// Creates the host builder.
    /// </summary>
    /// <param name="args">Command-line arguments.</param>
    /// <returns>An <see cref="IHostBuilder"/>.</returns>
    public static IHostBuilder CreateHostBuilder(string[] args) =>
        Host.CreateDefaultBuilder(args)
            .UseSerilog((context, services, loggerConfiguration) => loggerConfiguration
                .ReadFrom.Configuration(context.Configuration)
                .ReadFrom.Services(services)
                .Enrich.FromLogContext()
                .WriteTo.Console())
            .ConfigureServices((hostContext, services) =>
            {
                // Configuration options can be bound here
                services.AddOptions<RoutingOptions>()
                    .Bind(hostContext.Configuration.GetSection(RoutingOptions.SectionName))
                    .ValidateDataAnnotations()
                    .ValidateOnStart();

                // Add application services
                services.AddSingleton<RouterMemory>();
                services.AddSingleton<IRouterModelClient, MockRouterModelClient>(); // Using a mock for now
                services.AddSingleton<AgentAsARouter>();
                services.AddHostedService<Worker>();
            });
}

// A mock implementation of IRouterModelClient for demonstration purposes.
// This would be replaced with a real implementation that calls an LLM.
public class MockRouterModelClient : IRouterModelClient
{
    public Task<string> GetResponseAsync(string model, string prompt, CancellationToken cancellationToken = default)
    {
        return Task.FromResult($"Mock response from {model} for prompt: '{prompt}'");
    }
}
