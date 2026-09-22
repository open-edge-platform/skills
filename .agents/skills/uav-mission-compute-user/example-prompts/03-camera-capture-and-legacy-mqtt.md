# 03 — Camera capture and legacy MQTT

I need to capture one nadir frame and then record a five-second clip from the UAV Mission Compute SDK. Explain the default RTSP commands, how arming affects the result, how to validate the JPEG, and when the legacy MQTT capture path should be used. Also mention how to capture an annotated processed frame.

## Expected guidance

- Use `/capture-camera nadir` as the primary capture command.
- Use the raw RTSP URL pattern `rtsp://localhost:8554/uav-1/<camera>`.
- Arm the UAV before capture because RTSP paths are unavailable while disarmed.
- Use `ffmpeg -frames:v 1` for a single JPEG and `ffmpeg -t 5 -c copy` for a five-second clip.
- Suggest file or image validation for the captured JPEG.
- Explain that MQTT capture is legacy mode and is appropriate when `USE_RTSP=false` or when checking legacy topics.
- Mention the processed frame topic path `uav/uav-1/camera/<camera>/processed` for an annotated frame.
- Avoid claiming a frame or clip was actually captured.
