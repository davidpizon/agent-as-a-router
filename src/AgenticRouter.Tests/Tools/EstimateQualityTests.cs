using AgenticRouter.Tools;
using Xunit;

namespace AgenticRouter.Tests.Tools
{
    public class EstimateQualityTests
    {
        [Fact]
        public void Estimate_WithEmptyCode_ReturnsZero()
        {
            // Arrange
            var estimateQuality = new EstimateQuality();
            var code = "";

            // Act
            var score = estimateQuality.Estimate(code);

            // Assert
            Assert.Equal(0.0, score);
        }

        [Fact]
        public void Estimate_WithShortCode_ReturnsLowScore()
        {
            // Arrange
            var estimateQuality = new EstimateQuality();
            var code = "public class A {}";

            // Act
            var score = estimateQuality.Estimate(code);

            // Assert
            Assert.True(score > 0.0);
            Assert.True(score < 0.5);
        }

        [Fact]
        public void Estimate_WithLongerCodeAndNoComments_IsPenalized()
        {
            // Arrange
            var estimateQuality = new EstimateQuality();
            var codeWithComment = @"
// This is a good class
public class MyClass
{
    public void MyMethod() {}
}";
            var codeWithoutComment = @"
public class MyClass
{
    public void MyMethod() {}
}";

            // Act
            var scoreWithComment = estimateQuality.Estimate(codeWithComment);
            var scoreWithoutComment = estimateQuality.Estimate(codeWithoutComment);

            // Assert
            Assert.True(scoreWithoutComment < scoreWithComment);
        }
    }
}
