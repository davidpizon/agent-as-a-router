namespace AgenticRouter.Proxy;

/// <summary>
/// The outcome of resolving and rewriting a request body against the known-model allowlist.
/// </summary>
public sealed record ModelRouteResolutionResult
{
    private ModelRouteResolutionResult(bool isSuccess, ResolvedModelRoute? route, byte[]? rewrittenBody, string? errorMessage)
    {
        IsSuccess = isSuccess;
        Route = route;
        RewrittenBody = rewrittenBody;
        ErrorMessage = errorMessage;
    }

    /// <summary>
    /// Gets a value indicating whether the request's model was resolved to a known upstream.
    /// </summary>
    public bool IsSuccess { get; }

    /// <summary>
    /// Gets the resolved upstream route, when <see cref="IsSuccess"/> is <see langword="true"/>.
    /// </summary>
    public ResolvedModelRoute? Route { get; }

    /// <summary>
    /// Gets the request body with <c>model</c> rewritten to the provider's model id, when <see cref="IsSuccess"/> is <see langword="true"/>.
    /// </summary>
    public byte[]? RewrittenBody { get; }

    /// <summary>
    /// Gets a human-readable reason for failure, when <see cref="IsSuccess"/> is <see langword="false"/>.
    /// </summary>
    public string? ErrorMessage { get; }

    /// <summary>
    /// Creates a successful resolution result.
    /// </summary>
    public static ModelRouteResolutionResult Success(ResolvedModelRoute route, byte[] rewrittenBody) =>
        new(true, route, rewrittenBody, null);

    /// <summary>
    /// Creates a failed resolution result.
    /// </summary>
    public static ModelRouteResolutionResult Failure(string errorMessage) =>
        new(false, null, null, errorMessage);
}
