using AgenticRouter.Proxy;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using System.Net.Sockets;

namespace AgenticRouter.Tests.Proxy;

/// <summary>
/// Covers lifecycle behavior for <see cref="ProxyServer"/>.
/// </summary>
[Collection("ProxyLifecycle")]
[Trait("Category", "Integration")]
public class ProxyServerTests
{
    [Fact]
    public async Task ProxyServer_Starts_AcceptsConnection_AndStops()
    {
        var interceptor = new RequestInterceptor(NullLogger<RequestInterceptor>.Instance, ModelRouteResolverTestFactory.Empty());
        var proxyMiddleware = new ProxyMiddleware(NullLogger<ProxyMiddleware>.Instance, interceptor);

        var server = new ProxyServer(new NullLogger<ProxyServer>(), proxyMiddleware);

        await server.StartAsync(CancellationToken.None);

        using var tcpClient = new TcpClient();
        await tcpClient.ConnectAsync("127.0.0.1", 5001);

        Assert.True(tcpClient.Connected);

        using var stopCts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        await server.StopAsync(stopCts.Token);
    }
}
