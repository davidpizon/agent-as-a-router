# Copilot Instructions

## Project Guidelines
- Always use static string literals inside log statements. Do not use string interpolation or string formatting for log message templates. Example: logger.LogInformation("Model selected: {Model} with confidence {Confidence}", model, confidence) instead of logger.LogInformation($"Model selected: {model} with confidence {confidence}")