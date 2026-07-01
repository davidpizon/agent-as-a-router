using AgenticRouter.Router;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Xunit;

namespace AgenticRouter.Tests.Integration
{
    public class RouterCompositionTests
    {
        [Fact]
        public void Host_CanResolve_AllServices()
        {
            // Arrange
            var host = Program.CreateHostBuilder(new string[] { }).Build();

            // Act & Assert
            Assert.NotNull(host.Services.GetService<AgentAsARouter>());
            Assert.NotNull(host.Services.GetService<RouterMemory>());
            Assert.NotNull(host.Services.GetService<AgenticRouter.Proxy.RequestInterceptor>());
        }
    }
}
