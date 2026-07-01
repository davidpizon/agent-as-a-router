using AgenticRouter.Router;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Moq;
using System.Collections.Concurrent;
using System.Text.Json;
using AgenticRouter.Models;

namespace AgenticRouter.Tests.Router;

/// <summary>
/// Tests for the <see cref="JsonRouterMemoryStore"/> class.
/// </summary>
public class JsonRouterMemoryStoreTests : IDisposable
{
    private readonly string _testFilePath;

    public JsonRouterMemoryStoreTests()
    {
        _testFilePath = Path.Combine(Path.GetTempPath(), $"router_memory_{Guid.NewGuid()}.json");
    }

    [Fact]
    public async Task SaveAndLoad_WorkCorrectly()
    {
        // Arrange
        var loggerMock = new Mock<ILogger<JsonRouterMemoryStore>>();
        var optionsMock = new Mock<IOptions<RoutingOptions>>();
        // This is a bit of a hack to set the file path for the test.
        // A better approach would be a dedicated configuration for the memory store path.
        var store = new JsonRouterMemoryStore(loggerMock.Object, optionsMock.Object);
        // Overwrite the private field for testing purposes.
        var field = typeof(JsonRouterMemoryStore).GetField("_filePath", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        if (field != null)
        {
            field.SetValue(store, _testFilePath);
        }


        var memoryToSave = new ConcurrentDictionary<string, ConcurrentDictionary<string, List<double>>>();
        var dimensionScores = new ConcurrentDictionary<string, List<double>>();
        dimensionScores.TryAdd("model1", new List<double> { 0.8, 0.9 });
        memoryToSave.TryAdd("dim1", dimensionScores);

        // Act
        await store.SaveAsync(memoryToSave);
        var loadedMemory = await store.LoadAsync();

        // Assert
        Assert.NotNull(loadedMemory);
        Assert.True(loadedMemory.ContainsKey("dim1"));
        Assert.True(loadedMemory["dim1"].ContainsKey("model1"));
        Assert.Equal(2, loadedMemory["dim1"]["model1"].Count);
    }

    public void Dispose()
    {
        if (File.Exists(_testFilePath))
        {
            File.Delete(_testFilePath);
        }
        GC.SuppressFinalize(this);
    }
}
