# Mosquitto Broker Config

Write this file to `<deploy_dir>/mosquitto.conf`:

```
allow_anonymous true

listener 1883
keyfile /mosquitto/secrets/certs/scenescape-broker.key
certfile /mosquitto/secrets/certs/scenescape-broker.crt
tls_version tlsv1.3

listener 1884
cafile /mosquitto/secrets/certs/scenescape-ca.pem
keyfile /mosquitto/secrets/certs/scenescape-broker.key
certfile /mosquitto/secrets/certs/scenescape-broker.crt
protocol websockets
```

## Optional Mosquitto Password File

If you need a password file for a stricter broker configuration, generate it after running
`generate_secrets.sh` by extracting credentials from the auth JSON files:

```bash
SECRETSDIR=<deploy_dir>/secrets
: > "$SECRETSDIR/mosquitto.passwd"
for AUTH in controller.auth browser.auth calibration.auth; do
  USER=$(python3 -c "import json; d=json.load(open('$SECRETSDIR/$AUTH')); print(d['user'])")
  PASS=$(python3 -c "import json; d=json.load(open('$SECRETSDIR/$AUTH')); print(d['password'])")
  docker run --rm -v "$SECRETSDIR:/work" eclipse-mosquitto:2.0.22 \
    sh -lc "mosquitto_passwd -b /work/mosquitto.passwd '$USER' '$PASS'"
done
```
