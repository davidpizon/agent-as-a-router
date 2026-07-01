using AgenticRouter.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

namespace AgenticRouter.Tests.Hosting
{
    public class ServiceCollectionExtensionsTests
    {
        [Fact]
        public void AddAgenticRouter_RegistersServices()
        {
            // Arrange
            var services = new ServiceCollection();

            // Act
            services.AddAgenticRouter();

            // Assert
            var serviceProvider = services.BuildServiceProvider();
            Assert.NotNull(serviceProvider.GetService<AgenticRouter.Router.AgentAsARouter>());
            Assert.NotNull(serviceProvider.GetService<AgenticRouter.Tools.CheckSyntax>());
            Assert.NotNull(serviceProvider.GetService<AgenticRouter.Proxy.RequestInterceptor>());
        }
    }
}
