<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OpenMES defect publishing (optional, opt-in, all modes)

Load this file only when `{{OPENMES_ENABLED}}=yes`. It covers a
bare-minimum path:
- a plain Python script, `openmes_publisher.py`, runs on the host (no
  container);
- it subscribes to the stack's existing result topic on MQTT and filters
  defect events;
- it posts each one to a self-hosted
  [OpenMES](https://github.com/Mes-Open/OpenMes) as a quality **Issue**.

Copy [`../assets/openmes/openmes_publisher.py`](../assets/openmes/openmes_publisher.py)
verbatim, and template
[`../assets/openmes/openmes-publisher.json`](../assets/openmes/openmes-publisher.json)
for this stack.

**Non-goals:**
- syncing Issue state back (acknowledge/resolve/close);
- uploading images;
- rolling defects up per unit or lot;
- scrap or quality-check records;
- exactly-once delivery.

Publishing failures must never block inference, fusion or alerting. The
publisher is a separate process that only reads MQTT.

## OpenMES API contract

- **Endpoint:** `POST {{OPENMES_BASE_URL}}/api/v1/issues`.
- **Auth:** `Authorization: Bearer <token>` (a Sanctum user token).
- **Success:** HTTP `201`, with the new Issue's ID in `data.id`.
- **Fields:**

  | Field | Required | Rule |
  |---|---|---|
  | `work_order_id` | yes | integer; must exist |
  | `issue_type_id` | yes | integer; must exist |
  | `title` | yes | ≤ 255 chars |
  | `batch_step_id` | no | integer; must exist |
  | `description` | no | ≤ 5000 chars |

- **No custom metadata fields.** OpenMES rejects unknown top-level fields,
  so event metadata goes into `description` as compact JSON. Events whose
  description would exceed 5000 chars are logged and skipped.
- **Token lifetime.** Tokens from `POST /api/auth/login` expire after
  `DEFAULT_TOKEN_TTL_MINUTES`, which defaults to **15 min**. With the default,
  the token file stops working within 15 minutes and every event is marked
  `blocked`. Before enabling this, the OpenMES admin must either raise
  `DEFAULT_TOKEN_TTL_MINUTES` (a global OpenMES setting covering every
  login token) or rotate the token file externally. The script re-reads
  the file on every request, so rotation needs no restart.
- **Blocking issue types.** If the issue type has `is_blocking=true`,
  OpenMES blocks the whole work order on every Issue. Use a non-blocking
  issue type, such as "Quality – AI detected", unless the user explicitly
  wants line-stopping behaviour.
- **No ERP API keys.** The ERP API keys (`/api/v1/erp/*`) cannot create
  Issues; use a dedicated user's token.

## Config keys (`openmes-publisher.json`) and secrets

| Key | Parameter | Notes |
|---|---|---|
| `mode` | `{{OPENMES_SOURCE_MODE}}` | `vision` \| `ts` \| `multimodal`. Use `multimodal` for `vllm`/`agentic` too |
| `source_id` | `{{OPENMES_SOURCE_ID}}` | station/line identifier; appears in the title and dedupe key |
| `openmes.base_url` | `{{OPENMES_BASE_URL}}` | prefer `https://` |
| `openmes.token_file` | `{{OPENMES_TOKEN_FILE}}` | path to a file holding the token; **never the token value** |
| `openmes.work_order_id`, `openmes.issue_type_id`, `openmes.batch_step_id` | `{{OPENMES_WORK_ORDER_ID}}`, `{{OPENMES_ISSUE_TYPE_ID}}`, `{{OPENMES_BATCH_STEP_ID}}` | existing OpenMES IDs supplied by the user; `batch_step_id` may be `null` |
| `mqtt.host`/`port`/`topic`/`client_id` | `MQTT_HOST`, `MQTT_PORT`, `{{OPENMES_INPUT_TOPIC}}` | the script runs on the host, so `host` is `127.0.0.1` with the broker port published on loopback (see *Broker reachability*). `client_id` must be unique per publisher |
| `mqtt.username`/`password_file`/`tls`/`ca_file` | optional MQTT auth/TLS | only when the broker requires them |
| `fields` | — | JSON Pointers into the payload (see *Per-mode input*). `timestamp` may be one pointer or a list of fallbacks |
| `timestamp_format` | — | `iso8601` \| `kapacitor` \| `unix_ns` \| `unix_s` |
| `defect_equals` | — | `ts`/`multimodal`: the defect flag value (default `1`) |
| `defect_labels`, `min_confidence` | `{{OPENMES_DEFECT_LABELS}}`, `{{OPENMES_MIN_CONFIDENCE}}` | `vision` only. Labels must be non-empty and must never include the good/normal class; `min_confidence` defaults to `0.8` |
| `details` | — | optional extra JSON Pointers copied into `description` |
| `tls_ca_file` | — | CA bundle for an OpenMES on a private CA. Never disable verification |
| `use_env_proxy` | — | default `false`: ignore the host's `http(s)_proxy` for OpenMES calls. A corporate proxy cannot reach a LAN OpenMES and returns 504 |
| `sqlite_db` | — | dedupe/state store (default `openmes_events.db`) |

**Secrets:**
- Never put the bearer token in the config, in source-controlled files, in
  chat or in the final summary.
- The user creates the token file and restricts it with
  `chmod 0400 ./openmes_token`. Add `openmes_token` and `openmes_events.db`
  to `.gitignore`.
- The script never logs the token.

## Per-mode input (publish from exactly one topic)

| `{{DEPLOYMENT}}` | `mode` | `{{OPENMES_INPUT_TOPIC}}` | `fields` | `timestamp_format` |
|---|---|---|---|---|
| `multimodal`/`vllm`/`agentic` (scaffolded from the reference) | `multimodal` | `fusion/anomaly_detection_results` only | `defect: /fused_decision`, `label: /fusion_classification` (added to the payload by the scaffold), `timestamp: /time` | `iso8601` |
| `multimodal`/`vllm`/`agentic` (hand-written per `FUSION.md`) | `multimodal` | `{{FUSION_TOPIC}}` only | `defect: /fused_decision`, `label: /predicted_category`, `timestamp: ["/vision_time", "/timeseries_time"]` | `iso8601` |
| `ts` | `ts` | `{{ALERT_TOPIC}}` (requires `{{ALERT_CHANNEL}}=mqtt`) | `defect: /anomaly_status`, `label: /predicted_category` (optional), `timestamp: /time` | `kapacitor` |
| `vision` | `vision` | `{{VISION_TOPIC}}` (DLSPS MQTT metadata) | `label: /metadata/objects/0/classification~1Model0/label`, `confidence: …/confidence`, `timestamp: /metadata/rtp/sender_ntp_unix_timestamp_ns`, `item_id: /metadata/frame_id` | `unix_ns` |

- **Fused modes: the fused topic only.** Never also subscribe to
  `{{VISION_TOPIC}}` or `{{SENSOR_ALERT_TOPIC}}`; each defect would then be
  reported up to three times (see [`FUSION.md`](FUSION.md)).
- **`ts`:** the publisher needs the TICKscript's MQTT alert, so OPC-UA
  alerting is incompatible. Switch the single alert channel to `mqtt`, and
  never enable both (see [`ANALYTICS.md`](ANALYTICS.md)). Make the alert's
  `.message(...)` emit valid JSON containing `time` and `anomaly_status`.
- **`vision`:** a metadata stream must exist, so it requires the
  `dlsps-user` sub-path with an MQTT metadata destination (see
  [`PIPELINE.md`](PIPELINE.md) / [`DEMO_POC.md`](DEMO_POC.md)).
  - JSON Pointer escapes `/` inside a key as `~1`, as in
    `classification~1Model0`.
  - For a detector, use `/metadata/objects/0/detection/label`.
  - If the RTP timestamp is absent (no `rtspsrc`), use
    `timestamp: "/metadata/time"` or another per-frame time the pipeline
    emits. Check one real message first.
  - **Flood warning:** every frame showing a defect is a distinct event,
    so a static defect at 10 fps creates 10 Issues per second. Keep
    `min_confidence` high, and confirm the user accepts per-frame Issues
    before enabling this for vision.

## Broker reachability (the script runs on the host)

Neither reference stack publishes the Mosquitto port to the host, so add a
loopback-only mapping. The broker allows anonymous access, so never bind
it to `0.0.0.0`.

- **`multimodal`/`vllm`/`agentic`:** in the generated stack's
  `docker-compose.yml`, add `ports: ["127.0.0.1:1883:1883"]` under
  `ia-mqtt-broker`. Do this only when `{{OPENMES_ENABLED}}=yes`.
- **`ts`:** don't edit the shared `docker-compose.yml`. Add a repo-root
  `docker-compose.override.yml`:

  ```yaml
  services:
    ia-mqtt-broker:
      ports:
        - "127.0.0.1:1883:1883"
  ```

  Plain `make up_*_ingestion` runs `docker compose up` without `-f`, so it
  loads the override automatically. The validation targets pass explicit
  `-f` files and skip it.
- **`vision`:** the publisher connects to whatever broker the DLSPS demo
  publishes to, again on loopback.

## Generated files and startup

Place these beside the stack, in `{{STACK_DIR}}/openmes/` or
`{{TS_REPO_DIR}}/apps/{{APP_NAME}}/openmes/`:

```
openmes/
├── openmes_publisher.py      # copied verbatim from assets/openmes/
├── openmes-publisher.json    # templated for this stack/mode; no secrets
├── openmes_token             # user-provided, chmod 0400, git-ignored; never generated with a real secret
└── dummy_openmes_receiver.py # only when testing without a real OpenMES (see below)
```

Also add a short "OpenMES publishing" section to the generated `README.md`
with the run steps:

```bash
cd openmes
python -m venv .venv && . .venv/bin/activate
pip install paho-mqtt requests
python openmes_publisher.py --config ./openmes-publisher.json
```

Start the publisher **after** the stack is up. Keep it in a dedicated
foreground terminal and stop it with Ctrl-C. Persistent service deployment
requires a separate, explicitly approved service-management plan.

## Reliability model

- **Dedupe:** `event_id` is a SHA-256 of `source_id`, `mode`, the IDs,
  the label, `observed_at` (normalized to UTC) and `item_id`. It is stored
  in SQLite **before** the POST, so a replayed MQTT message, including one
  after a restart, logs `Duplicate event ignored` and creates no Issue.
- **Delivery states:**

  | State | Meaning |
  |---|---|
  | `delivered` | `201`; `issue_id` stored |
  | `blocked` | `401`/`403`: fix the token or permissions |
  | `rejected` | `400`/`404`/`422`: bad IDs or body |
  | `ambiguous` | a timeout, network error or other status; the Issue may or may not exist |

- **No automatic retries.** Re-delivering would risk a double Issue, so
  `blocked`, `rejected` and `ambiguous` events need manual reconciliation
  against OpenMES (inspect the `events` table).
- **Guarantee:** at-least-once-ish, with local dedupe. Not exactly-once.

## Testing without a real OpenMES (dummy receiver)

Use this only when the user explicitly asks to test without OpenMES. Copy
[`../assets/openmes/dummy_openmes_receiver.py`](../assets/openmes/dummy_openmes_receiver.py)
into the stack's `openmes/` folder. It needs only the Python standard library.

- **What it implements:** the same Issues API the publisher calls
  (`POST`/`GET /api/v1/issues`, `GET /api/v1/issues/<id>`). It checks the
  bearer token, applies the contract's validation (`201` / `401` / `422` /
  `400` / `413`), and accepts work orders `1001`, `2001`, non-blocking issue
  type `7` and batch step `501`. Override them with `--work-order-id`,
  `--issue-type-id` and `--batch-step-id`.
- **How it shows alerts:** a live page at `http://<host>:8099/` (refreshes
  every 2 s, with totals, per-defect counts, alerts in the last minute,
  401/422 rejections, and a click-to-expand row for each alert), plus one
  `ALERT #<id> | ...` console line per issue. It also appends each issue to a
  JSONL log (`--log-file`).
- **Config:** point `openmes-publisher.json` at it
  (`"base_url": "http://127.0.0.1:8099"`, `work_order_id` `1001`/`2001`,
  `issue_type_id` `7`). These dummy IDs are allowed **only** in this mode.
- **Token:** generate a throwaway token locally,
  `(umask 077; openssl rand -hex 24 > openmes_token); chmod 0400 openmes_token`.
  Pass the same file to both processes. Never reuse a real OpenMES token.
- **Scaffolded stacks:** `scaffold_stack.py` with `openmes.dummy: true` does all of
  this: it copies the receiver, generates the throwaway token and writes the
  config with the test IDs. It also writes `openmes/start_dummy_openmes_receiver.sh`
  (binds to `HOST_IP`, runs the receiver in the **foreground**) and
  `openmes/start_dummy_openmes_publisher.sh` (waits for `/health`, then runs the
  publisher in the **foreground**). Both `exec` the Python process — there is
  no `&`, no `nohup`/`disown`/`setsid`, no PID file and no separate stop
  script, because a backgrounded (`cmd &`) job is reparented to init and
  keeps running after the launching shell exits; it is **not** scoped to
  that shell's lifetime, so a script that claimed otherwise would be wrong.
  A plain foreground process has no such gap: it only runs for as long as
  something is actively attached to it.
- **Start:** run each script where something stays attached to it for as
  long as the process should run — never via shell `&`/`nohup`/`disown`:
  - **If your tool has its own attached background/async execution** (run
    in the background but still tied to, and stoppable from, this session —
    e.g. an agent's "async" bash mode, not a detached/independent process):
    start `start_dummy_openmes_receiver.sh` that way, poll
    `http://<host>:8099/health` until it answers, then start
    `start_dummy_openmes_publisher.sh` the same way. Stop both explicitly
    with that same tool's stop capability when done.
  - **Otherwise (plain shell only, or a human running this by hand):** run
    `start_dummy_openmes_receiver.sh` in one terminal and
    `start_dummy_openmes_publisher.sh` — which waits for `/health` itself
    before exec'ing the publisher — in a second terminal. Stop each with
    Ctrl-C.
  The page has no login, so bind a LAN address (`--host 0.0.0.0`) only on a
  trusted network, and say so to the user.
- **Volume:** fused modes report one Issue per defective frame, up to
  about 10 per second. The receiver keeps the newest `--max-issues`
  (default 5000) in memory.
- **Summary:** give the user the alerts page URL `http://<HOST_IP>:8099/` and
  how to stop it (Ctrl-C in each terminal, or your tool's stop capability),
  and state clearly that results came from the dummy receiver, not a real
  OpenMES.

## Manual verification (smoke test)

1. Publish one known defect to the input topic, e.g. the fused-verdict
   JSON from [`FUSION.md`](FUSION.md) with `fused_decision: 1`. The log
   shows `Delivered event=<id> issue_id=<n>`.
2. The Issue exists in the OpenMES UI, or via `GET /api/v1/issues`, and its
   `description` is populated.
3. Replaying the exact same payload logs `Duplicate event ignored`, and no
   new Issue appears.
4. A non-defect (`fused_decision: 0`, `anomaly_status: 0`, or a good vision
   label) creates no Issue.
5. An invalid token file logs `Auth failure (401)` and the event's state is
   `blocked`.

Quote the log lines from steps 1, 3 and 5 in the final summary, never the
token.
