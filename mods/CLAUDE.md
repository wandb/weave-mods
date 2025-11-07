# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when
working with code in this repository.

## Project Architecture

This is a Weave mod development environment with hybrid architecture:

- **Frontend**: JavaScript/TypeScript with neural terminal interface
(VIBEZ UI)
- **Backend**: Python SDK for Weave API interactions
- **Server**: Deno TypeScript server with WebSocket terminal support
- **Integration**: Weave platform for ML/AI workflow management

### Key Components

1. **Terminal Interface** (`src/index.html`, `src/index.ts`): Web-based
    terminal with cyberpunk styling that connects to Claude via WebSocket
2. **Deno Server** (`src/deno_server.ts`): Handles WebSocket
connections, spawns Claude processes with TTY support
3. **Python SDK** (`src/sdk/`): Weave API wrapper with Streamlit
components for data visualization
4. **Main App** (`main.py`, `pyproject.toml`): Basic Python entry point
    with Weave dependencies

## Development Commands

### JavaScript/TypeScript (src/)
```bash
cd src
pnpm install              # Install dependencies
npm run build            # Build static assets to dist/
deno run --allow-all deno_server.ts  # Run Deno server
```

### Python (root and sdk/)
```bash
# Root level
uv install               # Install Python dependencies
python main.py           # Run main application

# SDK development
cd src/sdk
uv install               # Install SDK dependencies
```

### Testing
- No specific test commands found - check for test files before
assuming test framework

## Environment Variables

Required for proper operation:
- `WANDB_API_KEY`: Weights & Biases API key for Weave integration
- `WANDB_ENTITY`: Default entity/team name
- `WANDB_PROJECT`: Project name for Weave
- `PORT`: Server port (default: 6637 for main, 8000 for terminal)
- `HEALTHCHECK_PORT`: Health check port (default: 6638)

## Weave Integration

This project integrates heavily with Weave for ML workflow management:

- **Calls**: Track ML operation calls and traces
- **Objects**: Store and version ML artifacts
- **Operations**: Define and version ML operations
- **Projects**: Organize work within Weave projects

Key Python modules:
- `mods.api.weave_api_next`: Extended Weave client functionality
- `mods.streamlit.*`: Streamlit components for data visualization
- `mods.api.query`: Query utilities for Weave data

## Server Architecture

The Deno server (`src/deno_server.ts`) provides:
- Static file serving from `dist/` directory
- WebSocket terminal interface at `/ws`
- Weave API proxy at `/__weave*` endpoints
- Custom handler loading from `index.ts`
- TTY emulation for Claude process interaction

## UI Framework

VIBEZ neural terminal interface features:
- Cyberpunk-themed web terminal using xterm.js
- Real-time WebSocket communication
- Terminal resize support
- Clipboard integration
- Connection status monitoring

## Package Management

- **JavaScript**: Uses pnpm (lockfile: `pnpm-lock.yaml`)
- **Python**: Uses uv (lockfiles: `uv.lock`)
- **Deno**: Uses native imports with JSR/HTTP modules

## File Structure

```
/app/
├── src/                    # JavaScript/TypeScript frontend
│   ├── sdk/               # Python SDK for Weave
│   ├── index.html         # Terminal UI
│   ├── deno_server.ts     # Main Deno server
│   └── package.json       # JS dependencies
├── main.py                # Python entry point
├── pyproject.toml         # Python project config
└── README.md              # Basic project info
```
