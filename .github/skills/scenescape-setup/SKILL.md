---
name: scenescape-setup
description: >
  Use when you need to deploy a working Intel® SceneScape installation from scratch, outside the
  scenescape repo. Handles everything end-to-end: prompting for camera streams, generating
  docker-compose, DLStreamer pipeline config, tracker config, bringing up containers, verifying
  MQTT data flow, running 3D mapping, creating the scene and cameras via REST API, and confirming
  object tracking is live on the regulated topic.
argument-hint: 'Optional: path to a directory where deployment files should be created (default: current directory)'
---

# SceneScape End-to-End Setup

Deploys a complete SceneScape installation from a clean directory. Only Docker and Python
required on the host — no SceneScape source checkout needed.

---

## Procedure Overview

Execute these steps in order. Each step links to a reference file with the exact content
to generate or commands to run.

| # | Step | Reference |
|---|---|---|
| 1 | Gather inputs from user | (below) |
| 2 | Create deployment directory | (below) |
| 3 | Generate `docker-compose.yml` | [docker-compose-template.md](./references/docker-compose-template.md) |
| 4 | Generate DLStreamer pipeline config | [pipeline-config.md](./references/pipeline-config.md) |
| 5 | Generate tracker config | (below — one JSON block) |
| 6 | Generate secrets and bring up containers | [generate_secrets.sh](./references/generate_secrets.sh) |
| 7 | Verify camera MQTT data flow | (below) |
| 8 | Check mapping service health | (below) |
| 9 | Capture frames and run 3D reconstruction | [reconstruction.md](./references/reconstruction.md) |
| 10 | Create scene and cameras via REST API | [scene-and-cameras.md](./references/scene-and-cameras.md) |
| 11 | Verify object tracking | [verify-tracking.md](./references/verify-tracking.md) |

Load a reference file only when you reach that step.

---

## Step 1 — Gather Inputs from the User

Prompt for:

| Field | Description | Example |
|---|---|---|
| `streams` | RTSP URL per camera | `rtsp://192.168.1.10:554/stream` |
| `camera_ids` | Unique ID per stream (same order) | `cam1`, `cam2` |
| `scene_name` | Human-readable scene name | `Warehouse Floor A` |
| `deploy_dir` | Directory for generated files | `./scenescape-deploy` |

Validate: `len(streams) == len(camera_ids)`, IDs are unique and contain no `/`, at least 1 camera.

The superuser password is **generated automatically** in Step 6 and written to
`<deploy_dir>/secrets/supass`.

---

## Step 2 — Create Deployment Directory

```bash
mkdir -p <deploy_dir>
```

All generated files go under `<deploy_dir>/`.

---

## Step 5 — Tracker Config

Write `<deploy_dir>/tracker-config.json`:

```json
{
  "max_unreliable_time_s": 1.0,
  "non_measurement_time_dynamic_s": 0.8,
  "non_measurement_time_static_s": 1.6,
  "time_chunking_enabled": true,
  "time_chunking_rate_fps": 30,
  "suspended_track_timeout_secs": 60.0
}
```

---

## Step 7 — Verify Camera MQTT Data Flow

After all containers are healthy, wait up to **2 minutes** for DLStreamer to initialise its
pipelines. Subscribe to `scenescape/data/camera/+` and confirm a message arrives for every
camera ID the user provided.

Read broker credentials from `<deploy_dir>/secrets/browser.auth` (`user` / `password` fields).

```bash
# Read credentials from the auth file
BROKER_USER=$(python3 -c "import json; d=json.load(open('<deploy_dir>/secrets/browser.auth')); print(d['user'])")
BROKER_PASS=$(python3 -c "import json; d=json.load(open('<deploy_dir>/secrets/browser.auth')); print(d['password'])")

docker compose exec broker mosquitto_sub \
  --cafile /mosquitto/secrets/certs/scenescape-ca.pem \
  -u "$BROKER_USER" -P "$BROKER_PASS" \
  -t 'scenescape/data/camera/+' \
  -C <num_cameras> --timeout 120
```

If timeout is reached without all cameras reporting, warn the user:
1. `docker compose logs dlstreamer --tail 50` — look for RTSP connection errors
2. Verify RTSP URLs are reachable: `docker compose exec dlstreamer curl <rtsp_url>`
3. `docker compose logs broker --tail 20` — check broker is accepting connections

---

## Step 8 — Check Mapping Service Health

Poll `GET https://localhost:8444/health` every 10 s for up to 3 minutes.

```bash
curl -sk https://localhost:8444/health
```

Must return `"status": "healthy"` or `"model_loaded": true`. The model installer downloads
`person-detection-retail-0013` on first run — allow extra time on a fresh deployment.
