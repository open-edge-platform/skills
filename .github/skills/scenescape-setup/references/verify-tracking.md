# Verify End-to-End Object Tracking

Subscribe to `scenescape/regulated/scene/<scene_uid>` and confirm that tracked objects
appear within 2 minutes of containers being live.

## Python Verification Script

```python
import json, ssl, threading
import paho.mqtt.client as mqtt

DEPLOY_DIR = "<deploy_dir>"
CA_CERT    = f"{DEPLOY_DIR}/secrets/certs/scenescape-ca.pem"
AUTH_FILE  = f"{DEPLOY_DIR}/secrets/browser.auth"

with open(AUTH_FILE) as f:
    auth = json.load(f)

TOPIC   = f"scenescape/regulated/scene/{scene_uid}"
result  = {}
done    = threading.Event()

def on_message(client, userdata, msg):
    data = json.loads(msg.payload)
    objects = data.get("objects") or data.get("tracked_objects") or []
    if len(objects) > 0:
        result["count"]   = len(objects)
        result["payload"] = data
        done.set()

client = mqtt.Client()
client.tls_set(ca_certs=CA_CERT)
client.username_pw_set(auth["user"], auth["password"])
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe(TOPIC, qos=1)
client.loop_start()

TIMEOUT_S = 120
if done.wait(timeout=TIMEOUT_S):
    print(f"Tracking confirmed — {result['count']} object(s) seen on {TOPIC}")
else:
    print("WARNING: No tracked objects seen within 2 minutes.")
    print("See troubleshooting section below for diagnostic steps.")

client.loop_stop()
client.disconnect()
```

## Troubleshooting Checklist

If no objects appear:

### 1. Check the Scene Controller logs

```bash
cd <deploy_dir>
docker compose logs scene --tail=50
```

Look for errors about: MQTT connection failures, schema validation errors, missing cameras.

### 2. Verify cameras are registered in the scene

```python
import requests
resp = requests.get(
    f"https://localhost/api/v1/cameras?scene={scene_uid}",
    headers=HEADERS, verify=CA_CERT,
)
cameras = resp.json()
print(f"{len(cameras)} camera(s) registered for scene {scene_uid}")
for c in cameras:
    print(f"  {c['name']}  sensor_id={c['sensor_id']}  uid={c['uid']}")
```

### 3. Check for non-zero camera pose

A camera with all-zero translation will be ignored by the controller.
Inspect `translation` in each registered camera's response JSON.

### 4. Check scene scale is non-zero

```python
resp = requests.get(
    f"https://localhost/api/v1/scene/{scene_uid}",
    headers=HEADERS, verify=CA_CERT,
)
print("scale =", resp.json().get("scale"))
```

A zero scale prevents regulated topic output. Fix: set a real-world scale via the UI
(Scene → Edit → Scale) or PATCH the field directly.

### 5. Verify raw detections are arriving from video-analytics

```bash
docker compose exec broker mosquitto_sub \
  -h broker.scenescape.intel.com -p 1883 \
  --cafile /mosquitto/secrets/certs/scenescape-ca.pem \
  -u webuser -P "<browser.auth password>" \
  -t "scenescape/data/camera/+" -C 3
```

If no messages appear, video-analytics pipelines are not detecting anything. Check:

- RTSP streams are accessible from inside the container
- The model files exist in the `vol-models` volume
- `docker compose logs video-analytics --tail=30`

### 6. Confirm controller sees the scene

```bash
docker compose logs scene | grep -i "scene\|camera\|calibrat"
```

The controller should log something like `"Loading scene <scene_uid>"` and
`"Camera <camera_id> calibrated"` after cameras are registered.
