#! /usr/bin/env bash

set -euxo pipefail

echo "Generating manifest..."

uv run build.py --manifest --no-build
