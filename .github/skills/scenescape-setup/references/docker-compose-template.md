# docker-compose.yml Template

Write this file to `<deploy_dir>/docker-compose.yml`. Replace `${SECRETSDIR}` with the
absolute path to `<deploy_dir>/secrets` (or pass it as an env var).

```yaml
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

name: scenescape

networks:
  scenescape:

secrets:
  root-cert:
    file: ${SECRETSDIR}/certs/scenescape-ca.pem
  web-cert:
    file: ${SECRETSDIR}/certs/scenescape-web.crt
  web-key:
    file: ${SECRETSDIR}/certs/scenescape-web.key
  vdms-client-cert:
    file: ${SECRETSDIR}/certs/scenescape-vdms-c.crt
  vdms-client-key:
    file: ${SECRETSDIR}/certs/scenescape-vdms-c.key
  vdms-server-cert:
    file: ${SECRETSDIR}/certs/scenescape-vdms-s.crt
  vdms-server-key:
    file: ${SECRETSDIR}/certs/scenescape-vdms-s.key
  django:
    file: ${SECRETSDIR}/django/secrets.py
  controller.auth:
    file: ${SECRETSDIR}/controller.auth
  browser.auth:
    file: ${SECRETSDIR}/browser.auth
  calibration.auth:
    file: ${SECRETSDIR}/calibration.auth
  autocalibration-cert:
    file: ${SECRETSDIR}/certs/scenescape-autocalibration.crt
  autocalibration-key:
    file: ${SECRETSDIR}/certs/scenescape-autocalibration.key
  mapping-cert:
    file: ${SECRETSDIR}/certs/scenescape-mapping.crt
  mapping-key:
    file: ${SECRETSDIR}/certs/scenescape-mapping.key

services:
  ntpserv:
    image: dockurr/chrony:4.8
    networks:
      scenescape:
    restart: unless-stopped
    environment:
      - NTP_DIRECTIVES=local stratum 10
    healthcheck:
      test:
        - CMD
        - sh
        - -c
        - "chronyc tracking | grep -E 'Stratum[[:space:]]+:[[:space:]]+([1-9]|1[0-6])[[:space:]]*$' || exit 1"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  broker:
    image: eclipse-mosquitto:2.0.22
    configs:
      - source: mosquitto-secure
        target: /mosquitto/config/mosquitto.conf
    volumes:
      - ${SECRETSDIR}:/mosquitto/secrets
    networks:
      scenescape:
        aliases:
          - broker.scenescape.intel.com
    restart: always

  pgserver:
    image: postgres:17.6
    environment:
      POSTGRES_USER: scenescape
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
      POSTGRES_DB: scenescape
    networks:
      - scenescape
    volumes:
      - vol-db:/var/lib/postgresql/data
    restart: always
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB -h localhost -p 5432",
        ]
      interval: 2s
      timeout: 3s
      retries: 30
      start_period: 5s

  web:
    image: scenescape-manager:latest
    init: true
    networks:
      scenescape:
        aliases:
          - web.scenescape.intel.com
    depends_on:
      pgserver:
        condition: service_healthy
      broker:
        condition: service_started
    ports:
      - "443:443"
    command: >
      webserver
      --dbtype postgres
      --broker broker.scenescape.intel.com
      --brokerauth /run/secrets/browser.auth
      --brokerrootcert /run/secrets/certs/scenescape-ca.pem
    healthcheck:
      test: "curl --insecure -X GET https://web.scenescape.intel.com:443/api/v1/database-ready | grep 'true'"
      interval: 10s
      timeout: 120s
      retries: 10
      start_period: 10s
    environment:
      SUPASS: ${SUPASS}
      DBHOST: pgserver
      DBPORT: 5432
      DATABASE_PASSWORD: ${DATABASE_PASSWORD}
      BROKER: broker.scenescape.intel.com
      BROKERAUTH: /run/secrets/browser.auth
      BROKERROOTCERT: /run/secrets/certs/scenescape-ca.pem
    volumes:
      - vol-media:/workspace/media
      - vol-models:/home/scenescape/SceneScape/models
      - ./secrets/django/secrets.py:/home/scenescape/SceneScape/manager/secrets.py:ro
    secrets:
      - source: root-cert
        target: certs/scenescape-ca.pem
      - source: web-cert
        target: certs/scenescape-web.crt
      - source: web-key
        target: certs/scenescape-web.key
      - django
      - browser.auth
      - calibration.auth
      - source: vdms-client-cert
        target: certs/scenescape-vdms-c.crt
      - source: vdms-client-key
        target: certs/scenescape-vdms-c.key
    restart: always

  scene:
    image: scenescape-controller:latest
    init: true
    networks:
      scenescape:
    depends_on:
      web:
        condition: service_healthy
      broker:
        condition: service_started
      ntpserv:
        condition: service_started
    command: >
      --restauth /run/secrets/controller.auth
      --brokerauth /run/secrets/controller.auth
      --broker broker.scenescape.intel.com
      --ntp ntpserv
    configs:
      - source: tracker-config
        target: /home/scenescape/SceneScape/tracker-config.json
      - source: reid-config
        target: /home/scenescape/SceneScape/reid-config.json
    volumes:
      - vol-media:/home/scenescape/SceneScape/media
      - ./secrets/django/secrets.py:/home/scenescape/SceneScape/manager/secrets.py:ro
    secrets:
      - source: root-cert
        target: certs/scenescape-ca.pem
      - django
      - controller.auth
      - source: vdms-client-key
        target: certs/scenescape-vdms-c.key
      - source: vdms-client-cert
        target: certs/scenescape-vdms-c.crt
    restart: always

  video-analytics:
    image: intel/dlstreamer-pipeline-server:latest
    networks:
      scenescape:
    depends_on:
      broker:
        condition: service_started
    environment:
      MQTT_HOST: broker.scenescape.intel.com
      no_proxy: broker.scenescape.intel.com
    volumes:
      - ./pipeline-config.json:/home/pipeline-server/config.json:ro
      - vol-models:/home/pipeline-server/models:ro
    restart: unless-stopped

  model_downloader:
    image: scenescape-model-installer:latest
    volumes:
      - vol-models:/home/scenescape/SceneScape/models
    restart: "no"

  mapping:
    image: scenescape-mapping:latest
    profiles:
      - mapping
    networks:
      scenescape:
        aliases:
          - mapping.scenescape.intel.com
    ports:
      - "8444:8444"
    volumes:
      - vol-mapping-model-weights:/workspace/model_weights
      - vol-mapping-torch-cache:/workspace/.cache/torch
      - vol-mapping-hf-cache:/workspace/.cache/huggingface
    secrets:
      - source: mapping-cert
        target: certs/scenescape-mapping.crt
      - source: mapping-key
        target: certs/scenescape-mapping.key
      - source: root-cert
        target: certs/scenescape-ca.pem
    healthcheck:
      test: ["CMD", "curl", "-sk", "https://localhost:8444/health"]
      interval: 15s
      timeout: 10s
      retries: 20
      start_period: 60s
    restart: unless-stopped

configs:
  mosquitto-secure:
    file: ./mosquitto.conf
  tracker-config:
    file: ./tracker-config.json
  reid-config:
    file: ./reid-config.json

volumes:
  vol-db:
  vol-media:
  vol-models:
  vol-mapping-model-weights:
    driver: local
  vol-mapping-torch-cache:
    driver: local
  vol-mapping-hf-cache:
    driver: local
```

## Required Supporting File: `mosquitto.conf`

Write `<deploy_dir>/mosquitto.conf` using the dedicated broker reference:

[mosquitto-config.md](./mosquitto-config.md)

## Environment Variables

Create `<deploy_dir>/.env` (or export before `docker compose up`):

```bash
SECRETSDIR=$(pwd)/secrets
DATABASE_PASSWORD=$(python3 -c "
import re, open as o
txt = open('secrets/django/secrets.py').read()
print(re.search(r\"DATABASE_PASSWORD='([^']+)'\", txt).group(1))
")
SUPASS=$(cat secrets/supass)
UID=$(id -u)
GID=$(id -g)
```
