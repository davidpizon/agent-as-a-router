using AgenticRouter.Proxy;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Moq;

namespace AgenticRouter.Tests.Proxy;

/// <summary>
/// Covers request and response interception behavior.
/// </summary>
public class RequestInterceptorTests
{
    [Fact]
    public async Task InterceptRequestAsync_IncrementsCount_AndLogsStructuredMessage()
    {
        var loggerMock = new Mock<ILogger<RequestInterceptor>>();
        var interceptor = new RequestInterceptor(loggerMock.Object);
        var context = new DefaultHttpContext();
        context.Request.Method = HttpMethods.Get;
        context.Request.Scheme = "https";
        context.Request.Host = new HostString("example.com");
        context.Request.Path = "/test";

        await interceptor.InterceptRequestAsync(context);
        await interceptor.InterceptRequestAsync(context);

        Assert.Equal(2, interceptor.InterceptedRequestCount);
        VerifyLogContains(loggerMock, LogLevel.Information, "[INTERCEPTOR] Intercepting request for");
    }

    [Fact]
    public async Task InterceptResponseAsync_LogsStructuredMessage()
    {
        var loggerMock = new Mock<ILogger<RequestInterceptor>>();
        var interceptor = new RequestInterceptor(loggerMock.Object);
        var context = new DefaultHttpContext();
        context.Request.Path = "/chat";
        context.Response.StatusCode = StatusCodes.Status200OK;

        await interceptor.InterceptResponseAsync(context);

        VerifyLogContains(loggerMock, LogLevel.Information, "[INTERCEPTOR] Intercepting response for");
    }

    private static void VerifyLogContains(Mock<ILogger<RequestInterceptor>> loggerMock, LogLevel level, string expectedText)
    {
        loggerMock.Verify(
            logger => logger.Log(
                level,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((state, _) => state.ToString()!.Contains(expectedText, StringComparison.Ordinal)),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.AtLeastOnce);
    }
}
