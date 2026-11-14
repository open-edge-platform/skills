---
name: edgemart-store-services
description: >
  Run, configure and integrate the EdgeMart store event services: store-activity
  (port 3100), table-occupancy (3200) and footfall (3300). USE FOR: switching a service
  between SOURCE=sim and SOURCE=real, ingesting events from a real camera or vision
  pipeline, seeding history, replaying a recorded day, subscribing to SSE or MQTT
  event streams, calling the plain-HTTP mirrors of the MCP tools, API keys and CORS,
  and benchmark mode. DO NOT USE FOR: general Docker troubleshooting (use
  edgemart-stack-deploy), registering MCP servers with an agent (use
  edgemart-agent-mcp), or the browser 3D simulator.
license: Apache-2.0
compatibility: Requires Node.js 18+, PostgreSQL and an authenticated MQTT broker, or the Compose stack.
metadata:
  author: Intel Open Edge Platform Team
  tags: "events mqtt sse simulation"
---

# EdgeMart Store Services

Three independent headless services share one pattern from
`backend/src/service-common/`: a durable Postgres event log, a hub that fans events out
over SSE and MQTT, a producer, and an MCP server. An agent sees the same contract
whether events are simulated or real.

| Service | Port | Base path | Events | Actions |
| --- | --- | --- | --- | --- |
| store-activity | 3100 | `/store-activity` | customer, order, table, queue | `mark-table-cleared`, `inject-event` |
| table-occupancy | 3200 | `/table-occupancy` | `table.occupied`, `table.dirty`, `table.cleared` | `mark-table-cleared`, `mark-table-occupied` |
| footfall | 3300 | `/footfall` | `footfall.count`, `zone.density_changed` | none |

Each service has an MCP sidecar in Compose (`store-activity-service-mcp` on 3101,
`table-occupancy-service-mcp` on 3201, `footfall-service-mcp` on 3301). Its `SOURCE`
follows the service's `*_SIM_SOURCE` variable. Tools and registration are in
edgemart-agent-mcp.

## When to Use

- The user wants live or historical events, or wants to plug in a real pipeline.
- The user asks what an env var such as `SIM_SPEED` or `SOURCE` does.
- Event history is empty and needs seeding.

## Instructions

1. **Start a service.** Compose: `docker compose up -d store-activity-service
   table-occupancy-service footfall-service`. Native, from `backend/`. The service runs
   in the foreground, so seed history first, or run the seed in a second terminal:

   ```bash
   node src/table-occupancy-service/seed-history.js --days=14
   node src/table-occupancy-service/index.js
   ```

   The same layout applies to the other two services.

2. **Pick the source per service.** `SOURCE` is `sim` (default) or `real`, and each
   service is independent. In Compose use `SIM_SOURCE` (store-activity),
   `TABLE_SIM_SOURCE` and `FOOTFALL_SIM_SOURCE`. An invalid value stops the service at
   start-up; this is deliberate so a typo like `Real` cannot silently disable ingest.

3. **Ingest real events.** Set `SOURCE=real`, then `POST <base>/ingest` with an
   envelope that matches the service's schema. Call the MCP `describe_service` tool to
   get the exact shape. The route returns 409 when the service is in `sim` mode and
   400 for an invalid envelope. A repeated `event_id` returns `duplicate: true` and is
   not stored twice.

4. **Consume events.**
   - SSE: `curl -N http://localhost:3300/footfall/events/stream`. On reconnect send
     `Last-Event-ID` with the last `event_id` and missed events replay from the log.
   - MQTT topics: `sim/<experience>/events/<event_type>`,
     `table-sim/<experience>/events/<event_type>`,
     `footfall-sim/<experience>/events/<event_type>`. The `sim` prefixes are historical
     and kept for compatibility. Subscribe with the broker username and password.

5. **Query without MCP.** Every read and act tool has an HTTP mirror, for example:

   ```bash
   curl "http://localhost:3200/table-occupancy/utilization?table_ref=table-4&start_date=2026-05-01&end_date=2026-05-20"
   curl -X POST http://localhost:3200/table-occupancy/actions/mark-table-cleared \
     -H 'Content-Type: application/json' -H "X-Api-Key: $TABLE_SIM_API_KEY" \
     -d '{"table_ref": "table-4"}'
   ```

## Environment reference

| Var | Default | Meaning |
| --- | --- | --- |
| `SOURCE` | `sim` | `sim` or `real`. |
| `SIM_MODE` | `live` | `live`, or `replay` of a recorded day (sim only). |
| `SIM_REPLAY_DATE` | today UTC | Day to replay, `YYYY-MM-DD`. |
| `SIM_SEED` | `edgemart-default-seed` | Same seed and day give identical events. |
| `SIM_SPEED` | `10` | 10 means ten simulated hours per real hour (60 = one simulated hour per real minute). |
| `SIM_BENCHMARK` | `0` | `1` turns off SSE and MQTT fanout; the log still records events. |
| `SIM_EXPERIENCE` | `cafe` | `cafe` or `grocery`. |
| `CAFE_TABLE_COUNT` | `15` | Clamped to 1 to 200. |
| `SIM_API_KEY`, `TABLE_SIM_API_KEY`, `FOOTFALL_SIM_API_KEY` | unset | When set, write routes need `X-Api-Key`. |
| `SIM_CORS_ORIGIN` and its `TABLE_SIM_` and `FOOTFALL_SIM_` variants | `http://localhost:4200` | Allowed origins. `*` is a literal string and matches nothing. |

Port and database variables are `SIM_PORT` / `SIM_DB_NAME`, `TABLE_SIM_PORT` /
`TABLE_SIM_DB_NAME`, `FOOTFALL_SIM_PORT` / `FOOTFALL_SIM_DB_NAME`. All three logs live
in the `pos_cafe` database in separate tables.

## Common Issues

| Symptom | Fix |
| --- | --- |
| `/ingest` returns 409 | Service is `SOURCE=sim`. Switch to `real`. |
| `/health` returns 503 | Postgres unreachable. Check the `db` and `mqtt` fields in the body. |
| 401 on a POST | An API key is set. Send `X-Api-Key`. |
| No MQTT messages while benchmarking | `SIM_BENCHMARK=1` disables fanout by design. |
| Empty history queries | Run `seed-history.js --days=N`, or wait for the live producer. |
| Malformed query parameter returns 400 | Dates must be `YYYY-MM-DD`; repeated parameters are rejected. |

## References

- Quick start and integration surfaces:
  https://github.com/intel-retail/qsr-store-pos-agent/blob/main/docs/STORE-SERVICES.md
- Per-service detail:
  https://github.com/intel-retail/qsr-store-pos-agent/blob/main/backend/src/store-activity-service/STORE-ACTIVITY-SERVICE.md
  https://github.com/intel-retail/qsr-store-pos-agent/blob/main/backend/src/table-occupancy-service/TABLE-OCCUPANCY-SERVICE.md
  https://github.com/intel-retail/qsr-store-pos-agent/blob/main/backend/src/footfall-service/FOOTFALL-SERVICE.md
