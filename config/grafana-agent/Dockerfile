# Grafana Agent sidecar image — production observability.
#
# Why a wrapper image instead of bare `grafana/alloy`: we bake the
# River config into the image so the running container has no external
# config-file dependency. Secrets still come from env at runtime.
#
# Upgrade path: bump the `FROM` tag, rebuild, redeploy. River config
# format has been stable across v1.x; if Grafana releases a breaking
# change they publish a migration command (`alloy convert`).

FROM grafana/alloy:v1.4.2

# Alloy runs as the 'alloy' user by default (uid 473). Keep that —
# no privileged ops needed to scrape HTTP or dial outbound HTTPS.
USER 0
COPY config.river /etc/alloy/config.river
RUN chown alloy:alloy /etc/alloy/config.river
USER alloy

# Default command: run with the baked config. Env vars wire up the
# actual scrape target + remote_write endpoint; see config.river
# header for the required set.
ENTRYPOINT ["/bin/alloy"]
CMD ["run", "/etc/alloy/config.river", "--server.http.listen-addr=0.0.0.0:12345"]

# Alloy's own admin UI on 12345 — handy for debugging scrape lag or
# queue overflow. Don't expose publicly; keep it on the internal net.
EXPOSE 12345
