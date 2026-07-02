using AgenticRouter.Models;
using AgenticRouter.Proxy;
using Microsoft.Extensions.Options;
using Moq;

namespace AgenticRouter.Tests.Proxy;

/// <summary>
/// Covers known-model allowlist resolution behavior for <see cref="ModelRouteResolver"/>.
/// </summary>
public class ModelRouteResolverTests
{
    [Fact]
    public void TryResolve_KnownModel_ReturnsUpstreamRouteWithInjectedCredential()
    {
        var resolver = ModelRouteResolverTestFactory.Create(
            modelName: "gpt-5.4",
            providerModelId: "gpt-5.4-2026-01",
            baseUrl: "https://api.openai.com",
            authHeaderName: "Authorization",
            authHeaderScheme: "Bearer",
            apiKey: "sk-test-123");

        var resolved = resolver.TryResolve("gpt-5.4", out var route);

        Assert.True(resolved);
        Assert.Equal("gpt-5.4", route!.ModelName);
        Assert.Equal("gpt-5.4-2026-01", route.ProviderModelId);
        Assert.Equal("https://api.openai.com/", route.UpstreamBaseUrl.ToString());
        Assert.Equal("Authorization", route.AuthHeaderName);
        Assert.Equal("Bearer sk-test-123", route.AuthHeaderValue);
    }

    [Fact]
    public void TryResolve_IsCaseInsensitiveOnModelName()
    {
        var resolver = ModelRouteResolverTestFactory.Create("gpt-5.4", "gpt-5.4", "https://api.openai.com");

        Assert.True(resolver.TryResolve("GPT-5.4", out _));
    }

    [Fact]
    public void TryResolve_UnknownModel_ReturnsFalse()
    {
        var resolver = ModelRouteResolverTestFactory.Create("gpt-5.4", "gpt-5.4", "https://api.openai.com");

        var resolved = resolver.TryResolve("some-other-model", out var route);

        Assert.False(resolved);
        Assert.Null(route);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void TryResolve_NullOrWhitespaceModelName_ReturnsFalse(string? modelName)
    {
        var resolver = ModelRouteResolverTestFactory.Create("gpt-5.4", "gpt-5.4", "https://api.openai.com");

        Assert.False(resolver.TryResolve(modelName, out var route));
        Assert.Null(route);
    }

    [Fact]
    public void TryResolve_MissingApiKeyEnvironmentVariable_ResolvesWithNullAuthHeaderValue()
    {
        var resolver = ModelRouteResolverTestFactory.Create(
            modelName: "gpt-5.4",
            providerModelId: "gpt-5.4",
            baseUrl: "https://api.openai.com",
            apiKey: null);

        var resolved = resolver.TryResolve("gpt-5.4", out var route);

        Assert.True(resolved);
        Assert.Null(route!.AuthHeaderValue);
    }

    [Fact]
    public void TryResolve_ProviderWithNoAuthScheme_UsesRawKeyAsHeaderValue()
    {
        var resolver = ModelRouteResolverTestFactory.Create(
            modelName: "claude-opus-4.6",
            providerModelId: "claude-opus-4-6",
            baseUrl: "https://api.anthropic.com",
            authHeaderName: "x-api-key",
            authHeaderScheme: "",
            apiKey: "anthropic-secret");

        resolver.TryResolve("claude-opus-4.6", out var route);

        Assert.Equal("x-api-key", route!.AuthHeaderName);
        Assert.Equal("anthropic-secret", route.AuthHeaderValue);
    }

    [Fact]
    public void Constructor_ModelListReferencesUnknownProvider_ThrowsOptionsValidationException()
    {
        var options = new ModelRoutingOptions
        {
            Providers = new Dictionary<string, ProviderOptions>(),
            ModelList = [new ModelRouteEntry { ModelName = "gpt-5.4", Provider = "openai", ProviderModelId = "gpt-5.4" }]
        };

        Assert.Throws<OptionsValidationException>(
            () => new ModelRouteResolver(Options.Create(options), Mock.Of<IEnvironmentVariableProvider>()));
    }

    [Fact]
    public void Constructor_EmptyConfiguration_DoesNotThrow_AndResolvesNothing()
    {
        var resolver = ModelRouteResolverTestFactory.Empty();

        Assert.False(resolver.TryResolve("anything", out _));
    }
}
