using AgenticRouter.Proxy;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using System.Threading;
using System.Threading.Tasks;

namespace AgenticRouter.Hosting
{
    /// <summary>
    /// A hosted service that manages the lifecycle of the proxy server.
    /// </summary>
    public class ProxyHostedService : IHostedService
    {
        private readonly ILogger<ProxyHostedService> _logger;
        private readonly ProxyServer _proxyServer;

        public ProxyHostedService(ILogger<ProxyHostedService> logger, IServiceCollection services)
        {
            _logger = logger;
            // Manually create a logger for ProxyServer as it's not directly in the DI container for the main host.
            var serviceProvider = services.BuildServiceProvider();
            var proxyLogger = serviceProvider.GetRequiredService<ILogger<ProxyServer>>();
            _proxyServer = new ProxyServer(proxyLogger, services);
        }

        /// <summary>
        /// Starts the proxy server.
        /// </summary>
        public Task StartAsync(CancellationToken cancellationToken)
        {
            _logger.LogInformation("Proxy Hosted Service is starting.");
            return _proxyServer.StartAsync(cancellationToken);
        }

        /// <summary>
        /// Stops the proxy server.
        /// </summary>
        public Task StopAsync(CancellationToken cancellationToken)
        {
            _logger.LogInformation("Proxy Hosted Service is stopping.");
            return _proxyServer.StopAsync(cancellationToken);
        }
    }
}
