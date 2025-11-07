#!/bin/bash

# Resolve host-gateway to an IP
HOST_GATEWAY_IP=$(getent hosts host.docker.internal | awk '{ print $1 }')

if [ -z "$HOST_GATEWAY_IP" ]; then
  echo "Error: Unable to resolve host-gateway IP!"
  exit 1
fi

# Update dnsmasq configuration
echo "address=/k8s.wandb.dev/$HOST_GATEWAY_IP" >> /etc/dnsmasq.conf

# Start dnsmasq
dnsmasq --no-daemon
