using AgenticRouter.Proxy;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using System.Net;
using System.Text;

namespace AgenticRouter.Tests.Integration;

/// <summary>
/// Covers end-to-end proxy interception behavior against a real local upstream endpoint.
/// </summary>
[Collection("ProxyLifecycle")]
public class ProxyInterceptionTests
{
    [Fact(Timeout = 5000)]
    public async Task Proxy_InterceptsAndForwards_Request_ToUpstream()
    {
        using var upstream = new HttpListener();
        var upstreamPort = GetFreeTcpPort();
        var prefix = $"http://127.0.0.1:{upstreamPort}/";
        upstream.Prefixes.Add(prefix);
        upstream.Start();

        var upstreamTask = Task.Run(async () =>
        {
            var context = await upstream.GetContextAsync();
            using var reader = new StreamReader(context.Request.InputStream, context.Request.ContentEncoding);
            var requestBody = await reader.ReadToEndAsync();

            context.Response.StatusCode = (int)HttpStatusCode.OK;
            context.Response.Headers.Add("X-Upstream", "ok");
            await using var writer = new StreamWriter(context.Response.OutputStream, Encoding.UTF8);
            await writer.WriteAsync($"upstream:{requestBody}");
            context.Response.Close();
        });

        var host = Program.CreateHostBuilder([]).Build();
        await host.StartAsync();

        try
        {
            var interceptor = host.Services.GetRequiredService<RequestInterceptor>();
            using var client = new HttpClient();
            using var request = new HttpRequestMessage(HttpMethod.Post, "http://127.0.0.1:5001/v1/chat/completions")
            {
                Content = new StringContent("payload", Encoding.UTF8, "text/plain")
            };

            request.Headers.Host = $"127.0.0.1:{upstreamPort}";

            var response = await client.SendAsync(request);
            var responseBody = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Equal("ok", response.Headers.GetValues("X-Upstream").Single());
            Assert.Contains("upstream:payload", responseBody, StringComparison.Ordinal);
            Assert.True(interceptor.InterceptedRequestCount >= 1);

            await upstreamTask;
        }
        finally
        {
            upstream.Stop();
            await host.StopAsync();
        }
    }

    private static int GetFreeTcpPort()
    {
        var listener = new System.Net.Sockets.TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        var port = ((IPEndPoint)listener.LocalEndpoint).Port;
        listener.Stop();
        return port;
    }
}
