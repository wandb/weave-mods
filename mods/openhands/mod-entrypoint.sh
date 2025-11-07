#!/bin/bash
set -eo pipefail

# Setup our mod-specific env
export SANDBOX_API_KEY=${WANDB_API_KEY}
export LLM_MODEL=${LLM_MODEL:-anthropic/claude-3-5-sonnet-20241022}
export LLM_API_KEY=${LLM_API_KEY:-${ANTHROPIC_API_KEY}}
cat <<EOF > /.openhands-state/settings.json
{
  "language": "en",
  "agent": "CodeActAgent",
  "max_iterations": null,
  "security_analyzer": null,
  "confirmation_mode": false,
  "llm_model": "$LLM_MODEL",
  "llm_api_key": "$LLM_API_KEY",
  "llm_base_url": null,
  "remote_runtime_resource_factor": null
}
EOF

# Setup DNS if running against *.k8s.wandb.dev for development
if [[ "$SANDBOX_REMOTE_RUNTIME_API_URL" == *"k8s.wandb.dev"* ]]; then
  if [ ! -z "$HOST_GATEWAY_IP" ]; then
    echo "Updating dnsmasq configuration with host-gateway IP: $HOST_GATEWAY_IP"
    sed -i "s/192.168.65.254/$HOST_GATEWAY_IP/g" /app/dnsmasq.conf
  else
    echo "Assuming our gateway IP is 192.168.65.254"
  fi

  # Start dnsmasq
  echo "Starting dnsmasq so wild cards work in development..."
  dnsmasq -C /app/dnsmasq.conf &
fi

# Start healthcheck
echo "Starting healthcheck..."
python /app/healthcheck.py &

# Call the original entrypoint with all passed arguments
exec /app/entrypoint.sh "$@"
