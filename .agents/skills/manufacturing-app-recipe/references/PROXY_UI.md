<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Nginx + Grafana + Mosquitto + (multimodal family) SeaweedFS reference

Two topologies share this file: the flat `{{STACK_DIR}}/` used by
`multimodal`/`vllm`/`agentic` modes (eleven-plus containers, SeaweedFS S3 +
WebRTC), and the `apps/<name>/` convention used by `ts` mode (seven
containers, no vision/WebRTC/S3). Read only the section for your mode.

## Nginx — single TLS entrypoint, path-based routing

One `server { listen ${GRAFANA_PORT_INTERNAL} ssl; }` block, self-signed cert
generated at container start (`nginx-cert-gen.sh`, mounted to a tmpfs volume
so the cert regenerates fresh each deploy).

### `multimodal`/`vllm`/`agentic` routes

| Path | Proxies to | Notes |
|---|---|---|
| `/ts-api` | `ia-time-series-analytics-microservice:5000` | `rewrite ^/ts-api/(.*)$ /$1 break` — strips prefix |
| `/dsps-api/` | `dlstreamer-pipeline-server:8080` | trailing slash on both sides — no rewrite needed |
| `/image-store` | `seaweedfs-filer:8888` | needs `sub_filter` rewrites on `href=`/`action=`/`fetch(`/`location.href=` so the filer's browser UI's absolute links stay under `/image-store/` |
| `/{{peer-id}}/whip\|whep` | `${MEDIAMTX_SERVER}:${WHIP_SERVER_PORT}` (regex match) | WebRTC signalling; needs `Upgrade`/`Connection: upgrade` headers + long timeouts (300s) for long-lived WebRTC negotiation |
| `/{{peer-id}}/` (prefix, non-signalling) | MediaMTX WHEP/HLS asset paths | separate `location ^~` block below the exact regex match so static asset requests don't fall through to `/` |
| `/` | `ia-grafana` | default catch-all |

### Profile routes — `vllm`/`agentic` (`NGINX_PROFILE`)

Copy the reference `nginx.conf.template` + `nginx-cert-gen.sh` unchanged
(apart from the `peer-id` path). The template `include`s
`/opt/nginx/certs/nginx-extra-locations.conf`, which `nginx-cert-gen.sh`
renders at container start from the `NGINX_PROFILE` env var that the
Makefile target exports:

| `NGINX_PROFILE` (set by) | Extra locations | Default / stream timeouts |
|---|---|---|
| `base` (`make up`) | none (empty include) | 60 s / 300 s |
| `vllm` (`make up_vllm`) | `= /insights-ui` → 308 to `/insights-ui/`; `/insights-ui/` → `multimodal-agentic-ui:5003` | 180 s / 180 s (VLM calls are slow) |
| `agentic` (`make up_agentic`) | the `vllm` ones + `/agentic-ui/` → `multimodal-agentic-ui:5003`; `/api/metrics/` → `apm-metrics:9090/metrics/` (SSE, `proxy_buffering off`); `/api/v1/capabilities` → `apm-metrics:9090` | 60 s / 300 s |
| `agentic_mcp` (`make up_agentic MCP=true`) | the `agentic` ones + `= /mcp` → `multimodal-mcp-server:8000` | 60 s / 300 s |

- Proxy optional upstreams (`apm-metrics`, the MCP server) through a
  variable with `resolver 127.0.0.11`, as the reference does, so nginx
  starts even before those containers exist. Upstreams referenced directly
  (`dlstreamer-pipeline-server`, `ia-grafana`, ...) must be in nginx's
  `depends_on`; otherwise nginx exits with `host not found in upstream`.
- **Same-origin rule.** The explanation UIs are reachable only as
  `https://<HOST_IP>:${GRAFANA_PORT}/insights-ui/` and `/agentic-ui/` and are
  embedded in Grafana as iframes. Never publish `multimodal-agentic-ui`,
  `apm-agent` or `vllm-server` on a separate host port for browser use, and
  never add a raw-API route (for example `/agent-api/`) as the user-facing
  way to see results. Same origin is what makes Run and Explain work
  without a second certificate prompt or CORS.
- Add `multimodal-agentic-ui` and `apm-metrics` to nginx's
  `no_proxy`/`NO_PROXY`.

Reuse `metro-ai-app-recipe`'s WHIP/WHEP + `--noproxy '*'` guidance from
[`PROXY_UI.md`](../metro-ai-app-recipe/references/PROXY_UI.md) verbatim for
the MediaMTX signalling block; the only difference here is the additional
`/ts-api`, `/dsps-api/`, and `/image-store` proxies this topology needs that
`metro-ai-app-recipe` doesn't.

### `ts` mode routes

| Path | Proxies to | Notes |
|---|---|---|
| `/ts-api/` | `ia-time-series-analytics-microservice:5000` | rewrite strips the `/ts-api` prefix, same rule as `multimodal`/`vllm`/`agentic` |
| `/` | `ia-grafana` | default catch-all |

Optionally uncomment the `stream { ... }` block at the top of `nginx.conf`
to also TLS-proxy raw MQTT on port `1883` for external (non-Compose-network)
MQTT clients — most deployments don't need this since MQTT stays internal to
`timeseries_network`; only enable it if a real external device/consumer must
reach the broker directly. No WebRTC/video routes in `ts` mode — there is no
vision component.

## Grafana — InfluxDB datasource + MQTT (optional) + WebRTC iframe (`multimodal`/`vllm`/`agentic`)

`configs/grafana/provisioning/datasources.yml` — one InfluxDB datasource is
**required** (multimodal/vision/sensor measurements all live there); an MQTT
datasource (`grafana-mqtt-datasource` plugin, same caveat as
`metro-ai-app-recipe`: pin to a Grafana version the plugin supports) is
**optional**, only add it if the dashboard needs a live low-latency panel on
`{{FUSION_TOPIC}}` in addition to the InfluxDB-backed historical panels:

```yaml
datasources:
  - name: InfluxDB
    type: influxdb
    access: proxy
    url: http://$INFLUX_SERVER:8086
    user: $INFLUXDB_USERNAME
    password: $INFLUXDB_PASSWORD
    database: $INFLUXDB_DB
    basicAuth: true
    basicAuthUser: $INFLUXDB_USERNAME
    isDefault: true
    jsonData: { graphiteVersion: "1.1" }
    secureJsonData:
      basicAuthPassword: $INFLUXDB_PASSWORD
      password: $INFLUXDB_PASSWORD
```

Dashboards live in `configs/grafana/dashboards_jsons/` and are copied into
`provisioning/` by the `up*` target (see `INSTALL.md`). There is one file
per mode: `{{DASHBOARD_SLUG}}.json` (`multimodal`),
`{{DASHBOARD_SLUG}}_vlm.json` (`vllm` and `agentic`) and
`{{DASHBOARD_SLUG}}_agentic.json` (`agentic`). The `_vlm`/`_agentic`
files are copied from the reference in Grafana's **v2** dashboard schema
and keep their `/insights-ui/` and `/agentic-ui/` iframes. Their
change list is in [`UI_SERVICE.md`](UI_SERVICE.md#dashboards--three-files-same-as-the-reference).
The base `{{DASHBOARD_SLUG}}.json` (classic schema) needs at
minimum:

- **WebRTC `<iframe>` panel** — `src="/<peer-id>/whep"` or whatever exact
  path your Nginx WHEP route resolves to; requires
  `GF_SECURITY_ALLOW_EMBEDDING=true` + `GF_PANELS_DISABLE_SANITIZE_HTML=true`
  env vars on the Grafana container, otherwise the iframe is stripped.
- **Sensor trend panel** — InfluxDB query against
  `{{SENSOR_MEASUREMENT}}-anomaly-data`.
- **Multimodal verdict table/stat panel** — InfluxDB query against the multimodal
  measurement, or an MQTT panel on `{{FUSION_TOPIC}}` if the MQTT datasource
  is configured.
- Grafana's minimum refresh interval is 5 s — tell the user in the README
  that graph/video sync may lag by a few seconds; this is expected, not a
  bug.
- Embed other same-origin pages only as iframes. A relative `<a
  href="/...">` inside a Grafana text panel is caught by Grafana's
  client-side router and shows "Page not found".

## Grafana — one dashboard file per app (`ts` mode)

Unlike `multimodal`/`vllm`/`agentic`'s `dashboards_jsons/` directory convention,
the `ts` repo mounts a **single file directly**:

```yaml
volumes:
  - ./apps/${SAMPLE_APP}/grafana-dashboard.json:/etc/grafana/provisioning/dashboards/grafana-dashboard.json
```

Which means switching `SAMPLE_APP` (via `app=` on `make up_*`) automatically
swaps the provisioned dashboard on the next `docker compose up` — no
copy-into-provisioning step is needed here (contrast with the `multimodal`
family's `Makefile`, which must `rm`+`cp` because it uses a directory of
JSON files instead).

`ts` mode's dashboard JSON needs at minimum:

- **Sensor trend panel(s)** — InfluxDB query against
  `{{SENSOR_MEASUREMENT}}` (raw) and `{{SENSOR_MEASUREMENT}}-anomaly-data` or
  equivalent (UDF output), so both raw and flagged data are visible together.
- **Alert/anomaly indicator** — a stat/table panel highlighting rows where
  `anomaly_status > 0`.
- No WebRTC/video panel needed — this stack has no vision component.

`configs/grafana/dashboards/datasources.yml` (repo-root, shared across all
`ts`-mode apps) provisions the InfluxDB datasource — do not duplicate it per
app; only `grafana-dashboard.json` is per-app.

## Mosquitto

Minimal `mosquitto.conf` is sufficient for either topology (no TLS/ACL
needed inside the Compose network):

```
allow_anonymous true
listener 1883
```

Tighten this (ACLs, TLS listener, auth) only if a real (non-simulator) sensor
device connects over the network rather than from inside the Compose
network.

## SeaweedFS — S3-compatible stored-frame storage (`multimodal`/`vllm`/`agentic` only)

Four services: `seaweedfs-master` (metadata), `seaweedfs-volume` (blob
storage), `seaweedfs-filer` (POSIX-like directory view + the `/image-store`
UI proxied above), `seaweedfs-s3` (S3 gateway DLSPS's `s3_write` destination
talks to). Bring them up in that dependency order
(`master → volume → filer → s3`, each with a `depends_on` + healthcheck gate).
No SeaweedFS component in `ts` mode — there is no vision component to store
frames for.

`seaweedfs-s3` needs `DEFAULT_S3_BUCKETS=dlstreamer-pipeline-results` (or
whatever bucket name `PIPELINE.md`'s `s3_write.bucket` uses) baked into its
init script so the bucket exists before DLSPS's first frame write; also set
`S3_BUCKET_TTL` (e.g. `30m`) so stored frames don't grow the disk unbounded —
this is a demo/production-lite retention knob, not meant for long-term
archival.
