# AGENTS.md

This repository contains the Agent-as-a-Router project.

## Start Here
- Read `README.md` first for the current project overview, quick start, demos, and repository layout.
- Read `docs/HANDBOOK.md` for maintainer guidance and extended notes.
- Use `PLAN.md` for the current C# migration roadmap.

## Working Rules
- Keep changes minimal and scoped to the user request.
- Prefer the existing repository conventions and document any deliberate deviation.
- When editing C# code, follow .NET 10 best practices: nullable reference types, async/await where appropriate, dependency injection, options binding, and structured logging.
- Add or update tests when behavior changes.
- Validate changes before finishing.
- **Markdown Diagrams:** All diagrams in markdown documentation MUST be represented using Mermaid syntax (not ASCII art, text boxes, or other formats). This ensures consistency, readability, and platform compatibility across documentation.
- **Logging:** Use Serilog exclusively for all logging. Configure Serilog via `appsettings.json` to support output destinations based on configuration:
  - **File logging:** Enable via `Serilog.WriteTo.File` configuration with customizable path, retention, and rolling file policies.
  - **Windows Event Viewer logging:** Enable via `Serilog.Sinks.EventLog` configuration for events that should be captured by the Windows Event Viewer (errors, critical events, audit trails).
  - Example configuration in appsettings.json:
    ```json
    {
      "Serilog": {
        "Using": ["Serilog.Sinks.File", "Serilog.Sinks.EventLog"],
        "MinimumLevel": "Information",
        "WriteTo": [
          {
            "Name": "File",
            "Args": {
              "path": "./logs/acrouter-.log",
              "rollingInterval": "Day",
              "retainedFileCountLimit": 30
            }
          },
          {
            "Name": "EventLog",
            "Args": {
              "source": "ACRouter",
              "logName": "Application",
              "restrictedToMinimumLevel": "Error"
            }
          }
        ],
        "Enrich": ["FromLogContext", "WithMachineName", "WithThreadId"]
      }
    }
    ```
  - Use structured logging: `logger.LogInformation("Model selected: {Model} with confidence {Confidence}", model, confidence)` (not string interpolation).
  - Log all routing decisions, proxy interceptions, memory updates, and errors to enable audit trails and diagnostics.

## Key References
- `README.md`
- `docs/HANDBOOK.md`
- `PLAN.md`
- `data/README.md`
