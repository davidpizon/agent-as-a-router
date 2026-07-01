using AgenticRouter.Proxy;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using System.Net.Sockets;

namespace AgenticRouter.Tests.Proxy;

/// <summary>
/// Covers lifecycle behavior for <see cref="ProxyServer"/>.
/// </summary>
[Collection("ProxyLifecycle")]
public class ProxyServerTests
{
    [Fact]
    public async Task ProxyServer_Starts_AcceptsConnection_AndStops()
    {
        var services = new ServiceCollection();
        services.AddSingleton<ILogger<ProxyServer>>(new NullLogger<ProxyServer>());
        services.AddSingleton<ILogger<ProxyMiddleware>>(new NullLogger<ProxyMiddleware>());
        services.AddSingleton<ILogger<RequestInterceptor>>(new NullLogger<RequestInterceptor>());
        services.AddSingleton<RequestInterceptor>();
        services.AddTransient<ProxyMiddleware>();

        var server = new ProxyServer(new NullLogger<ProxyServer>(), services);

        await server.StartAsync(CancellationToken.None);

        using var tcpClient = new TcpClient();
        await tcpClient.ConnectAsync("127.0.0.1", 5001);

        Assert.True(tcpClient.Connected);

        using var stopCts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        await server.StopAsync(stopCts.Token);
    }
}
