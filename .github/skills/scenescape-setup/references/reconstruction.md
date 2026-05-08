# 3D Reconstruction: Capture Frames and Call Mapping Service

## 1. Capture Calibration Frames via MQTT

Send `getcalibrationimage` to the DLStreamer command topic for each camera. The
`PostInferenceDataPublish` adapter responds by publishing an unannotated JPEG frame to
`scenescape/image/calibration/camera/<camera_id>`.

Read broker credentials from `<deploy_dir>/secrets/browser.auth`.

```python
import json, ssl, time, threading
import paho.mqtt.client as mqtt

DEPLOY_DIR = "<deploy_dir>"
CA_CERT    = f"{DEPLOY_DIR}/secrets/certs/scenescape-ca.pem"
AUTH_FILE  = f"{DEPLOY_DIR}/secrets/browser.auth"

with open(AUTH_FILE) as f:
    auth = json.load(f)

images   = {}            # camera_id -> base64 JPEG string
lock     = threading.Event()
expected = set(camera_ids)

def on_message(client, userdata, msg):
    data = json.loads(msg.payload)
    topic_parts = msg.topic.split("/")
    camera_id = topic_parts[-1]   # last segment of scenescape/image/calibration/camera/<id>
    if "image" in data and camera_id in expected:
        images[camera_id] = data["image"]
        if expected <= set(images):
            lock.set()

client = mqtt.Client()
client.tls_set(ca_certs=CA_CERT)
client.username_pw_set(auth["user"], auth["password"])
client.on_message = on_message
client.connect("localhost", 8883, 60)
client.subscribe("scenescape/image/calibration/camera/+", qos=2)
client.loop_start()

# Trigger frame capture from each camera
for camera_id in camera_ids:
    client.publish(
        f"scenescape/cmd/camera/{camera_id}",
        "getcalibrationimage",
        qos=2,
    )

timeout = 30 * len(camera_ids)
if not lock.wait(timeout=timeout):
    missing = expected - set(images)
    raise TimeoutError(f"No calibration image received from: {missing}")

client.loop_stop()
client.disconnect()
print(f"Collected calibration frames from: {list(images)}")
```

## 2. Submit Reconstruction Job (Async)

```python
import requests, base64, io, time

MAPPING_URL = "https://localhost:8444"
CA_CERT     = f"{DEPLOY_DIR}/secrets/certs/scenescape-ca.pem"

files = []
for camera_id in camera_ids:   # preserve user-specified order
    img_bytes = base64.b64decode(images[camera_id])
    files.append(("images",     (f"{camera_id}.jpg", io.BytesIO(img_bytes), "image/jpeg")))
    files.append(("camera_ids", (None, camera_id)))

data = {"output_format": "glb", "mesh_type": "mesh"}
resp = requests.post(
    f"{MAPPING_URL}/reconstruction",
    data=data, files=files,
    verify=CA_CERT, timeout=30,
)
resp.raise_for_status()
request_id = resp.json()["request_id"]
print(f"Reconstruction queued: {request_id}")
```

## 3. Poll Until Complete

```python
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S  = 900   # 15 minutes
deadline = time.time() + POLL_TIMEOUT_S

while time.time() < deadline:
    sr = requests.get(
        f"{MAPPING_URL}/reconstruction/status/{request_id}",
        verify=CA_CERT, timeout=10,
    )
    sr.raise_for_status()
    status = sr.json()
    state  = status.get("state", "")
    print(f"  state={state}  {status.get('message', '')}")

    if state == "complete":
        result = status["result"]
        break
    if state == "failed":
        raise RuntimeError(f"Reconstruction failed: {status.get('error')}")

    time.sleep(POLL_INTERVAL_S)
else:
    raise TimeoutError("Reconstruction did not complete within 15 minutes")
```

## 4. Extract Results

```python
glb_b64    = result["glb_data"]       # base64-encoded GLB
cam_poses  = result["camera_poses"]   # [{rotation:[x,y,z,w], translation:[x,y,z]}, ...]
intrinsics = result["intrinsics"]     # [[[fx,0,cx],[0,fy,cy],[0,0,1]], ...]  (one per camera)

with open(f"{DEPLOY_DIR}/scene.glb", "wb") as f:
    f.write(base64.b64decode(glb_b64))

print(f"GLB saved. Camera poses: {len(cam_poses)}, intrinsics: {len(intrinsics)}")
```

`cam_poses` and `intrinsics` are in the same order as `camera_ids` (the order images were sent).
