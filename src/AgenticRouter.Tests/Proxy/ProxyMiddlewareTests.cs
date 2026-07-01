using AgenticRouter.Proxy;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Moq;
using System.Net;
using System.Net.Http;
using System.Text;

namespace AgenticRouter.Tests.Proxy;

/// <summary>
/// Covers request forwarding behavior for <see cref="ProxyMiddleware"/>.
/// </summary>
public class ProxyMiddlewareTests
{
    [Fact]
    public async Task InvokeAsync_ForwardsRequestAndCopiesResponse()
    {
        var loggerMock = new Mock<ILogger<ProxyMiddleware>>();
        var interceptor = new RequestInterceptor(Mock.Of<ILogger<RequestInterceptor>>());
        var handler = new DelegatingHandlerStub(async request =>
        {
            Assert.Equal(HttpMethod.Post, request.Method);
            Assert.Equal("https://example.com/chat?x=1", request.RequestUri!.ToString());
            Assert.True(request.Headers.Contains("X-Trace"));

            var body = request.Content is null ? string.Empty : await request.Content.ReadAsStringAsync();
            Assert.Equal("{\"model\":\"gpt\"}", body);

            var response = new HttpResponseMessage(HttpStatusCode.Accepted)
            {
                Content = new StringContent("forwarded", Encoding.UTF8, "text/plain")
            };
            response.Headers.Add("X-From-Upstream", "true");
            return response;
        });

        var middleware = new ProxyMiddleware(loggerMock.Object, interceptor, new HttpClient(handler));

        var context = new DefaultHttpContext();
        context.Request.Method = HttpMethods.Post;
        context.Request.Scheme = "https";
        context.Request.Host = new HostString("example.com");
        context.Request.Path = "/chat";
        context.Request.QueryString = new QueryString("?x=1");
        context.Request.Headers["X-Trace"] = "abc";
        var requestBody = Encoding.UTF8.GetBytes("{\"model\":\"gpt\"}");
        context.Request.Body = new MemoryStream(requestBody);
        context.Request.ContentLength = requestBody.Length;
        context.Response.Body = new MemoryStream();

        await middleware.InvokeAsync(context, _ => Task.CompletedTask);

        Assert.Equal(StatusCodes.Status202Accepted, context.Response.StatusCode);
        Assert.Equal("true", context.Response.Headers["X-From-Upstream"].ToString());
        Assert.Equal(1, interceptor.InterceptedRequestCount);

        context.Response.Body.Position = 0;
        using var reader = new StreamReader(context.Response.Body, Encoding.UTF8);
        var responseBody = await reader.ReadToEndAsync();
        Assert.Equal("forwarded", responseBody);

        loggerMock.Verify(
            logger => logger.Log(
                LogLevel.Information,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((state, _) => state.ToString()!.Contains("Proxy middleware caught request to", StringComparison.Ordinal)),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Once);
    }

    [Fact]
    public async Task InvokeAsync_WhenForwardingFails_ThrowsHttpRequestException()
    {
        var interceptor = new RequestInterceptor(Mock.Of<ILogger<RequestInterceptor>>());
        var handler = new DelegatingHandlerStub(_ => throw new HttpRequestException("upstream unavailable"));
        var middleware = new ProxyMiddleware(Mock.Of<ILogger<ProxyMiddleware>>(), interceptor, new HttpClient(handler));

        var context = new DefaultHttpContext();
        context.Request.Method = HttpMethods.Get;
        context.Request.Scheme = "https";
        context.Request.Host = new HostString("example.com");
        context.Request.Path = "/fail";

        await Assert.ThrowsAsync<HttpRequestException>(() => middleware.InvokeAsync(context, _ => Task.CompletedTask));
    }

    private sealed class DelegatingHandlerStub : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, Task<HttpResponseMessage>> _handler;

        public DelegatingHandlerStub(Func<HttpRequestMessage, Task<HttpResponseMessage>> handler)
        {
            _handler = handler;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            => _handler(request);
    }
}
