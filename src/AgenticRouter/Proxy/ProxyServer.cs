using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using System.Threading;
using System.Threading.Tasks;

namespace AgenticRouter.Proxy
{
    /// <summary>
    /// Represents the proxy server, responsible for building and managing the Kestrel web host.
    /// </summary>
    public class ProxyServer
    {
        private readonly IHost _host;

        public ProxyServer(ILogger<ProxyServer> logger, IServiceCollection services)
        {
            _host = Host.CreateDefaultBuilder()
                .ConfigureWebHostDefaults(webBuilder =>
                {
                    webBuilder.UseKestrel(options =>
                    {
                        options.ListenLocalhost(5001);
                    });

                    webBuilder.ConfigureServices(s =>
                    {
                        foreach (var service in services)
                        {
                            s.Add(service);
                        }
                    });

                    webBuilder.Configure(app =>
                    {
                        app.UseMiddleware<ProxyMiddleware>();
                    });
                })
                .Build();
        }

        /// <summary>
        /// Starts the proxy server.
        /// </summary>
        public Task StartAsync(CancellationToken cancellationToken)
        {
            return _host.StartAsync(cancellationToken);
        }

        /// <summary>
        /// Stops the proxy server.
        /// </summary>
        public Task StopAsync(CancellationToken cancellationToken)
        {
            return _host.StopAsync(cancellationToken);
        }
    }
}
