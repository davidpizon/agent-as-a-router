using AgenticRouter.Proxy;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging.Abstractions;
using System.Threading.Tasks;
using Xunit;

namespace AgenticRouter.Tests.Proxy
{
    public class RequestInterceptorTests
    {
        [Fact]
        public async Task InterceptRequestAsync_LogsRequest()
        {
            // Arrange
            var logger = new NullLogger<RequestInterceptor>();
            var interceptor = new RequestInterceptor(logger);
            var context = new DefaultHttpContext();
            context.Request.Method = "GET";
            context.Request.Scheme = "https";
            context.Request.Host = new HostString("example.com");
            context.Request.Path = "/test";

            // Act
            await interceptor.InterceptRequestAsync(context);

            // Assert
            // This test primarily ensures no exceptions are thrown.
            // Logging can be verified with a mock logger if needed.
        }

        [Fact]
        public async Task InterceptResponseAsync_LogsResponse()
        {
            // Arrange
            var logger = new NullLogger<RequestInterceptor>();
            var interceptor = new RequestInterceptor(logger);
            var context = new DefaultHttpContext();
            context.Response.StatusCode = 200;

            // Act
            await interceptor.InterceptResponseAsync(context);

            // Assert
            // This test primarily ensures no exceptions are thrown.
        }
    }
}
