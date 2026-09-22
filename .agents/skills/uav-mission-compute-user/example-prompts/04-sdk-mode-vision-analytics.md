# 04 — SDK mode with UAV Vision Analytics

I want to run UAV Vision Analytics in UAV Mission Compute SDK mode. I can either download the ZIP or clone the whole edge-ai-suites repository. Explain both source options and the ordered setup from the SDK infrastructure through model preparation, analytics startup, managed CPU/GPU/NPU pipelines, and annotated RTSP output. Do not run anything.

## Expected guidance

- Provide both the release ZIP/unzip path and the git clone path.
- State that the SDK core infrastructure must be started before the analytics application.
- Include `make init` and `make up-sim-camera` for the SDK side and `make model` plus `make uavsdk-up` for the analytics side.
- Explain why `HOST_IP=0.0.0.0` may be needed when the analytics stack is in a separate Docker network.
- Use `make start-rtsp DEVICE=cpu|gpu|npu|all` for managed pipelines.
- State that annotated SDK-mode streams are served on port `8555` at `nadir`, `forward`, and `rear` paths.
- Avoid conflating SDK mode with standalone `pymavlink` mode or claiming live output.
