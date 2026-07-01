using AgenticRouter.Proxy;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

namespace AgenticRouter.Tests.Proxy
{
    public class ProxyServerTests
    {
        [Fact]
        public async Task ProxyServer_StartsAndStops()
        {
            // Arrange
            var services = new ServiceCollection();
            services.AddSingleton<ILogger<ProxyServer>>(new NullLogger<ProxyServer>());
            services.AddSingleton<ILogger<ProxyMiddleware>>(new NullLogger<ProxyMiddleware>());
            services.AddSingleton<ILogger<RequestInterceptor>>(new NullLogger<RequestInterceptor>());
            services.AddSingleton<RequestInterceptor>();
            services.AddTransient<ProxyMiddleware>();

            var logger = new NullLogger<ProxyServer>();
            var server = new ProxyServer(logger, services);
            var cancellationTokenSource = new CancellationTokenSource(100); // Stop after 100ms

            // Act
            await server.StartAsync(CancellationToken.None);
            await server.StopAsync(cancellationTokenSource.Token);

            // Assert
            // Test passes if no exceptions are thrown.
        }
    }
}
