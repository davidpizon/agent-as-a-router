# Complete List of Environment Variables Used in ACRouter

## ACRouter-Specific Variables

### Router Configuration
| Variable | Type | Purpose | Example | Source |
|----------|------|---------|---------|--------|
| `ACROUTER_CHEAP_CHAIN` | String | Comma-separated list of models to try in fallback order | `"gpt-3.5-turbo,llama2"` | SYSTEM_PROXY_ARCHITECTURE.md |
| `ACROUTER_MEMORY_PATH` | Path | Location of router memory JSON file | `/var/lib/acrouter/memory.json` | SYSTEM_PROXY_ARCHITECTURE.md |
| `PROXY_LISTEN_PORT` | Integer | Port for proxy server to listen on | `5002` | SYSTEM_PROXY_ARCHITECTURE.md |

## API Provider Authentication Variables

### OpenAI
| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI API authentication |
| `OPENAI_BASE_URL` | Custom OpenAI endpoint (optional) |

### Anthropic
| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Anthropic (Claude) API authentication |

### Google Gemini
| Variable | Purpose | Example |
|----------|---------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `GOOGLE_GEMINI_BASE_URL` | Gemini API endpoint | `https://generativelanguage.googleapis.com` |
| `GEMINI_MODEL` | Model to use | `gemini-pro` |

### Other Providers
| Variable | Provider | Purpose |
|----------|----------|---------|
| `MOONSHOT_API_KEY` | Moonshot (kimi-k2.5) | Authentication |
| `MINIMAX_API_KEY` | MiniMax | Authentication |
| `ALIBABA_API_KEY` | Alibaba (Qwen) | Authentication |
| `ZHIPU_API_KEY` | Zhipu (glm-5) | Authentication |

## Proxy Variables

### Standard HTTP/HTTPS Proxy
| Variable | Purpose | Notes |
|----------|---------|-------|
| `HTTP_PROXY` | HTTP proxy URL | Format: `http://host:port` |
| `HTTPS_PROXY` | HTTPS proxy URL | Format: `http://host:port` or `https://host:port` |
| `ALL_PROXY` | Fallback proxy for all protocols | Used if HTTP/HTTPS not set |
| `NO_PROXY` | Comma-separated hosts to bypass proxy | Format: `localhost,127.0.0.1,::1` |

**Lowercase Variants:** `http_proxy`, `https_proxy`, `all_proxy`, `no_proxy` (case-insensitive on Unix/Linux)

### Gateway/Upstream Proxy
| Variable | Purpose | Source |
|----------|---------|--------|
| `CCR_UPSTREAM_PROXY_URL` | Upstream proxy URL for gateway | gateway/service.ts |
| `HTTP_PROXY` (in gateway) | Passed to gateway process | gateway/service.ts |
| `HTTPS_PROXY` (in gateway) | Passed to gateway process | gateway/service.ts |
| `ALL_PROXY` (in gateway) | Passed to gateway process | gateway/service.ts |

## Node.js / Gateway Runtime Variables

| Variable | Purpose | Value | Source |
|----------|---------|-------|--------|
| `NODE_OPTIONS` | Node.js command-line options | e.g., `--require /path/to/preload.js` | gateway/service.ts |
| `ELECTRON_RUN_AS_NODE` | Run Electron as Node.js | `"1"` | gateway/service.ts |
| `GATEWAY_CONFIG_PATH` | Path to gateway configuration file | e.g., `./gateway-config.json` | gateway/service.ts |
| `HOST` | Gateway host | `127.0.0.1` or hostname | gateway/service.ts |
| `PORT` | Gateway port | e.g., `8080` | gateway/service.ts |
| `CCR_GATEWAY_RUNTIME_ID` | Unique gateway runtime identifier | UUID | gateway/service.ts |

## Authentication Variables (Gateway)

| Variable | Purpose | Example |
|----------|---------|---------|
| `AUTH_ENABLED` | Enable authentication | `"true"` |
| `AUTH_MODE` | Authentication method | `"static_api_key"` |
| `AUTH_REQUIRED` | Require auth for all requests | `"true"` |
| `AUTH_STATIC_API_KEY_BEARER_ONLY` | Only accept Bearer tokens | `"false"` |
| `AUTH_STATIC_API_KEY_ENV` | Environment variable containing API key | `"CCR_AUTH_TOKEN"` |
| `AUTH_STATIC_API_KEY_HEADER` | HTTP header for API key | `"X-API-Key"` |
| `CCR_AUTH_TOKEN` | (Dynamic) The actual API key | `"sk-..."` |

## Profile/Shell Integration Variables

| Variable | Purpose | Values |
|----------|---------|--------|
| `CCR_PROFILE_SURFACE` | Execution context | `"app"` or `"cli"` |
| `CCR_UNDICI_MODULE` | Path to undici HTTP client | e.g., `./node_modules/undici` |

## Configuration File Variables (via Interpolation)

ACRouter supports environment variable interpolation in configuration files using:
- `${VARIABLE_NAME}` syntax
- `$VARIABLE_NAME` syntax (if variable name is all uppercase)

**Example in config file:**
```json
{
  "routerModel": "${ROUTER_MODEL}",
  "apiKey": "$OPENAI_API_KEY",
  "memoryPath": "${MEMORY_PATH:/var/lib/acrouter/memory.json}"
}
```

## Python-Specific Environment (from Code)

### Constants (Hardcoded, Not Environment Variables)
From `src/acrouter_repro/constants.py`:
```python
OOD_CHEAP_CHAIN = ["MiniMax-M2.7", "kimi-k2.5", "gpt-5.4", "glm-5"]
OOD_ESCALATE_TO = "claude-opus-4-6"
REWARD_COST_WEIGHT = 0.1
```

These are Python constants but can be overridden via environment variables in deployment.

## Configuration Files vs. Environment Variables

| Source | Priority | Format |
|--------|----------|--------|
| Environment Variables | High (runtime override) | UPPERCASE_WITH_UNDERSCORES |
| Config Files (.env) | Medium | key=value pairs |
| settings.json | Medium | JSON |
| Hardcoded Constants | Low (default) | Python/TypeScript constants |

### .env File Locations
- **Gemini CLI:** `~/.gemini/.env`
- **Claude Desktop:** `~/.claude/config.json` (not .env)
- **ACRouter (.NET):** `appsettings.json` or `appsettings.{ENVIRONMENT}.json`
- **CC-Switch:** `cc-switch/src/.env` or user-specific location

## Summary by Category

### Deployment & Infrastructure
- `PROXY_LISTEN_PORT`
- `HOST`, `PORT` (gateway)
- `CCR_GATEWAY_RUNTIME_ID`
- `GATEWAY_CONFIG_PATH`

### Router Logic
- `ACROUTER_CHEAP_CHAIN`
- `ACROUTER_MEMORY_PATH`

### API Keys (Provider-Specific)
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- Provider-specific alternatives

### Network/Proxy
- `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`
- `CCR_UPSTREAM_PROXY_URL`

### Authentication
- `AUTH_ENABLED`, `AUTH_MODE`, `AUTH_REQUIRED`
- `AUTH_STATIC_API_KEY_*` variables
- `CCR_AUTH_TOKEN` (dynamic)

### Runtime/Node.js
- `NODE_OPTIONS`
- `ELECTRON_RUN_AS_NODE`
- `CCR_UNDICI_MODULE`
- `CCR_PROFILE_SURFACE`

## Migration Note for .NET 10

When migrating ACRouter to .NET 10, environment variables should be:
1. Loaded via `IConfiguration` (dependency injection)
2. Configured in `appsettings.json` with environment variable interpolation
3. Accessed through strongly-typed `IOptions<T>` pattern
4. Documented in `AGENTS.md` (as per Serilog logging requirements)

**Example .NET 10 Configuration:**
```csharp
// In appsettings.json
{
  "ACRouter": {
    "CheapChain": "${ACROUTER_CHEAP_CHAIN:gpt-3.5-turbo,llama2}",
    "MemoryPath": "${ACROUTER_MEMORY_PATH:/var/lib/acrouter/memory.json}",
    "ProxyListenPort": "${PROXY_LISTEN_PORT:5002}"
  }
}

// In code
services.Configure<ACRouterOptions>(configuration.GetSection("ACRouter"));
var options = serviceProvider.GetRequiredService<IOptions<ACRouterOptions>>();
```
