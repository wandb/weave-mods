#!/bin/bash
set -euxo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

cd ~/Development/OpenHands
docker build --load --push -t localhost:5001/mods/openhands-app -f ./containers/app/Dockerfile .

cd $SCRIPT_DIR
cp ~/Development/weave/weave/flow/prompt/prompt.py .
docker build . -t localhost:5001/mods/openhands:0.1.0 --push
