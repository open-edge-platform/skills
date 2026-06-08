# Create Scene and Register Cameras via REST API

## 1. Authenticate

```python
import requests, json

MANAGER_URL = "https://localhost"
CA_CERT     = f"{DEPLOY_DIR}/secrets/certs/scenescape-ca.pem"
SUPASS      = open(f"{DEPLOY_DIR}/secrets/supass").read().strip()

resp = requests.post(
    f"{MANAGER_URL}/api/v1/auth",
    json={"username": "admin", "password": SUPASS},
    verify=CA_CERT, timeout=10,
)
resp.raise_for_status()
TOKEN = resp.json()["token"]
HEADERS = {"Authorization": f"Token {TOKEN}"}
```

## 2. Create the Scene (upload GLB map)

> **Note:** The `/api/v1/scene` POST endpoint requires `parent`, `transform`, `map_processed`,
> `regions`, and `tripwires` — all mandatory when a map file is **not** provided. If no GLB map
> is available yet (pre-mapping), use the Django ORM fallback below.

```python
with open(f"{DEPLOY_DIR}/scene.glb", "rb") as glb_file:
    resp = requests.post(
        f"{MANAGER_URL}/api/v1/scene",
        headers=HEADERS,
        files={"map": ("scene.glb", glb_file, "model/gltf-binary")},
        data={"name": scene_name},
        verify=CA_CERT, timeout=30,
    )
resp.raise_for_status()
scene = resp.json()
scene_uid = scene["uid"]
print(f"Scene created: uid={scene_uid}")
```

### Fallback — create scene without a map (pre-mapping)

If no GLB map file is available yet, create the scene directly via the Django shell:

```bash
SCENE_UUID=$(docker exec scenescape-web-1 bash -c "
cd /home/scenescape/SceneScape && python manage.py shell -c \"
from manager.models import Scene
s = Scene(name='${scene_name}')
s.save()
print(s.pk)
\" 2>/dev/null" | tail -1)
echo "Scene UUID: $SCENE_UUID"
```

Save `SCENE_UUID` — it is used as `scene_uid` when creating cameras below.

# Guard: if scale came back as zero, set a placeholder and warn
if float(scene.get("scale") or 0) == 0.0:
    r = requests.patch(
        f"{MANAGER_URL}/api/v1/scene/{scene_uid}",
        headers=HEADERS, json={"scale": 1.0},
        verify=CA_CERT, timeout=10,
    )
    r.raise_for_status()
    print("WARNING: Scene scale was 0 — set to 1.0. Measure real-world dimensions and update scale via the UI.")
```

## 3. Create Cameras

`cam_poses` and `intrinsics` come from the reconstruction result, in the same order as
`camera_ids`. The intrinsics matrix is 3×3:

```
[[fx, 0,  cx],
 [0,  fy, cy],
 [0,  0,   1]]
```

Extract `[fx, fy, cx, cy]` for the API:

```python
for idx, camera_id in enumerate(camera_ids):
    pose = cam_poses[idx]
    K    = intrinsics[idx]   # 3x3 as nested list
    fx, fy, cx, cy = K[0][0], K[1][1], K[0][2], K[1][2]

    payload = {
        "name":        camera_id,
        "sensor_id":   camera_id,
        "scene":       scene_uid,
        "translation": pose["translation"],      # [x, y, z]
        "rotation":    pose["rotation"],          # [x, y, z, w]  (quaternion)
        "intrinsics":  [fx, fy, cx, cy],
    }

    resp = requests.post(
        f"{MANAGER_URL}/api/v1/camera",
        headers=HEADERS, json=payload,
        verify=CA_CERT, timeout=10,
    )
    resp.raise_for_status()
    cam = resp.json()
    print(f"Camera registered: {camera_id}  uid={cam['uid']}")
```

## Notes

- `rotation` is a quaternion in `[x, y, z, w]` order as returned by the mapping service.
- If any POST fails with a 400 containing "sensor_id already exists", a camera with that
  sensor_id was registered in a previous run. Either delete the old camera via the UI/API
  or use a unique sensor_id per run.
- The manager URL is `https://localhost` (port 443 mapped in docker-compose).
