# DLStreamer Pipeline Config

Write `<deploy_dir>/pipeline-config.json`. Generate one pipeline entry per camera using the
RTSP URLs and camera IDs the user provided, then wrap them in the config envelope below.

## Per-Camera Pipeline Entry Template

Replace `<camera_id>` and `<rtsp_url>` for each camera:

```json
{
  "name": "<camera_id>",
  "source": "gstreamer",
  "pipeline": "rtspsrc location=<rtsp_url> latency=200 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! gvapython class=PostDecodeTimestampCapture function=processFrame module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py name=timesync ! gvadetect model=/home/pipeline-server/models/intel/person-detection-retail-0013/FP32/person-detection-retail-0013.xml model-proc=/home/pipeline-server/models/object_detection/person/person-detection-retail-0013.json ! gvametaconvert add-tensor-data=true name=metaconvert ! gvapython class=PostInferenceDataPublish function=processFrame module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py name=datapublisher ! gvametapublish name=destination ! appsink sync=true",
  "auto_start": true,
  "parameters": {
    "type": "object",
    "properties": {
      "ntp_config": {
        "element": { "name": "timesync", "property": "kwarg", "format": "json" },
        "type": "object",
        "properties": { "ntpServer": { "type": "string" } }
      },
      "camera_config": {
        "element": { "name": "datapublisher", "property": "kwarg", "format": "json" },
        "type": "object",
        "properties": {
          "cameraid":           { "type": "string" },
          "metadatagenpolicy":  { "type": "string" },
          "publish_frame":      { "type": "boolean" },
          "detection_labels":   { "type": "array", "items": { "type": "string" } }
        }
      }
    }
  },
  "payload": {
    "parameters": {
      "ntp_config": { "ntpServer": "ntpserv" },
      "camera_config": {
        "cameraid": "<camera_id>",
        "metadatagenpolicy": "detectionPolicy",
        "detection_labels": ["person"]
      }
    }
  }
}
```

## Full File Envelope

```json
{
  "config": {
    "logging": { "C_LOG_LEVEL": "INFO", "PY_LOG_LEVEL": "INFO" },
    "pipelines": [
      /* ...one entry per camera, generated from the template above... */
    ]
  }
}
```

## Notes

- Detection model: `person-detection-retail-0013` (FP32). Downloaded automatically by the
  `model_downloader` service into the shared `vol-models` volume.
- The `ntpserv` value for `ntpServer` matches the NTP service hostname in docker-compose.
- Each pipeline entry must have a unique `"name"` — use the camera ID.
