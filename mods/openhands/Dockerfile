# docker.all-hands.dev/all-hands-ai/openhands:main
FROM localhost:5001/mods/openhands-app:latest

LABEL \
    name="openhands" \
    version="0.1.0" \
    description="OpenHands is a tool for building mods for the Weave AI platform." \
    mod.secrets="WANDB_API_KEY,ANTHROPIC_API_KEY"

RUN useradd -l -m -u 999 -s /bin/bash enduser \
    && usermod -aG app enduser \
    && mkdir -p /home/enduser/.cache/huggingface/hub/ \
    && mkdir -p /home/enduser/.cache/ms-playwright/ \
    && chown -R enduser:app /.openhands-state \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -o Dpkg::Options::="--force-confold" dnsmasq iproute2 \
    && rm -rf /var/lib/apt/lists/*

# TODO: SANDBOX_LOCAL_RUNTIME_URL
ENV NO_SETUP=true \
    RUNTIME=remote \
    TZ=UTC \
    SANDBOX_USER_ID=999 \
    SANDBOX_REMOTE_RUNTIME_API_URL=http://sandbox.k8s.wandb.dev \
    SANDBOX_RUNTIME_CONTAINER_IMAGE=localhost:5001/mods/oh-runtime:latest

USER enduser
EXPOSE 6637

COPY mod-entrypoint.sh /app/mod-entrypoint.sh
COPY dnsmasq.conf /app/dnsmasq.conf
COPY healthcheck.py /app/healthcheck.py
# Temporary patch for prompt.py
COPY prompt.py /app/.venv/lib/python3.12/site-packages/weave/flow/prompt/prompt.py

ENTRYPOINT ["/app/mod-entrypoint.sh"]
CMD ["uvicorn", "openhands.server.listen:app", "--host", "0.0.0.0", "--port", "6637"]
