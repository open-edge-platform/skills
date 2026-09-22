# 01 — Sim stack start and validation

I have a fresh checkout of the UAV Mission Compute SDK on Ubuntu with Docker and an Intel GPU. Explain the exact sequence to initialize it, start the default simulated three-camera stack, validate the infrastructure, and make the camera streams available for testing. Do not run commands or claim that the stack is running.

## Expected guidance

- Start from the SDK root and run `make init`.
- Use `/start-stack sim` or the equivalent `make up-sim-camera` flow for the default Gazebo multi-camera stack.
- Validate with `/validate-infra` to check PX4, MQTT, bridges, REST, and RTSP health.
- State that RTSP paths are only published while the UAV is armed and that the documented arm endpoint is `curl -X POST http://localhost:8080/action/arm`.
- Call out the three simulated camera streams: `nadir`, `forward`, and `rear`.
- Avoid claiming the stack was executed or that services are already healthy.
