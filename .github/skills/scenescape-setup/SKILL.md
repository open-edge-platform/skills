---
name: scenescape-setup
description: >
  Use when you need to deploy a working Intel® SceneScape installation from scratch, outside the
  scenescape repo. Handles everything end-to-end: prompting for camera streams, generating
  docker-compose, DLStreamer pipeline config, tracker config, bringing up containers, verifying
  MQTT data flow, running 3D mapping, creating the scene and cameras via REST API, and confirming
  object tracking is live on the regulated topic.
argument-hint: "Optional: path to a directory where deployment files should be created (default: current directory)"
---

# SceneScape End-to-End Setup

Deploys a complete SceneScape installation from a clean directory. Only Docker and Python
required on the host — no SceneScape source checkout needed.

---

## Procedure Overview

Execute these steps in order. Each step links to a reference file with the exact content
to generate or commands to run.

| #   | Step                                                        | Reference                                                             |
| --- | ----------------------------------------------------------- | --------------------------------------------------------------------- |
| 1   | Gather inputs from user                                     | (below)                                                               |
| 2   | Create deployment directory                                 | (below)                                                               |
| 2a  | Download `dlstreamer-pipeline-server/` from scenescape repo | (below)                                                               |
| 3   | Generate `docker-compose.yml`                               | [docker-compose-template.md](./references/docker-compose-template.md) |
| 4   | Build and verify DLStreamer detection pipeline              | **dlstreamer-coding-agent skill** (below)                             |
| 5   | Adapt pipeline-server config from canonical template        | [pipeline-config.md](./references/pipeline-config.md)                 |
| 5a  | Verify pipeline-server integration                          | (below)                                                               |
| 6   | Generate tracker and ReID config                            | (below — two JSON blocks)                                             |
| 7   | Generate broker config, secrets, and bring up containers    | [generate_secrets.sh](./references/generate_secrets.sh), [openssl.cnf](./references/openssl.cnf) |
| 8   | Verify camera MQTT data flow                                | (below)                                                               |
| 9   | Check mapping service health                                | (below)                                                               |
| 10  | Capture frames and run 3D reconstruction                    | [reconstruction.md](./references/reconstruction.md)                   |
| 11  | Create scene and cameras via REST API                       | [scene-and-cameras.md](./references/scene-and-cameras.md)             |
| 12  | Verify object tracking                                      | [verify-tracking.md](./references/verify-tracking.md)                 |

Load a reference file only when you reach that step.

---

## Step 1 — Gather Inputs from the User

Prompt for:

| Field        | Description                       | Example                          |
| ------------ | --------------------------------- | -------------------------------- |
| `streams`    | RTSP URL per camera               | `rtsp://192.168.1.10:554/stream` |
| `camera_ids` | Unique ID per stream (same order) | `cam1`, `cam2`                   |
| `scene_name` | Human-readable scene name         | `Warehouse Floor A`              |
| `deploy_dir` | Directory for generated files     | `./scenescape-deploy`            |

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

## Step 2a — Download `dlstreamer-pipeline-server/` from the SceneScape Repo

The canonical pipeline configs, `sscape_adapter.py` user scripts, and mosquitto config all live in the
SceneScape repository. Download the `dlstreamer-pipeline-server/` directory into `<deploy_dir>/` using
a sparse checkout (no full clone needed):

```bash
cd <deploy_dir>
git clone --filter=blob:none --sparse \
  https://github.com/open-edge-platform/scenescape.git _scenescape-tmp
cd _scenescape-tmp
git sparse-checkout set dlstreamer-pipeline-server
cp -r dlstreamer-pipeline-server ../
cd .. && rm -rf _scenescape-tmp
```

Alternatively, if `git` sparse checkout is unavailable, use `curl` to download individual files:

```bash
mkdir -p dlstreamer-pipeline-server/user_scripts/gvapython/sscape
curl -fsSL https://raw.githubusercontent.com/open-edge-platform/scenescape/main/dlstreamer-pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py \
  -o dlstreamer-pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py
curl -fsSL https://raw.githubusercontent.com/open-edge-platform/scenescape/main/dlstreamer-pipeline-server/queuing-config.json \
  -o dlstreamer-pipeline-server/queuing-config.json
```

After this step, `<deploy_dir>/dlstreamer-pipeline-server/` contains:

- `queuing-config.json` — canonical pipeline config template (used in Step 5)
- `user_scripts/gvapython/sscape/sscape_adapter.py` — SceneScape MQTT bridge (mounted into video-analytics)
- `mosquitto/mosquitto-secure.conf` — broker config (mounted into broker service)
- `model-proc-files/` — model processing descriptors

---

## Step 4 — Build and Verify DLStreamer Detection Pipeline

**Invoke the `dlstreamer-coding-agent` skill** to build and validate a working detection pipeline
before it is embedded into the pipeline-server config. This ensures the model, pipeline string,
and container connectivity are all confirmed working independently.

### What to pass to the dlstreamer-coding-agent

Provide the following as the argument:

> Build a GStreamer command-line object detection pipeline using YOLO11n on CPU.
> Input: `<rtsp_url>` (first camera stream). Output: JSON metadata only (no video file).
> Run inside Docker on the `<docker_network>` network with `no_proxy` set to include the
> mediaserver hostname. Confirm detections appear in the output JSON before proceeding.

Use the first camera stream for validation. The same model and pipeline elements will be
reused for all cameras in Step 5.

### What to capture from the dlstreamer-coding-agent output

Record the following for use in Step 5:

| Item                                     | Where to find it                     |
| ---------------------------------------- | ------------------------------------ |
| Verified model path (inside container)   | Reported by the skill after export   |
| Working `gst-launch-1.0` pipeline string | Final validated command              |
| Docker network name                      | Used in the `docker run` command     |
| Any `no_proxy` / env var requirements    | Noted by the skill during validation |

**Do not proceed to Step 5 until the dlstreamer-coding-agent reports detections are live.**

---

## Step 5 — Wrap Verified Pipeline into Pipeline-Server Config

Read [pipeline-config.md](./references/pipeline-config.md) now.

Take the verified `gst-launch-1.0` pipeline elements from Step 4 and adapt them to the
pipeline-server format:

- Replace `gst-launch-1.0` syntax with the inline `"pipeline"` string format.
- Replace the standalone `fakesink` / `filesink` with the SceneScape adapter elements
  (`gvapython sscape_adapter`, `gvametapublish`, `appsink`) as shown in the reference template.
- Replace the standalone model path with the container-internal path
  `/home/pipeline-server/models/...` (or the path exported in Step 4 if custom).
- Replicate the entry for every camera using its `<camera_id>` and `<rtsp_url>`.

---

## Step 5a — Verify Pipeline-Server Integration

Start only the `video-analytics` and `mediaserver` services (not the full stack):

```bash
docker compose up -d mediaserver video-analytics
docker compose logs -f video-analytics 2>&1 | head -80
```

Confirm in the logs:

- No RTSP connection errors for any camera stream
- `Pipeline started` or equivalent log line per camera
- No model-load failures

If the pipeline-server fails to start a pipeline, check:

1. Model path is correct inside the container — `docker compose exec video-analytics ls <model_path>`
2. RTSP URL is reachable — `docker compose exec video-analytics curl <rtsp_url>`
3. `no_proxy` / proxy env vars are set in the compose service environment (add under `environment:` in `docker-compose.yml` if needed)

**Do not proceed to Step 6 until all camera pipelines are confirmed running in the logs.**

---

## Step 6 — Tracker and ReID Config

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

Write `<deploy_dir>/reid-config.json`:

```json
{
  "similarity_metric": "COSINE",
  "stale_feature_timeout_secs": 5.0,
  "stale_feature_check_interval_secs": 1.0,
  "feature_accumulation_threshold": 12,
  "minimum_bbox_area": 5000,
  "feature_slice_size": 10,
  "similarity_threshold": 0.5
}
```

---

## Step 7 — Generate Secrets and Bring Up Containers

Read and execute [generate_secrets.sh](./references/generate_secrets.sh) using the
[openssl.cnf](./references/openssl.cnf) template. Then create `.env` and start all services:

```bash
cd <deploy_dir>
bash generate_secrets.sh

# Build .env — read DATABASE_PASSWORD from generated secrets.py
SECRETSDIR=$(pwd)/secrets
DATABASE_PASSWORD=$(python3 -c "
import re
txt = open('secrets/django/secrets.py').read()
print(re.search(r\"DATABASE_PASSWORD='([^']+)'\", txt).group(1))
")
SUPASS=$(cat secrets/supass)
cat > .env <<EOF
SECRETSDIR=${SECRETSDIR}
DATABASE_PASSWORD=${DATABASE_PASSWORD}
SUPASS=${SUPASS}
http_proxy=${http_proxy}
https_proxy=${https_proxy}
no_proxy=${no_proxy}
EOF

docker compose up -d
```

Wait for all containers to be healthy:

```bash
docker compose ps
```

Expected healthy: `broker`, `ntpserv`, `pgserver`, `web`, `scene`.

### Download AI models

The `model_downloader` service (`scenescape-model-installer:latest`) exits immediately without
downloading models by itself. Run the download manually using the openvino omz_downloader:

```bash
docker run --rm --user root \
  -e http_proxy="${http_proxy}" \
  -e https_proxy="${https_proxy}" \
  -v <project_name>_vol-models:/models \
  scenescape-model-installer:latest bash -c "
pip3 install --break-system-packages openvino-dev 2>&1 | grep Successfully
/usr/local/bin/omz_downloader --name person-detection-retail-0013 -o /models/
chmod -R a+rX /models/
"
```

Replace `<project_name>` with the Docker Compose project name (default: `scenescape` from the
`name:` field in `docker-compose.yml`, so the volume is `scenescape_vol-models`).

After models download, restart `video-analytics` so it picks them up:

```bash
docker compose restart video-analytics
```

---

## Step 8 — Verify Camera MQTT Data Flow

After all containers are healthy, wait up to **2 minutes** for video-analytics to initialise its
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

1. `docker compose logs video-analytics --tail 50` — look for RTSP connection errors
2. Verify RTSP URLs are reachable: `docker compose exec video-analytics curl <rtsp_url>`
3. `docker compose logs broker --tail 20` — check broker is accepting connections

---

## Step 9 — Check Mapping Service Health

Poll `GET https://localhost:8444/health` every 10 s for up to 3 minutes.

```bash
curl -sk https://localhost:8444/health
```

Must return `"status": "healthy"` or `"model_loaded": true`. The model installer downloads
`person-detection-retail-0013` on first run — allow extra time on a fresh deployment.
