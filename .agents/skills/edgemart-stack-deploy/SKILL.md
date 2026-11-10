---
name: edgemart-stack-deploy
description: >
  Deploy, configure, rebuild and troubleshoot the EdgeMart (qsr-store-pos-agent)
  Docker Compose stack: Angular frontend, Express backend, PostgreSQL (grocery
  and cafe databases), authenticated Mosquitto MQTT, and the store-activity,
  table-occupancy and footfall services. USE FOR: first-time `docker compose up`,
  filling in .env secrets, compose startup refusing to run, rebuilding after code
  changes, port conflicts, unhealthy containers, corporate proxy builds, running
  the backend natively against local Postgres. DO NOT USE FOR: wiring the Hermes
  agent to MCP servers (use edgemart-agent-mcp), calling or seeding the event
  services (use edgemart-store-services), or generic Docker questions unrelated
  to this repo.
license: Apache-2.0
compatibility: Requires Docker Engine 24+ with Compose v2. Native mode needs Node.js 18+ and PostgreSQL 14+.
metadata:
  author: Intel Open Edge Platform Team
  tags: "docker-compose pos mqtt postgres"
---

# EdgeMart Stack Deploy

EdgeMart is a demo point-of-sale system with a grocery and a cafe experience. The
Compose file starts everything; the main failure modes are missing secrets, stale
images and wrong hostnames between containers and the host.

## When to Use

- The user wants to start, stop, rebuild or debug the stack.
- `docker compose` fails with "Set DB_PASSWORD in .env" or similar.
- A container is unhealthy, or the Agent Chat tab shows disconnected.

## Instructions

1. Copy the template and set the four required values. Compose has no defaults for
   them and refuses to start while any is empty.

   ```bash
   cp .env.example .env
   # DB_PASSWORD, HERMES_API_KEY, MQTT_USERNAME, MQTT_PASSWORD
   ```

   `HERMES_API_KEY` must equal the Hermes gateway's `API_SERVER_KEY`. The MQTT
   account is created by the broker container at start-up from `MQTT_USERNAME` and
   `MQTT_PASSWORD`; anonymous access is disabled.

2. Start the stack. Add `--build` whenever backend or frontend code changed.

   ```bash
   docker compose up --build
   ```

3. Check health. The UI is on `http://localhost` (port 80). Container health checks use
   `/api/health` (backend, 3000), `/store-activity/health` (3100),
   `/table-occupancy/health` (3200), `/footfall/health` (3300) and `/health` on the
   MCP sidecars (3101, 3201, 3301).

4. Rebuild after code changes with `docker compose up --build <service>`. The three
   event services and their MCP sidecars share one image per service
   (`${IMAGE_REGISTRY:-qsr-store-pos-agent}/<service>:${IMAGE_TAG:-latest}`), so
   rebuild the service and its sidecar together. The sidecar service names are
   `store-activity-service-mcp`, `table-occupancy-service-mcp` and
   `footfall-service-mcp`; Compose rejects any other name. For example:

   ```bash
   docker compose up -d --build table-occupancy-service table-occupancy-service-mcp
   ```

   `--force-recreate` alone reuses the existing image and silently keeps running old
   code, because source is baked in by `COPY` at build time.

## Things that are easy to get wrong

- **Hermes runs on the host, not in Compose.** The backend reaches it through
  `HERMES_GATEWAY_URL` (default `http://host.docker.internal:3001`). Hermes must
  listen on `0.0.0.0`, not `127.0.0.1`, or the container cannot connect.
- **Containers are hardened**: read-only root filesystem, all capabilities dropped,
  `no-new-privileges`, only `/tmp` writable. Do not "fix" a problem by writing files
  inside a container; change code and rebuild.
- **Postgres is published on loopback only** (`127.0.0.1:5432`). Other containers use
  the host name `postgres`.
- **Two databases**: `pos_grocery` and `pos_cafe`, created by `database/init-db.sh`
  from `database/<experience>/schema.sql`. Schema changes do not apply to an existing
  volume; recreate it with `docker compose down -v` (this deletes data, so confirm
  with the user first).
- **Behind a proxy**, the event-service builds forward `HTTP_PROXY`, `HTTPS_PROXY` and
  `NO_PROXY` as build args. Export them before `docker compose build`.
- **Experience selection**: every backend request carries `X-Experience: grocery|cafe`
  (or `?experience=`). Anything else returns 400. Default is `grocery`.
- Optional hardening keys (`SIM_API_KEY`, `TABLE_SIM_API_KEY`, `FOOTFALL_SIM_API_KEY`,
  `MCP_API_KEY`) are open when empty. Set `IMAGE_REGISTRY` lowercase with no trailing
  slash.

## Native (no Docker) backend

Requires Node.js 18+ and PostgreSQL 14+. Create and initialize both databases first;
the schema files are not applied automatically outside Compose:

```bash
createdb -U postgres pos_grocery
psql -U postgres -d pos_grocery -f database/grocery/schema.sql
createdb -U postgres pos_cafe
psql -U postgres -d pos_cafe -f database/cafe/schema.sql
```

Then configure the backend. Set `DB_PASSWORD` in `backend/.env` to the real Postgres
password (the template value is a placeholder), and run the backend and frontend in
two terminals because `npm run dev` does not return:

```bash
# terminal 1, from the repository root
cd backend && npm install && cp .env.example .env   # edit .env, then:
npm run dev

# terminal 2, from the repository root
cd frontend && npm install && ng serve   # http://localhost:4200
```

The backend's CORS allows only `http://localhost:4200`. Mosquitto must have a user
unless the broker is local and anonymous; set `MQTT_BROKER_URL`, `MQTT_USERNAME`,
`MQTT_PASSWORD` in `backend/.env`.

## Common Issues

| Symptom | Cause and fix |
| --- | --- |
| `Set MQTT_USERNAME in .env` on `up` | Required secret empty. Fill all four values. |
| Backend healthy, chat disconnected | Gateway not running, wrong `HERMES_API_KEY`, or bound to 127.0.0.1. Run `curl http://localhost:3001/health`. |
| Code change has no effect | Image not rebuilt. Use `docker compose up --build <service>`. |
| Backend waits forever on start | Postgres unhealthy; check `docker compose logs postgres`. |
| Table events never arrive | MQTT credentials differ between broker and clients, or the broker is down. Without a broker the backend runs offline and the cafe simulator posts events over HTTP instead. |

## References

- Full setup, ports and env reference:
  https://github.com/intel-retail/qsr-store-pos-agent/blob/main/README.md
- Event service images and registry publishing:
  https://github.com/intel-retail/qsr-store-pos-agent/blob/main/docs/STORE-SERVICES.md
