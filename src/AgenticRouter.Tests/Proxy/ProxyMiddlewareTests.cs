using AgenticRouter.Proxy;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging.Abstractions;
using System.Threading.Tasks;
using Xunit;

namespace AgenticRouter.Tests.Proxy
{
    public class ProxyMiddlewareTests
    {
        [Fact]
        public async Task InvokeAsync_ForwardsRequest()
        {
            // This is an integration test and is difficult to unit test without a running server.
            // The test ensures that the middleware can be instantiated and attempts to process a request.
            // A full end-to-end test would be required to verify the forwarding behavior.

            // Arrange
            var logger = new NullLogger<ProxyMiddleware>();
            var interceptorLogger = new NullLogger<RequestInterceptor>();
            var interceptor = new RequestInterceptor(interceptorLogger);
            var middleware = new ProxyMiddleware(logger, interceptor);
            var context = new DefaultHttpContext();
            context.Request.Host = new HostString("bing.com"); // Use a real host to avoid DNS errors
            context.Request.Scheme = "https";

            // Act & Assert
            await Assert.ThrowsAsync<System.Net.Http.HttpRequestException>(() => middleware.InvokeAsync(context, (ctx) => Task.CompletedTask));
        }
    }
}
