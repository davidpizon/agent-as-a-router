using Microsoft.Extensions.Options;

namespace AgenticRouter.Models;

/// <summary>
/// Represents the known-model allowlist and provider configuration bound from the <c>ModelRouting</c> section.
/// </summary>
public sealed class ModelRoutingOptions
{
    /// <summary>
    /// Gets the configuration section name used for model routing settings.
    /// </summary>
    public const string SectionName = "ModelRouting";

    /// <summary>
    /// Gets the configured upstream providers, keyed by provider name.
    /// </summary>
    public Dictionary<string, ProviderOptions> Providers { get; init; } = new(StringComparer.OrdinalIgnoreCase);

    /// <summary>
    /// Gets the allowlist of known models the proxy is permitted to route to.
    /// </summary>
    public List<ModelRouteEntry> ModelList { get; init; } = [];

    /// <summary>
    /// Performs domain-level validation that is not fully expressible through data annotations.
    /// </summary>
    /// <exception cref="OptionsValidationException">Thrown when the model routing configuration is inconsistent.</exception>
    public void EnsureValid()
    {
        var errors = new List<string>();
        var seenModelNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var entry in ModelList)
        {
            if (string.IsNullOrWhiteSpace(entry.ModelName))
            {
                errors.Add("ModelList entries must have a non-empty ModelName.");
                continue;
            }

            if (!seenModelNames.Add(entry.ModelName))
            {
                errors.Add($"Duplicate ModelName '{entry.ModelName}' in ModelList.");
            }

            if (string.IsNullOrWhiteSpace(entry.Provider) || !Providers.ContainsKey(entry.Provider))
            {
                errors.Add($"ModelList entry '{entry.ModelName}' references unknown provider '{entry.Provider}'.");
            }

            if (string.IsNullOrWhiteSpace(entry.ProviderModelId))
            {
                errors.Add($"ModelList entry '{entry.ModelName}' must have a non-empty ProviderModelId.");
            }
        }

        foreach (var (name, provider) in Providers)
        {
            if (!Uri.TryCreate(provider.BaseUrl, UriKind.Absolute, out _))
            {
                errors.Add($"Provider '{name}' has an invalid BaseUrl '{provider.BaseUrl}'.");
            }

            if (string.IsNullOrWhiteSpace(provider.AuthHeaderName))
            {
                errors.Add($"Provider '{name}' must have a non-empty AuthHeaderName.");
            }
        }

        if (errors.Count > 0)
        {
            throw new OptionsValidationException(nameof(ModelRoutingOptions), typeof(ModelRoutingOptions), errors);
        }
    }
}

/// <summary>
/// Represents a single upstream provider's connection details.
/// </summary>
public sealed class ProviderOptions
{
    /// <summary>
    /// Gets the absolute base URL of the provider's API (scheme + host, e.g. <c>https://api.openai.com</c>).
    /// </summary>
    public string BaseUrl { get; init; } = string.Empty;

    /// <summary>
    /// Gets the name of the environment variable holding the API key used to authenticate with this provider.
    /// Used only when <see cref="ApiKey"/> is not set. Prefer this over <see cref="ApiKey"/> so secrets are not
    /// checked into configuration files.
    /// </summary>
    public string? ApiKeyEnvVar { get; init; }

    /// <summary>
    /// Gets the literal API key used to authenticate with this provider, when supplied directly in configuration.
    /// Takes precedence over <see cref="ApiKeyEnvVar"/> when non-empty.
    /// </summary>
    public string? ApiKey { get; init; }

    /// <summary>
    /// Gets the name of the HTTP header used to carry the API key (e.g. <c>Authorization</c> or <c>x-api-key</c>).
    /// </summary>
    public string AuthHeaderName { get; init; } = "Authorization";

    /// <summary>
    /// Gets the scheme prefixed to the API key value in the auth header (e.g. <c>Bearer</c>). Empty means the raw key is used.
    /// </summary>
    public string AuthHeaderScheme { get; init; } = "Bearer";
}

/// <summary>
/// Maps a client-facing model alias to a provider and the model identifier that provider expects.
/// </summary>
public sealed class ModelRouteEntry
{
    /// <summary>
    /// Gets the client-facing model name, as sent in the request body's <c>model</c> field.
    /// </summary>
    public string ModelName { get; init; } = string.Empty;

    /// <summary>
    /// Gets the provider key this model routes to. Must exist in <see cref="ModelRoutingOptions.Providers"/>.
    /// </summary>
    public string Provider { get; init; } = string.Empty;

    /// <summary>
    /// Gets the model identifier to substitute into the forwarded request's <c>model</c> field.
    /// </summary>
    public string ProviderModelId { get; init; } = string.Empty;
}
