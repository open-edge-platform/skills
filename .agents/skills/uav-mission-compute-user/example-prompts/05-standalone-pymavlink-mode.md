# 05 — Standalone pymavlink mode

Describe how to run UAV Vision Analytics in standalone mode rather than using the UAV Mission Compute SDK. Include source/configuration, model preparation, startup, how the UAV is armed for managed pipelines, CPU/GPU/NPU selection, output viewing, and shutdown. This is a planning answer only; do not execute commands.

## Expected guidance

- Explain that standalone mode supplies its own PX4, MAVLink router, MQTT, and metrics services.
- Include `make init` and `make model` before `make pymav-up`.
- Use `make start-rtsp DEVICE=cpu|gpu|npu|all`.
- Explain that the UAV must be armed or take off before managed output streams become available.
- Mention the standalone annotated output paths or port `8555`.
- End with `make pymav-down` for stopping the standalone stack.
- Avoid requiring the UAV Mission Compute SDK to be running for this mode.
