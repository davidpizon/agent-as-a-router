using AgenticRouter.Tools;
using System.Linq;
using Xunit;

namespace AgenticRouter.Tests.Tools
{
    public class CheckSyntaxTests
    {
        [Fact]
        public void Check_WithValidCode_ReturnsNoErrors()
        {
            // Arrange
            var checkSyntax = new CheckSyntax();
            var code = @"
public class MyClass
{
    public void MyMethod()
    {
    }
}";

            // Act
            var diagnostics = checkSyntax.Check(code);

            // Assert
            Assert.Empty(diagnostics);
        }

        [Fact]
        public void Check_WithInvalidCode_ReturnsErrors()
        {
            // Arrange
            var checkSyntax = new CheckSyntax();
            var code = @"
public class MyClass
{
    public void MyMethod()
    {
        // Missing closing brace
    ";

            // Act
            var diagnostics = checkSyntax.Check(code);

            // Assert
            Assert.NotEmpty(diagnostics);
            Assert.True(diagnostics.All(d => d.Severity == Microsoft.CodeAnalysis.DiagnosticSeverity.Error));
        }
    }
}
