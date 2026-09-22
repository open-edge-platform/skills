# 02 — Camera mode switching

The SDK is currently running in simulated camera mode. I need to switch first to a USB camera and later to an Intel RealSense D400 camera. Give me the safe command-driven procedure, including device discovery, environment initialization, teardown, startup targets, expected streams, and the most relevant verification step. Do not start the stack.

## Expected guidance

- Explain that only one camera profile should run at a time and the current stack must be stopped before switching.
- Use `/switch-camera-mode usb` and `/switch-camera-mode realsense` as the primary mode-switch commands.
- Use `v4l2-ctl --list-devices` for USB discovery and identify `USB_VIDEO_DEVICE` and `USB_CAMERA_ID` as relevant environment values.
- Use `make init` after a RealSense camera is connected or reconnected so the `RS_VIDEO` and `RS_MEDIA` nodes are detected.
- Use `make up-usb-camera` for USB mode and `make up-realsense-camera` for RealSense mode.
- Identify USB as usually `nadir` and RealSense as `ir` and `depth` streams.
- Recommend `docker compose ps` and the active camera bridge or camera list as a verification step.
- Avoid inventing a fourth profile or claiming that the switch was performed.
