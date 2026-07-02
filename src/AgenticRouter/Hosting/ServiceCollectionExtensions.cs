using AgenticRouter.Proxy;
using AgenticRouter.Router;
using AgenticRouter.Tools;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;

namespace AgenticRouter.Hosting
{
    /// <summary>
    /// Extension methods for setting up agentic router services in an <see cref="IServiceCollection" />.
    /// </summary>
    public static class ServiceCollectionExtensions
    {
        /// <summary>
        /// Adds the core services for the agentic router to the specified <see cref="IServiceCollection" />.
        /// </summary>
        /// <param name="services">The <see cref="IServiceCollection" /> to add the services to.</param>
        /// <returns>The <see cref="IServiceCollection"/> so that additional calls can be chained.</returns>
        public static IServiceCollection AddAgenticRouter(this IServiceCollection services)
        {
            // Core Router
            services.AddSingleton<IRouterMemoryStore, JsonRouterMemoryStore>();
            services.AddSingleton<RouterMemory>();
            // Note: IRouterModelClient is not registered here as it will be context-specific.
            // It should be provided by a factory or a more specific DI scope.
            services.AddTransient<AgentAsARouter>();

            // Tools
            services.AddTransient<CheckSyntax>();
            services.AddTransient<RunVisibleTests>();
            services.AddTransient<EstimateQuality>();

            // Proxy
            services.AddSingleton<RequestInterceptor>();
            services.AddTransient<ProxyMiddleware>();

            // Create a copy of services WITHOUT hosted services BEFORE registering ProxyHostedService
            // to prevent circular dependency
            var proxyServices = new ServiceCollection();
            foreach (var descriptor in services)
            {
                var isHostedService = descriptor.ServiceType == typeof(Microsoft.Extensions.Hosting.IHostedService)
                    || typeof(Microsoft.Extensions.Hosting.IHostedService).IsAssignableFrom(descriptor.ServiceType)
                    || (descriptor.ImplementationType is not null && typeof(Microsoft.Extensions.Hosting.IHostedService).IsAssignableFrom(descriptor.ImplementationType))
                    || (descriptor.ImplementationInstance is Microsoft.Extensions.Hosting.IHostedService)
                    || (descriptor.ImplementationFactory is not null && descriptor.ServiceType == typeof(Microsoft.Extensions.Hosting.IHostedService));

                if (isHostedService)
                {
                    continue;
                }

                proxyServices.Add(descriptor);
            }

            services.AddHostedService(sp =>
            {
                return new ProxyHostedService(
                    sp.GetRequiredService<Microsoft.Extensions.Logging.ILogger<ProxyHostedService>>(),
                    sp.GetRequiredService<Microsoft.Extensions.Logging.ILogger<ProxyServer>>(),
                    proxyServices);
            });

            return services;
        }
    }
}
