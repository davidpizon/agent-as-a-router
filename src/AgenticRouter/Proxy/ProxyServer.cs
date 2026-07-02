using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
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

        /// <summary>
        /// Initializes a new instance of the <see cref="ProxyServer"/> class.
        /// </summary>
        /// <param name="logger">The logger for this instance (currently unused by Kestrel wiring, reserved for future diagnostics).</param>
        /// <param name="proxyMiddleware">
        /// The already-constructed middleware instance used to handle every request. Passed directly, rather than
        /// copying the application's DI container into the inner host, so the inner host can never end up with its
        /// own copy of application-level hosted service registrations (which previously caused unbounded recursive
        /// construction of <see cref="AgenticRouter.Hosting.ProxyHostedService"/>).
        /// </param>
        public ProxyServer(ILogger<ProxyServer> logger, ProxyMiddleware proxyMiddleware)
        {
            ArgumentNullException.ThrowIfNull(logger);
            ArgumentNullException.ThrowIfNull(proxyMiddleware);

            _host = Host.CreateDefaultBuilder()
                .ConfigureWebHostDefaults(webBuilder =>
                {
                    webBuilder.UseKestrel(options =>
                    {
                        options.ListenLocalhost(5001);
                    });

                    webBuilder.Configure(app =>
                    {
                        app.Run(context => proxyMiddleware.InvokeAsync(context, _ => Task.CompletedTask));
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
