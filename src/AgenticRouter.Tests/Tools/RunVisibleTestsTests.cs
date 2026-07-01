using AgenticRouter.Tools;
using System.IO;
using System.Threading.Tasks;
using Xunit;

namespace AgenticRouter.Tests.Tools
{
    public class RunVisibleTestsTests
    {
        [Fact]
        public async Task RunAsync_WithValidTestProject_RunsTests()
        {
            // Arrange
            var runVisibleTests = new RunVisibleTests();
            // This test is an integration test and relies on the structure of the solution.
            // It assumes that this test project itself can be tested.
            var projectPath = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "..", "..", ".."));

            // Act
            var output = await runVisibleTests.RunAsync(projectPath);

            // Assert
            Assert.Contains("Test Run Successful.", output);
        }
    }
}
