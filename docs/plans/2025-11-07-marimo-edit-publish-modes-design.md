# Marimo Edit/Publish Modes Design

**Date:** 2025-11-07
**Status:** Approved

## Overview

This design adds support for switching between edit mode and publish mode for marimo-based mods, both in local development and production Docker containers. Users can control the mode via the `MARIMO_MODE` environment variable.

## Background

Currently, marimo mods run with `marimo run` command (read-only/publish mode). This design enables users to switch to `marimo edit` for interactive notebook editing while maintaining backwards compatibility.

## Requirements

### Functional Requirements
- Support two marimo modes: edit (interactive) and publish (read-only)
- Mode switching via `MARIMO_MODE` environment variable
- Default to edit mode when environment variable is unset
- Work consistently in both dev and production environments
- Create example marimo mod with latest marimo version

### Non-Functional Requirements
- Minimal code changes
- No breaking changes to existing mods
- Fail-safe defaults (invalid values default to edit mode)

## Architecture

### Mode Selection Logic

```
Check MARIMO_MODE environment variable:
  - If "publish" → use `marimo run`
  - If "edit" or unset → use `marimo edit` (default)
  - If invalid value → use `marimo edit` (default)
```

### Components

1. **build.py** - Production build logic
2. **mods/dev-entrypoint.py** - Development runtime logic
3. **mods/marimo-entrypoint.py** - NEW: Production runtime wrapper script
4. **mods/marimo/** - NEW: Example marimo mod

## Design Details

### 1. Production Runtime Wrapper (marimo-entrypoint.py)

**Purpose:** Enable runtime mode switching in production Docker containers

**Location:** `mods/marimo-entrypoint.py`

**Functionality:**
- Read `MARIMO_MODE` environment variable
- Default to "edit" if unset or invalid
- Execute appropriate marimo command with correct args
- Pass through port and host configuration

**Pseudocode:**
```python
mode = os.getenv("MARIMO_MODE", "edit")
if mode == "publish":
    command = "run"
else:
    command = "edit"

exec(["marimo", command, "--port=6637", "--host=0.0.0.0", "/app/src/app.py"])
```

### 2. Build Script Updates (build.py)

**Changes to FLAVORS dictionary (line 52):**
- Remove static marimo command
- Or keep as fallback but note that wrapper script takes precedence in production

**Build process changes:**
- Detect marimo flavor during build
- Copy `marimo-entrypoint.py` to mod directory (alongside healthcheck.py)
- Set CMD to use wrapper script instead of direct marimo command

### 3. Dev Entrypoint Updates (mods/dev-entrypoint.py)

**Changes to marimo flavor handling (lines 254-264):**

Current:
```python
elif flavor == "marimo":
    args = [
        "uv", "run", "--no-project",
        "marimo", "run",
        "--port=" + os.getenv("PORT"),
        "--host=0.0.0.0",
        *entrypoint,
    ]
```

New:
```python
elif flavor == "marimo":
    mode = os.getenv("MARIMO_MODE", "edit")
    command = "run" if mode == "publish" else "edit"
    args = [
        "uv", "run", "--no-project",
        "marimo", command,
        "--port=" + os.getenv("PORT"),
        "--host=0.0.0.0",
        *entrypoint,
    ]
```

### 4. Example Marimo Mod (mods/marimo/)

**Structure:**
```
mods/marimo/
├── pyproject.toml
├── app.py
└── README.md
```

**pyproject.toml:**
- Latest marimo version as dependency
- Flavor set to "marimo"
- Example weave mod configuration

**app.py:**
- Simple marimo notebook demonstrating weave integration
- Show practical examples of both edit and publish modes

**README.md:**
- Document edit vs publish modes
- Show how to set MARIMO_MODE
- Reference for best practices

## Data Flow

### Development Mode
1. User runs `./dev.py mods/marimo`
2. Optionally sets `MARIMO_MODE=publish` or `MARIMO_MODE=edit`
3. `dev-entrypoint.py` reads environment variable
4. Builds marimo command args with appropriate mode
5. Executes `uv run --no-project marimo [edit|run] ...`

### Production Mode
1. Docker build creates image with marimo-entrypoint.py
2. User runs container with optional `MARIMO_MODE=publish`
3. Container starts, entrypoint script reads environment variable
4. Executes `marimo [edit|run] --port=6637 --host=0.0.0.0 /app/src/app.py`
5. Mode can be changed by restarting container with different env var (no rebuild needed)

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid MARIMO_MODE value | Default to "edit" mode |
| Missing marimo dependency | Dev: auto-install via uv; Prod: build fails |
| Port conflicts | Use existing port configuration (6637) |
| Entrypoint script errors | Minimal - simple env var reading and exec |

## Testing Strategy

### Manual Testing Workflow

**Dev Mode:**
1. `./dev.py mods/marimo` (should use edit mode by default)
2. `MARIMO_MODE=edit ./dev.py mods/marimo` (should use edit mode)
3. `MARIMO_MODE=publish ./dev.py mods/marimo` (should use run mode)

**Production Build:**
1. Build: `./build.py mods/marimo`
2. Run without env var (should default to edit)
3. Run with `docker run -e MARIMO_MODE=publish ...` (should use run mode)

**Validation:**
- Edit mode: can modify cells, see editor UI
- Publish mode: read-only view, no editing controls
- Correct marimo command appears in logs
- Server accessible on port 6637

## Version Update Strategy

- Check latest marimo version and add to example mod's dependencies
- Existing mods (if any) remain at their current versions
- Example mod serves as reference for latest best practices
- No global version updates to avoid breaking existing mods

## Migration Path

**For existing mods:**
- No changes required
- Continue working as-is
- Can opt-in to mode switching by setting MARIMO_MODE

**For new mods:**
- Use `mods/marimo/` as template
- Include latest marimo version
- Document mode switching in README

## Future Enhancements

Potential future improvements (not in scope for this design):
- Additional marimo flags (--no-token, --headless variants)
- Per-mod default mode in pyproject.toml
- UI toggle for mode switching without restart
- Mode persistence in user preferences

## Implementation Checklist

- [ ] Create marimo-entrypoint.py wrapper script
- [ ] Update build.py to copy wrapper for marimo flavor mods
- [ ] Update dev-entrypoint.py to support MARIMO_MODE
- [ ] Create mods/marimo/ example mod with latest marimo version
- [ ] Test dev mode with both modes
- [ ] Test production build with both modes
- [ ] Update documentation/README if needed
