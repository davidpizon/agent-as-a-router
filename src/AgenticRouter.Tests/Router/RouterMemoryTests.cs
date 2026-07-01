using AgenticRouter.Router;
using Moq;

namespace AgenticRouter.Tests.Router;

/// <summary>
/// Tests for the <see cref="RouterMemory"/> class.
/// </summary>
public class RouterMemoryTests
{
    [Fact]
    public async Task AddScore_And_GetAverageScore_WorkCorrectly()
    {
        // Arrange
        var memory = new RouterMemory();
        var dimension = "test_dimension";
        var model = "test_model";

        // Act
        await memory.AddScoreAsync(dimension, model, 0.8);
        await memory.AddScoreAsync(dimension, model, 0.9);
        var averageScore = memory.GetAverageScore(dimension, model);

        // Assert
        Assert.NotNull(averageScore);
        Assert.Equal(0.85, averageScore.Value, 2);
    }

    [Fact]
    public void GetAverageScore_ReturnsNull_ForUnknownModel()
    {
        // Arrange
        var memory = new RouterMemory();

        // Act
        var averageScore = memory.GetAverageScore("unknown_dimension", "unknown_model");

        // Assert
        Assert.Null(averageScore);
    }

    [Fact]
    public async Task GetModelsForDimension_ReturnsCorrectModels()
    {
        // Arrange
        var memory = new RouterMemory();
        var dimension = "test_dimension";
        await memory.AddScoreAsync(dimension, "model1", 0.8);
        await memory.AddScoreAsync(dimension, "model2", 0.9);

        // Act
        var models = memory.GetModelsForDimension(dimension);

        // Assert
        Assert.Collection(models.OrderBy(m => m),
            m => Assert.Equal("model1", m),
            m => Assert.Equal("model2", m));
    }
}
