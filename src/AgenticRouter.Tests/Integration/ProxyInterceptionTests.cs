using AgenticRouter.Proxy;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using System.Net.Http;
using System.Threading.Tasks;
using Xunit;

namespace AgenticRouter.Tests.Integration
{
    public class ProxyInterceptionTests
    {
        [Fact]
        public async Task Proxy_Intercepts_Request()
        {
            // Arrange
            var host = Program.CreateHostBuilder(new string[] { }).Build();
            var lifetime = host.Services.GetRequiredService<IHostApplicationLifetime>();
            var interceptor = host.Services.GetRequiredService<RequestInterceptor>();
            var client = new HttpClient();

            await host.StartAsync();

            // Act
            try
            {
                // Send a request to the proxy. We expect this to fail with an HttpRequestException
                // because the target service isn't running, but the proxy should still intercept it.
                await client.GetAsync("http://localhost:5001/v1/chat/completions");
            }
            catch (HttpRequestException)
            {
                // This is expected.
            }

            // Assert
            Assert.True(interceptor.InterceptedRequestCount > 0);

            // Clean up
            lifetime.StopApplication();
            await host.WaitForShutdownAsync();
        }
    }
}
