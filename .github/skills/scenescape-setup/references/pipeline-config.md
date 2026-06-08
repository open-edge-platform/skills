# DLStreamer Pipeline Config

The canonical pipeline config template is `queuing-config.json` downloaded in Step 2a from
`https://github.com/open-edge-platform/scenescape/blob/main/dlstreamer-pipeline-server/queuing-config.json`.

**Do not generate this file from scratch.** Instead, adapt the downloaded file for the user's cameras.

## Procedure

1. Copy the canonical template as the starting point:

```bash
cp <deploy_dir>/dlstreamer-pipeline-server/queuing-config.json <deploy_dir>/pipeline-config.json
```

2. Edit `<deploy_dir>/pipeline-config.json`:
   - The template has two entries (`qcam1`, `qcam2`). **Add or remove entries to match the user's
     camera count.**
   - For each camera entry, substitute:

     | Placeholder in template                     | Replace with                |
     | ------------------------------------------- | --------------------------- |
     | `"name": "qcam1"` / `"name": "qcam2"`       | `"name": "<camera_id>"`     |
     | `rtsp://mediaserver:8554/queuing-cam1`      | `<rtsp_url>`                |
     | `rtsp://mediaserver:8554/queuing-cam2`      | `<rtsp_url>`                |
     | `"cameraid": "atag-qcam1"` / `"atag-qcam2"` | `"cameraid": "<camera_id>"` |

   - Keep `add-reference-timestamp-meta=true` on `rtspsrc` — required for NTP timestamp extraction.
   - Keep all `sscape_adapter.py` module paths unchanged — they are container-internal paths.

## Notes

- Detection model: `person-detection-retail-0013` (FP32). Downloaded automatically by the
  `model_downloader` service into the shared `vol-models` volume.
- The `ntpServer` value `ntpserv` matches the NTP service hostname in `docker-compose.yml`.
- Each pipeline entry must have a unique `"name"` — use the camera ID.
- The `user_scripts/` directory containing `sscape_adapter.py` must be volume-mounted into the
  `video-analytics` container (see `docker-compose.yml`).
