# Set default registry
registry := "localhost:5001/mods"

# Conditionally add --push flag
push := env_var_or_default("PUSH", "")
docker-flags := if push != "" { "--load --push" } else { "--load" }

ref := `git branch --show-current`

# Check if user needs to authenticate for packages
_check-gh-auth:
    #!/usr/bin/env bash
    set -euxo pipefail
    if ! gh auth status -t 2>&1 | grep -q "read:packages"; then
        gh auth login -s read:packages
    fi

# Build development image
build-dev:
    docker build . -f Dockerfile.dev --tag {{registry}}/dev {{docker-flags}}

docker-ghlogin token=`gh auth token` user=`gh api user -q .login`: _check-gh-auth
    echo {{token}} | docker login ghcr.io -u {{user}} --password-stdin

build-mod directory ref=ref:
    gh workflow run build_mods.yaml -f directory={{directory}} --ref={{ref}}
    sleep 3
    gh run watch
