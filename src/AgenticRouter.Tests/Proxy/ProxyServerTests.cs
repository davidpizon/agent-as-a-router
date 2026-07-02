using AgenticRouter.Proxy;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using System;
using System.Linq;
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

        var server = new ProxyServer(new NullLogger<ProxyServer>(), proxyMiddleware, port: 0);

        await server.StartAsync(CancellationToken.None);

        var boundPort = new Uri(server.Addresses.Single()).Port;

        using var tcpClient = new TcpClient();
        await tcpClient.ConnectAsync("127.0.0.1", boundPort);

        Assert.True(tcpClient.Connected);

        using var stopCts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        await server.StopAsync(stopCts.Token);
    }

    [Theory]
    [InlineData(-1)]
    [InlineData(65536)]
    public void Constructor_PortOutOfRange_ThrowsArgumentOutOfRangeException(int port)
    {
        var interceptor = new RequestInterceptor(NullLogger<RequestInterceptor>.Instance, ModelRouteResolverTestFactory.Empty());
        var proxyMiddleware = new ProxyMiddleware(NullLogger<ProxyMiddleware>.Instance, interceptor);

        Assert.Throws<ArgumentOutOfRangeException>(() => new ProxyServer(new NullLogger<ProxyServer>(), proxyMiddleware, port));
    }
}
