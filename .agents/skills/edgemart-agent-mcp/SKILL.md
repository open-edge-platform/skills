---
name: edgemart-agent-mcp
description: >
  Connect an LLM agent (Hermes Gateway or any MCP client) to the EdgeMart POS and
  store MCP servers and use their tools correctly. USE FOR: registering the pos-tools,
  table-status, store-activity, table-occupancy and footfall MCP servers over stdio or
  streamable HTTP, choosing the right database (grocery vs cafe), setting up the Hermes
  API server for the Agent Chat tab, picking the right tool for a sales, table or
  footfall question, and debugging tool calls that fail. DO NOT USE FOR: starting the
  Docker stack itself (use edgemart-stack-deploy), generating or ingesting store events
  (use edgemart-store-services), or writing new MCP servers for unrelated projects.
license: Apache-2.0
compatibility: Requires Node.js 18+ for stdio servers, or the Compose MCP sidecars for HTTP. Hermes Agent v0.14+ with a model that has at least 64K context.
metadata:
  author: Intel Open Edge Platform Team
  tags: "mcp hermes agent pos"
---

# EdgeMart Agent and MCP

Five MCP servers expose the store to an agent. Two are the original POS servers and
three belong to the event services. The Agent Chat tab streams from Hermes through
`POST /api/chat` on the backend.

## When to Use

- Add or fix an `mcp_servers` entry for Hermes or Claude Desktop.
- An agent answers sales or table questions wrongly, or a tool errors.
- The user needs the Hermes API server enabled for the chat tab.

## The servers

| Server | Entry point | Data source | Tools |
| --- | --- | --- | --- |
| pos-tools | `backend/src/mcp-server.js` | Postgres (`MCP_DB_NAME`) | `list_categories`, `search_products`, `get_product_details`, `get_sales_summary`, `get_sales_summary_by_date`, `get_sales_by_date`, `get_product_sales`, `list_customers`, `get_customer_purchases`, `get_top_customers`, `run_query`, `get_schema` |
| table-status | `backend/src/mcp-table-status.js` | MQTT live state | `get_all_tables`, `get_dirty_tables`, `get_occupied_tables`, `get_clean_tables`, `get_table_history`, `get_table_stats`, `mark_table_cleared`, `mark_table_occupied`, `get_service_status` |
| store-activity | `backend/src/store-activity-service/mcp-store-activity-server.js` | durable event log | `describe_service`, `list_event_types`, `query_history`, `compare_to_baseline`, `tail_events`, `get_current_snapshot`, `mark_table_cleared`, `inject_event` |
| table-occupancy | `backend/src/table-occupancy-service/mcp-table-occupancy-server.js` | durable event log | `describe_service`, `list_event_types`, `get_utilization`, `get_dirty_duration_stats`, `get_table_history`, `mark_table_cleared`, `mark_table_occupied` |
| footfall | `backend/src/footfall-service/mcp-footfall-server.js` | durable event log | `describe_service`, `list_event_types`, `get_total_footfall`, `get_busy_time_patterns` (read-only) |

Call `describe_service` and `list_event_types` first on the three service servers; they
return the live contract, so do not guess event names.

## Instructions

1. **Choose a transport.**
   - stdio: the agent spawns `node <server>`. Use absolute paths, and pass the env block
     from `hermes-config.json` (copy the relevant entries into `~/.hermes/config.yaml`).
   - Streamable HTTP: with the Compose stack running, the sidecars serve `POST /mcp` on
     3101 (store-activity), 3201 (table-occupancy) and 3301 (footfall). Set
     `MCP_API_KEY` to require `X-Api-Key` or `Authorization: Bearer`. Rate limit is
     120 requests per minute per IP.
   - Compose service names are `store-activity-service-mcp`,
     `table-occupancy-service-mcp` and `footfall-service-mcp`. Each has `GET /health`
     on its port. Register them by URL, for example `http://localhost:3201/mcp`, or
     `http://table-occupancy-service-mcp:3201/mcp` from another container.
   - The same server files run over HTTP natively with `MCP_TRANSPORT=http` and
     `MCP_HTTP_PORT`. `MCP_CORS_ORIGIN` limits browser origins.
   - The pos-tools and table-status servers are stdio only.

   The stdio env names differ per service server, matching `hermes-config.json`: the
   database variable is `SIM_DB_NAME` (store-activity), `TABLE_SIM_DB_NAME`
   (table-occupancy) or `FOOTFALL_SIM_DB_NAME` (footfall). Set all of them to `pos_cafe`
   for the cafe, and also pass `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `MQTT_BROKER_URL`,
   `MQTT_USERNAME` and `MQTT_PASSWORD`.

2. **Pick the database for pos-tools.** `MCP_DB_NAME` defaults to the grocery database.
   Set `MCP_DB_NAME=pos_cafe` for the cafe, otherwise an agent asked about lattes will
   query grocery data and report nothing.

3. **Enable the Hermes API server** in `~/.hermes/.env`, then `hermes gateway run`:

   ```env
   API_SERVER_ENABLED=true
   API_SERVER_PORT=3001
   API_SERVER_HOST=0.0.0.0
   API_SERVER_KEY=<same value as HERMES_API_KEY>
   ```

   Verify with `curl http://localhost:3001/health` and `hermes doctor`.

4. **Backend side:** set `HERMES_GATEWAY_URL` and `HERMES_API_KEY` (see
   edgemart-stack-deploy). The Config page can also start and stop the pos-tools and
   table-status servers through `/api/mcp/*`.

## Tool-choice rules

- Revenue, products, customers: pos-tools. Use `run_query` only for read-only ad hoc
  SQL when no dedicated tool fits; call `get_schema` first.
- "Which tables are dirty right now": the right tool depends on where the events
  went. table-status holds live state built from the MQTT topics
  `cafe/vision/events`, `cafe/pos/events` and `cafe/staff/events`. store-activity's
  `get_current_snapshot` and table-occupancy read their own durable event logs. They do
  not share state, so an event ingested into one need not show in another, and
  table-status then reports the default clean state. Ask which source the events
  were sent to, or query the one that matches the user's pipeline.
- Utilization and how long tables stay dirty over a date range: table-occupancy.
- Busy hours and visitor counts by zone: footfall.
- Parameter names differ by server. table-status takes `table_id`; the table-occupancy
  tools and store-activity's `mark_table_cleared` take `table_ref`. store-activity's
  `inject_event` takes `ref` instead (plus `event_type`); pass the table id there or
  the event is stored with `ref: null`. Table ids look like `table-4`.
- Dates are `YYYY-MM-DD`.
- Action tools (`mark_table_cleared`, `mark_table_occupied`, `inject_event`) change
  state. Confirm intent before calling them on behalf of a user.

## Common Issues

| Symptom | Fix |
| --- | --- |
| Tools list is empty or the server exits | Run the entry point by hand; stderr shows DB or MQTT connection errors. |
| 401 from an HTTP sidecar | `MCP_API_KEY` is set; send it as `X-Api-Key` or a bearer token. |
| Model never calls tools | Model lacks native tool use or has under 64K context. Use a larger or higher-quantization model. |
| Agent reports no sales | Wrong `MCP_DB_NAME`, or an empty database. |

## References

- Tool tables and Hermes setup:
  https://github.com/intel-retail/qsr-store-pos-agent/blob/main/README.md
- Reference MCP config:
  https://github.com/intel-retail/qsr-store-pos-agent/blob/main/hermes-config.json
- Service HTTP, SSE and MCP surfaces:
  https://github.com/intel-retail/qsr-store-pos-agent/blob/main/docs/STORE-SERVICES.md
