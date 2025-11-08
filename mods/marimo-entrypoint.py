#!/usr/bin/env python3
"""
Entrypoint wrapper for marimo mods in production.

Reads MARIMO_MODE environment variable to determine whether to run
marimo in edit mode (interactive) or run mode (read-only).

Environment Variables:
    MARIMO_MODE: "edit" or "run" (default)
    PORT: Port to run on (default: 6637)
"""

import os


def main():
    # Read mode from environment, default to "run" for production
    mode = os.getenv("MARIMO_MODE", "run").lower()

    # Validate and set command
    if mode == "edit":
        command = "edit"
    else:
        # Default to run for any other value (including "run" or invalid)
        command = "run"

    # Get port from environment (default is 6637)
    port = os.getenv("PORT", "6637")

    # Build command args
    args = [
        "marimo",
        command,
        "--headless",
        "--no-token",
        "--no-sandbox",
        f"--port={port}",
        "--host=0.0.0.0",
        "/app/src/app.py",
    ]

    # Replace current process with marimo
    os.execvp("marimo", args)


if __name__ == "__main__":
    main()
