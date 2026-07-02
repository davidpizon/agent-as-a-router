using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using System.Collections.Generic;
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
        /// <param name="port">
        /// The localhost port Kestrel listens on. Defaults to 5001. Pass 0 to bind an ephemeral port (useful in
        /// tests to avoid flaking when the default port is already in use); the resolved address is available via
        /// <see cref="Addresses"/> once <see cref="StartAsync"/> completes.
        /// </param>
        public ProxyServer(ILogger<ProxyServer> logger, ProxyMiddleware proxyMiddleware, int port = 5001)
        {
            ArgumentNullException.ThrowIfNull(logger);
            ArgumentNullException.ThrowIfNull(proxyMiddleware);
            ArgumentOutOfRangeException.ThrowIfNegative(port);
            ArgumentOutOfRangeException.ThrowIfGreaterThan(port, 65535);

            _host = Host.CreateDefaultBuilder()
                .ConfigureWebHostDefaults(webBuilder =>
                {
                    webBuilder.UseKestrel(options =>
                    {
                        options.ListenLocalhost(port);
                    });

                    webBuilder.Configure(app =>
                    {
                        app.Run(context => proxyMiddleware.InvokeAsync(context, _ => Task.CompletedTask));
                    });
                })
                .Build();
        }

        /// <summary>
        /// Gets the addresses Kestrel is actually listening on. Only meaningful after <see cref="StartAsync"/> completes.
        /// </summary>
        public IReadOnlyCollection<string> Addresses
        {
            get
            {
                var addresses = _host.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()?.Addresses;
                return addresses is null ? [] : new List<string>(addresses);
            }
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
