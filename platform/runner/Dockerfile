FROM ghcr.io/actions/actions-runner:2.337.0

USER root
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://dl.k8s.io/release/v1.34.1/bin/linux/${TARGETARCH}/kubectl" \
      -o /usr/local/bin/kubectl \
    && curl -fsSL "https://kind.sigs.k8s.io/dl/v0.32.0/kind-linux-${TARGETARCH}" \
      -o /usr/local/bin/kind \
    && chmod 755 /usr/local/bin/kubectl /usr/local/bin/kind \
    && mkdir -p /home/runner/.kube \
    && chown runner:runner /home/runner/.kube

COPY --chmod=755 platform/runner/entrypoint.sh /usr/local/bin/sem3-runner-entrypoint
USER runner
WORKDIR /home/runner
ENTRYPOINT ["/usr/local/bin/sem3-runner-entrypoint"]
