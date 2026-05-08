#!/bin/bash -e
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Generates all secrets required by a SceneScape deployment.
# Usage: bash generate_secrets.sh [SUPASS]
#
# If SUPASS is not supplied, a random one is generated and written to secrets/supass.
# Run this script from <deploy_dir>/.

SECRETSDIR="$(cd "$(dirname "$0")" && pwd)/secrets"
CERTDOMAIN="scenescape.intel.com"
CERTPASS=$(openssl rand -base64 33)
DBPASS=$(openssl rand -base64 12)
SUPASS="${1:-$(openssl rand -base64 16)}"

mkdir -p "$SECRETSDIR/ca" "$SECRETSDIR/certs"

# ── Root CA ───────────────────────────────────────────────────────────────────
echo "Generating root CA key..."
openssl ecparam -name secp384r1 -genkey \
  | openssl ec -aes256 -passout pass:"$CERTPASS" \
    -out "$SECRETSDIR/ca/scenescape-ca.key"
chmod 0644 "$SECRETSDIR/ca/scenescape-ca.key"

echo "Generating root CA certificate..."
openssl req -passin pass:"$CERTPASS" -x509 -new \
  -key "$SECRETSDIR/ca/scenescape-ca.key" -days 1825 \
  -out "$SECRETSDIR/certs/scenescape-ca.pem" \
  -subj "/CN=ca.$CERTDOMAIN"
chmod 0644 "$SECRETSDIR/certs/scenescape-ca.pem"

# ── Helper: issue a service certificate ──────────────────────────────────────
# Usage: issue_cert <hostname> <serverAuth|clientAuth>
issue_cert() {
  local HOST="$1" USAGE="$2"
  local KEYFILE="$SECRETSDIR/certs/scenescape-${HOST}.key"
  local CSRFILE="$SECRETSDIR/certs/scenescape-${HOST}.csr"
  local CRTFILE="$SECRETSDIR/certs/scenescape-${HOST}.crt"
  local SAN="DNS.1=${HOST}.${CERTDOMAIN}"

  echo "Generating ${HOST}.key..."
  openssl ecparam -name secp384r1 -genkey -noout -out "$KEYFILE"
  chmod 0644 "$KEYFILE"

  openssl req -new -key "$KEYFILE" -out "$CSRFILE" \
    -subj "/CN=${HOST}.${CERTDOMAIN}" \
    -addext "subjectAltName=${SAN}"

  openssl x509 -passin pass:"$CERTPASS" -req \
    -in "$CSRFILE" \
    -CA "$SECRETSDIR/certs/scenescape-ca.pem" \
    -CAkey "$SECRETSDIR/ca/scenescape-ca.key" \
    -CAcreateserial \
    -out "$CRTFILE" -days 360 \
    -extfile <(printf "subjectAltName=${SAN}\nextendedKeyUsage=${USAGE}\n")
  chmod 0644 "$CRTFILE"
}

issue_cert broker          serverAuth
issue_cert web             serverAuth
issue_cert vdms-c          clientAuth
issue_cert vdms            serverAuth
issue_cert autocalibration serverAuth
issue_cert mapping         serverAuth

# ── MQTT auth files ───────────────────────────────────────────────────────────
# Format: {"user": "<name>", "password": "<pass>"}
issue_auth() {
  local FILE="$SECRETSDIR/$1" USER="$2"
  local PASS
  PASS=$(openssl rand -base64 12)
  echo "{\"user\": \"${USER}\", \"password\": \"${PASS}\"}" > "$FILE"
  chmod 0644 "$FILE"
}

issue_auth controller.auth  scenectrl
issue_auth browser.auth     webuser
issue_auth calibration.auth calibration

# ── Django secret key ─────────────────────────────────────────────────────────
mkdir -p "$SECRETSDIR/django"
SECRET_KEY=$(python3 -c \
  'import secrets; chars="abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"; \
   print("".join(secrets.choice(chars) for _ in range(50)))')
printf "SECRET_KEY='%s'\nDATABASE_PASSWORD='%s'\n" "$SECRET_KEY" "$DBPASS" \
  > "$SECRETSDIR/django/secrets.py"

# ── Postgres password ─────────────────────────────────────────────────────────
mkdir -p "$SECRETSDIR/pgserver"
printf 'POSTGRES_PASSWORD="%s"\n' "$DBPASS" > "$SECRETSDIR/pgserver/pgserver.env"

# ── Superuser password ────────────────────────────────────────────────────────
echo -n "$SUPASS" > "$SECRETSDIR/supass"
chmod 0600 "$SECRETSDIR/supass"

echo ""
echo "Secrets written to: $SECRETSDIR"
echo "Superuser password: $SUPASS"
echo "(also saved to $SECRETSDIR/supass)"
