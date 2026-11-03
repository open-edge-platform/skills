<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Vision + sensor multimodal — weld defect detection

**User:**
> I want to catch defective welds — I have a camera on the weld and
> pressure/gas-flow sensors on the welder, and I only want an alert when
> both agree there's a problem. Each confirmed defect should also be logged
> as a quality issue in our OpenMES.

Both signals must combine into one verdict, so it routes to
**`manufacturing-app-recipe`** (`{{DEPLOYMENT}}=multimodal`, `FUSION_MODE=AND`)
rather than a single-modality skill. The OpenMES request turns on the
recipe's optional publisher (`{{OPENMES_ENABLED}}=yes`). The orchestrator
confirms the video/CSV input source and deployment target, and asks for the
OpenMES details:
- the base URL;
- the **path** to a token file (never the token itself);
- an existing work order ID and a non-blocking issue type ID;
- a station/line name.

It doesn't invent any of these. Then it builds.

Output:
- `./weld-defect-stack/` Docker Compose solution: DLSPS (vision) + Telegraf/
  InfluxDB + Time Series Analytics (sensor) + Fusion Analytics
- A fused alert only when the camera and the sensor flag the same weld
- A Grafana dashboard at `https://localhost:3000` with the live video panel,
  sensor trend, and fused-verdict table
- `./weld-defect-stack/openmes/`: the recipe's `openmes_publisher.py` reading
  the **fused** topic only (`fused_decision == 1`), so each confirmed defect
  becomes one OpenMES Issue and nothing is reported from the camera-only or
  sensor-only topics. The MQTT broker is published on `127.0.0.1:1883` only
  for this host-side publisher
