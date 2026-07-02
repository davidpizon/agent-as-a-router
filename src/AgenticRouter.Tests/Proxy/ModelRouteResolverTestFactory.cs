using AgenticRouter.Models;
using AgenticRouter.Proxy;
using Microsoft.Extensions.Options;
using Moq;

namespace AgenticRouter.Tests.Proxy;

/// <summary>
/// Builds <see cref="IModelRouteResolver"/> instances for tests without needing real environment variables.
/// </summary>
internal static class ModelRouteResolverTestFactory
{
    public const string ApiKeyEnvVar = "TEST_PROVIDER_API_KEY";

    public static IModelRouteResolver Create(
        string modelName,
        string providerModelId,
        string baseUrl,
        string authHeaderName = "Authorization",
        string authHeaderScheme = "Bearer",
        string? apiKey = "test-api-key",
        string providerName = "test-provider")
    {
        var options = new ModelRoutingOptions
        {
            Providers = new Dictionary<string, ProviderOptions>(StringComparer.OrdinalIgnoreCase)
            {
                [providerName] = new ProviderOptions
                {
                    BaseUrl = baseUrl,
                    ApiKeyEnvVar = ApiKeyEnvVar,
                    AuthHeaderName = authHeaderName,
                    AuthHeaderScheme = authHeaderScheme
                }
            },
            ModelList =
            [
                new ModelRouteEntry { ModelName = modelName, Provider = providerName, ProviderModelId = providerModelId }
            ]
        };

        var environment = new Mock<IEnvironmentVariableProvider>();
        environment.Setup(e => e.GetVariable(ApiKeyEnvVar)).Returns(apiKey);

        return new ModelRouteResolver(Options.Create(options), environment.Object);
    }

    public static IModelRouteResolver Empty() =>
        new ModelRouteResolver(Options.Create(new ModelRoutingOptions()), Mock.Of<IEnvironmentVariableProvider>());
}
