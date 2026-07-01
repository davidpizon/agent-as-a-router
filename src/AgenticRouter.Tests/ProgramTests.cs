using Microsoft.Extensions.Hosting;
using Xunit;

namespace AgenticRouter.Tests
{
    public class ProgramTests
    {
        [Fact]
        public void CreateHostBuilder_BuildsSuccessfully()
        {
            // Arrange
            var args = new string[] { };

            // Act
            var host = Program.CreateHostBuilder(args).Build();

            // Assert
            Assert.NotNull(host);
        }
    }
}
