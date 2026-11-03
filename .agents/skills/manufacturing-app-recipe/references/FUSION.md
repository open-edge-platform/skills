<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Fusion Analytics reference (the correlator — core of `multimodal`/`vllm`/`agentic` modes)

No delegate skill exists for this component yet — author it from these
templates directly (Python, `paho-mqtt` + `influxdb` client + a small FastAPI
health/API app), matching the reference `fusion-analytics/` service
(`Dockerfile`, `fusion.py`, `api.py`, `requirements.txt`).

For MQTT sensor input, the simulator publishes raw points to
`{{TS_RAW_TOPIC}}` and Telegraf consumes that topic. The UDF publishes every
processed point to `{{TS_PROCESSED_TOPIC}}`; Fusion subscribes to this
processed topic, never the raw input topic. Keep Fusion's service-local
`TS_TOPIC` environment key, mapped to `{{TS_PROCESSED_TOPIC}}` in Compose.

## Responsibilities

1. Subscribe to **both** MQTT topics: `{{VISION_TOPIC}}` (DLSPS) and
  `{{TS_PROCESSED_TOPIC}}` (Time Series Analytics Microservice, *every*
  processed point — not just the alert-only topic).
2. Buffer each stream in a bounded rolling deque (`BUFFER_SIZE`, default
   `100`–`1000`).
3. Match one vision message with one sensor message whose timestamps are
   within `{{TOLERANCE_NS}}` of each other.
4. Apply `{{FUSION_MODE}}` (`AND`/`OR`) to the two per-modality anomaly
   flags to produce one fused decision.
5. Write the fused verdict + raw vision metadata to InfluxDB, and publish
   the fused verdict on `{{FUSION_TOPIC}}`.
6. (`vllm`/`agentic` modes) Serve the storage API (`api.py`, port `8080`)
   that the UI and `apm-agent` read. **Do not** publish `batch-complete` by
   default. In the reference format the user starts agent runs from the
   agentic UI's **Run Agentic Analysis** button, and VLM explanations from
   the **Explain** button. Automatic triggering is opt-in; see *Batching for
   the explanation layer (opt-in)* below.

## Required env

```
MQTT_BROKER=ia-mqtt-broker
MQTT_PORT=1883
VISION_TOPIC={{VISION_TOPIC}}
TS_TOPIC={{TS_PROCESSED_TOPIC}}          # service-local key; subscribes to the UDF output, not raw sensor input
FUSION_TOPIC={{FUSION_TOPIC}}
BUFFER_SIZE=100
TOLERANCE_NS={{TOLERANCE_NS}}            # e.g. 50e6 = 50 ms
FUSION_MODE={{FUSION_MODE}}              # "AND" or "OR" — validate at startup, raise on anything else
INFLUXDB_HOST=ia-influxdb
INFLUXDB_PORT=8086
INFLUXDB_DB=datain
INFLUXDB_USERNAME=${INFLUXDB_USERNAME}
INFLUXDB_PASSWORD=${INFLUXDB_PASSWORD}

FUSION_MEASUREMENT=fusion_result         # keep the reference name; the UI and agent read it
VISION_MEASUREMENT={{VISION_MEASUREMENT}}

# agentic mode, ONLY when {{AGENT_TRIGGER}} is `size` or `time` (opt-in; the
# reference default `ui` sets none of these)
MQTT_BATCH_TOPIC=apm/batch-complete
BATCH_TRIGGER_MODE={{AGENT_TRIGGER}}     # "size" or "time" — validate at startup
BATCH_SIZE={{BATCH_SIZE}}                # confirmed defects per run, when size (e.g. 10)
BATCH_INTERVAL_S={{BATCH_INTERVAL_S}}    # seconds between runs, when time (e.g. 300)
BATCH_MIN_INTERVAL_S={{BATCH_MIN_INTERVAL_S}}  # cooldown >= one agent run (CPU LLM: ~120-300 s)
```

## Timestamp handling — the trickiest part

- **Vision side:** timestamp comes from
  `payload["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"]` — only present
  when the DLSPS pipeline set `add-reference-timestamp-meta=true` on
  `rtspsrc` **and** `add-rtp-timestamp=true` on `gvametaconvert` (see
  [PIPELINE.md](PIPELINE.md)). If that key is missing, log a warning and skip
  multimodal for that frame rather than crashing — DLSPS may omit it for the
  first ~300 packets after a (re)start.
- **Sensor side:** timestamp comes from the TICKscript alert's
  `{{ index .Time }}` field, formatted like
  `"YYYY-MM-DD HH:MM:SS.fffffffff +0000 UTC"`. Parse it defensively — accept
  a space or `T` separator, optional fractional seconds up to 9 digits, and
  an optional (sometimes duplicated) timezone offset suffix. See the
  reference `parse_ts_string_to_ns()` for the exact regex-based parser; reuse
  it verbatim rather than a naive `datetime.strptime` (the reference
  implementation exists specifically because Kapacitor's raw timestamp
  string format is inconsistent across builds).
- Convert **both** sides to epoch nanoseconds on ingest so
  `find_nearest()`/tolerance comparisons are a plain integer `abs(diff)`
  check against `{{TOLERANCE_NS}}`.

## Multimodal algorithm — first-come-first-served pairing

Do not naively fuse "latest vision + latest sensor" — messages arrive at
different rates and out of lockstep. Use first-come-first-served pairing:

1. Peek the oldest message in each queue.
2. Whichever queue's oldest message has the smaller timestamp is the
   **source**; pop it.
3. Search the **other** queue for the entry with the nearest timestamp
   (`find_nearest`); if the nearest diff exceeds `{{TOLERANCE_NS}}`, there is
   no match — do not block waiting for one. What happens next depends on
   `{{FUSION_MODE}}`:
   - `AND`: an unmatched source can never satisfy `AND` on its own, so emit
     no fused alert (both per-modality anomaly flags recorded as `0`).
   - `OR`: an unmatched source's own anomaly flag is already sufficient to
     satisfy `OR`, so if the source message is itself anomalous, still
     publish a fused verdict using only the source's flag (the missing
    modality's flag recorded as `0`); if the source message is not anomalous,
    emit no fused alert. Publish and persist every such verdict. Set the
    missing modality's timestamp and `delta_ms` to JSON `null` in MQTT; omit
    unavailable fields from the InfluxDB point so they read as null there.
4. If a match is found, pop it from the target queue too and combine the two
   per-modality anomaly flags with `{{FUSION_MODE}}`:
   - `AND`: fused anomaly = `vision_anomaly AND timeseries_anomaly`
   - `OR`: fused anomaly = `vision_anomaly OR timeseries_anomaly`
5. When labels disagree between modalities, resolve one human-readable label
   by taking whichever side has higher confidence (see
   `combine_classifications()` in the reference implementation) — do not
   just report both labels unresolved, downstream Grafana panels expect one
   `predicted_category` string.

## InfluxDB writes — two separate concerns

- **Raw vision metadata** — write every vision message to a
  `VISION_MEASUREMENT` (e.g. `vision-weld-classification-results`) regardless
  of multimodal outcome, tagged with `label`/`confidence`/`search_time`, so
  Grafana can show a vision-only trend even when no sensor match was found.
  This happens in the MQTT `on_message` callback, not in the multimodal step.
  `search_time` (the RTP sender timestamp in ns) and the fields `frame_id`
  and `img_handle` are **required** in `vllm`/`agentic`: the UI's Explain
  flow joins on them to fetch the stored frame. See
  [`UI_SERVICE.md`](UI_SERVICE.md#data-contract).
- **Fused verdict** — write every verdict published to `{{FUSION_TOPIC}}` to
  a separate `FUSION_MEASUREMENT` (keep the reference name `fusion_result`;
  the UI and agent default to it). Store `vision_timestamp` and
  `timeseries_timestamp` as epoch-ns integers and `frame_id` as a field.
  Include both source timestamps and the timestamp delta for matched pairs;
  for unmatched `OR` verdicts, set the missing modality's timestamp and the
  delta to JSON `null` in the MQTT payload and omit those unavailable fields
  from the InfluxDB point (they read as null in queries). Always include
  `{{FUSION_MODE}}` and the fused decision.

## MQTT publish — the fused verdict

```json
{
  "fused_decision": 1,
  "mode": "{{FUSION_MODE}}",
  "vision_anomaly": 1,
  "timeseries_anomaly": 0,
  "predicted_category": "Porosity with Excessive Penetration",
  "vision_time": "2026-09-08T12:00:00.123Z",
  "timeseries_time": "2026-09-08T12:00:00.150Z",
  "delta_ms": 27.0
}
```

Publish this to `{{FUSION_TOPIC}}` with QoS 1. Keep the payload **flat JSON
with scalar `fused_decision`**, not a nested object — Grafana's MQTT
datasource plots scalars directly; a nested/array payload breaks the panel
(same caveat as `metro-ai-app-recipe`'s count-topic rule).

**OpenMES (`{{OPENMES_ENABLED}}=yes`):** this fused verdict is the **only**
input for OpenMES publishing in `multimodal`/`vllm`/`agentic` modes.
- The publisher reports `fused_decision == 1` from `{{FUSION_TOPIC}}`.
- It never subscribes to `{{VISION_TOPIC}}`, `{{TS_PROCESSED_TOPIC}}` or
  `{{SENSOR_ALERT_TOPIC}}`, which would duplicate modality-level reports.
- Keep the `vision_time`/`timeseries_time` keys exactly as above. The
  publisher uses whichever one is non-null as the event timestamp.
- Fusion Analytics needs no code change.

See [`OPENMES.md`](OPENMES.md).

## Health/API surface

Expose the reference FastAPI app (`api.py`) on port `8080`: `/health`
for the container healthcheck, plus `/detections`, `/detections/summary`,
`/detections/labels` and `/detections/max_id`. In `agentic` mode
`apm-agent` reads these through `STORAGE_SERVICE_URL`; the exact response
shapes it needs (including `frame_id` per row) are in
[`AGENTIC.md`](AGENTIC.md#storage-api-contract-the-agent-depends-on).
Copy the reference `api.py` and change only names.

**InfluxQL injection — keep the guard when adapting.** Every user-supplied
filter must be validated before it reaches a query: the reference
`/detections?label=...` checks `_SAFE_LABEL_RE.fullmatch(label)` (400 on
failure) and passes the value as a bind parameter (`$label`). Numeric filters
are typed FastAPI `Query` parameters. Do not drop either guard, and never
interpolate a raw string parameter into InfluxQL.

## Batching for the explanation layer (opt-in)

**Default (`{{AGENT_TRIGGER}}=ui`, the reference format): Fusion Analytics
publishes nothing for the explanation layer.** VLM explanations are
requested per row from `/insights-ui/` (Explain), and agent runs from
`/agentic-ui/` (Run Agentic Analysis, which publishes `apm/batch-complete`
itself). `vllm` mode has no batch topic at all.

Only when the user explicitly asks for **automatic** agent runs in
`agentic` mode (`{{AGENT_TRIGGER}}=size` or `time`), add this to Fusion
Analytics:

- Record the time of every **confirmed** verdict (`fused_decision == 1`),
  not every pairing. At 10 fps a defective part yields about 10 per second.
- `size`: flush when at least `BATCH_SIZE` confirmed verdicts have
  accumulated **and** `BATCH_MIN_INTERVAL_S` has passed since the last flush.
  `time`: flush every `BATCH_INTERVAL_S` if any accumulated. Use a background
  thread, never a sleep in the MQTT callback.
- Set `BATCH_MIN_INTERVAL_S` to at least one agent run's duration (a CPU
  agent LLM run is about 2–5 min). Without it, runs queue up far faster
  than they complete (observed: 65 queued batches within minutes).
- On flush, publish the same payload the UI's Run publishes
  (`{"run_id", "status": "completed", "device", "video_filename",
  "start_id", "end_id", "pipeline_status"}`), where `start_id`/`end_id` are
  epoch-ns bounds with `start_id < end_id`. `apm-agent` rejects anything
  else. The rows themselves are read from the storage API, never carried
  in MQTT.

## Verifying multimodal end-to-end

```bash
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '{{FUSION_TOPIC}}' -p 1883
docker exec -it ia-influxdb influx -username <user> -password <pass> \
  -execute 'use datain; select * from "<multimodal-measurement>"'
```

Confirm a fused message appears **only** after both a vision anomaly and a
sensor anomaly (for `AND`) or either one, matched **or unmatched** (for
`OR`) land within/without `{{TOLERANCE_NS}}` — inject one modality's anomaly
without the other and confirm the multimodal behavior matches `{{FUSION_MODE}}`
exactly (if `{{GENERATE_TESTS}}=yes`, this is the single most important test
in [`TESTS.md`](TESTS.md); otherwise verify it manually). Confirm every
published verdict, including unmatched `OR` verdicts, is present in
`FUSION_MEASUREMENT` with unavailable timestamp/delta fields reading as null.
