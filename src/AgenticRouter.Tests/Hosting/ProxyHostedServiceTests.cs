using AgenticRouter.Hosting;
using AgenticRouter.Proxy;
using AgenticRouter.Tests.Proxy;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;

namespace AgenticRouter.Tests.Hosting;

/// <summary>
/// Covers hosted service lifecycle behavior for <see cref="ProxyHostedService"/>.
/// </summary>
[Collection("ProxyLifecycle")]
[Trait("Category", "Integration")]
public class ProxyHostedServiceTests
{
    [Fact(Skip = "Integration testing disabled")]
    public async Task StartAndStopAsync_StartsAndStopsProxy_AndLogsLifecycle()
    {
        var loggerMock = new Mock<ILogger<ProxyHostedService>>();
        var proxyLogger = new NullLogger<ProxyServer>();
        var services = new ServiceCollection();
        services.AddSingleton<ILogger<ProxyServer>>(proxyLogger);
        services.AddSingleton<ILogger<ProxyMiddleware>>(new NullLogger<ProxyMiddleware>());
        services.AddSingleton<ILogger<RequestInterceptor>>(new NullLogger<RequestInterceptor>());
        services.AddSingleton<IEnvironmentVariableProvider, EnvironmentVariableProvider>();
        services.AddSingleton<IModelRouteResolver>(ModelRouteResolverTestFactory.Empty());
        services.AddSingleton<RequestInterceptor>();
        services.AddTransient<ProxyMiddleware>();

        var hostedService = new ProxyHostedService(loggerMock.Object, proxyLogger, services);

        await hostedService.StartAsync(CancellationToken.None);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        await hostedService.StopAsync(cts.Token);

        VerifyLogContains(loggerMock, LogLevel.Information, "Proxy Hosted Service is starting.");
        VerifyLogContains(loggerMock, LogLevel.Information, "Proxy Hosted Service is stopping.");
    }

    private static void VerifyLogContains(Mock<ILogger<ProxyHostedService>> loggerMock, LogLevel level, string expectedText)
    {
        loggerMock.Verify(
            logger => logger.Log(
                level,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((state, _) => state.ToString()!.Contains(expectedText, StringComparison.Ordinal)),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Once);
    }
}
