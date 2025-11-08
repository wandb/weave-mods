# Marimo Example Mod

An example marimo mod demonstrating edit and publish modes.

## Overview

This mod showcases marimo's ability to run in two modes:

- **Edit Mode**: Full interactive notebook editing capabilities (default in dev)
- **Run Mode**: Read-only view for end users (default in production)

## Usage

### Development

Run in edit mode (default in dev):
```bash
./dev.py mods/marimo
```

Run in run mode:
```bash
MARIMO_MODE=run ./dev.py mods/marimo
```

### Production

Build the Docker image:
```bash
./build.py mods/marimo
```

Run in run mode (default in production):
```bash
docker run -p 6637:6637 localhost/marimo-example:latest
```

Run in edit mode:
```bash
docker run -p 6637:6637 -e MARIMO_MODE=edit localhost/marimo-example:latest
```

Access at: http://localhost:6637

## Environment Variables

- `MARIMO_MODE`: Set to "edit" (default) or "run"
- `PORT`: Port to run on (default: 6637)

## Features Demonstrated

- Mode switching without rebuild
- Interactive UI components (sliders)
- Markdown documentation
- Reactive cell updates

## Notes

- Edit mode allows full notebook modification
- Publish mode is read-only but shows all interactive outputs
- Mode can be changed by restarting with different environment variable
