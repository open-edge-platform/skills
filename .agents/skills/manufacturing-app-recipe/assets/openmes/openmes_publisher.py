# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
# Run: python openmes_publisher.py --config ./openmes-publisher.json

import argparse
import hashlib
import json
import logging
import re
import sqlite3
import ssl
from datetime import datetime, timezone
from pathlib import Path
import time

import paho.mqtt.client as mqtt
import requests


log = logging.getLogger("openmes-publisher")

_MISSING = object()
_KAPACITOR_TS = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?\s*([+-]\d{2}:?\d{2}|Z)?"
)


def ptr(doc, path, default=_MISSING):
    """Resolve a JSON Pointer (RFC 6901). Missing keys return `default`, or raise if none given."""
    if not path:
        return doc
    cur = doc
    try:
        for p in path.strip("/").split("/"):
            p = p.replace("~1", "/").replace("~0", "~")
            cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    except (KeyError, IndexError, TypeError, ValueError):
        if default is _MISSING:
            raise KeyError(f"JSON pointer {path!r} not found") from None
        return default
    if cur is None and default is not _MISSING:
        return default
    return cur


def first_ptr(doc, paths):
    """Return the first non-null value among one or more JSON Pointers."""
    for path in [paths] if isinstance(paths, str) else paths:
        value = ptr(doc, path, None)
        if value is not None:
            return value
    raise KeyError(f"none of the JSON pointers {paths!r} has a value")


def to_utc(value, fmt):
    if fmt == "iso8601":
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    elif fmt == "kapacitor":
        # Kapacitor alert time, e.g. "2026-09-08 12:00:00.150000000 +0000 UTC"
        m = _KAPACITOR_TS.match(str(value).strip())
        if not m:
            raise ValueError(f"Unparseable Kapacitor timestamp {value!r}")
        date, clock, frac, tz = m.groups()
        tz = "+00:00" if tz in (None, "Z") else (tz if ":" in tz else f"{tz[:3]}:{tz[3:]}")
        frac = f".{(frac or '0')[:6].ljust(6, '0')}"
        dt = datetime.fromisoformat(f"{date}T{clock}{frac}{tz}")
    elif fmt == "unix_ns":
        ns = int(value)
        sec, frac = divmod(ns, 1_000_000_000)
        dt = datetime.fromtimestamp(sec, timezone.utc).replace(microsecond=frac // 1000)
    elif fmt == "unix_s":
        dt = datetime.fromtimestamp(float(value), timezone.utc)
    else:
        raise ValueError("Unsupported timestamp format")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self, db_path="openmes_events.db"):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS events (
          event_id TEXT PRIMARY KEY,
          state TEXT NOT NULL,
          body TEXT NOT NULL,
          issue_id TEXT,
          created_at REAL NOT NULL
        )""")
        self.db.commit()

    def insert_if_new(self, event_id, body):
        try:
            self.db.execute(
                "INSERT INTO events(event_id,state,body,created_at) VALUES(?,?,?,?)",
                (event_id, "pending", json.dumps(body), time.time()),
            )
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def mark(self, event_id, state, issue_id=None):
        self.db.execute(
            "UPDATE events SET state=?, issue_id=? WHERE event_id=?",
            (state, issue_id, event_id),
        )
        self.db.commit()


def make_event_id(source_id, mode, work_order_id, issue_type_id, label, observed_at, item_id=None):
    key = {
        "source_id": source_id,
        "mode": mode,
        "work_order_id": work_order_id,
        "issue_type_id": issue_type_id,
        "label": label,
        "observed_at": observed_at,
        "item_id": item_id,
    }
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = json.loads(Path(args.config).read_text())

    store = Store(cfg.get("sqlite_db", "openmes_events.db"))

    mode = cfg["mode"]  # vision | ts | multimodal
    if mode not in ("vision", "ts", "multimodal"):
        raise SystemExit(f"mode must be vision, ts or multimodal, got {mode!r}")
    source_id = cfg["source_id"]
    topic = cfg["mqtt"]["topic"]

    base_url = cfg["openmes"]["base_url"].rstrip("/")
    endpoint = f"{base_url}/api/v1/issues"
    token_file = Path(cfg["openmes"]["token_file"])
    if not token_file.read_text().strip():
        raise SystemExit(f"OpenMES token file {token_file} is empty")

    work_order_id = int(cfg["openmes"]["work_order_id"])
    issue_type_id = int(cfg["openmes"]["issue_type_id"])
    batch_step_id = cfg["openmes"].get("batch_step_id")

    ts_format = cfg.get("timestamp_format", "iso8601")
    fields = cfg["fields"]

    defect_labels = set(cfg.get("defect_labels", []))
    min_conf = float(cfg.get("min_confidence", 0.8))
    defect_equals = cfg.get("defect_equals", 1)
    if mode == "vision" and not defect_labels:
        raise SystemExit("defect_labels is required when mode=vision")

    session = requests.Session()
    session.verify = cfg.get("tls_ca_file", True)
    # Self-hosted OpenMES is usually on the LAN; ignore host http(s)_proxy unless opted in.
    session.trust_env = bool(cfg.get("use_env_proxy", False))

    def publish_to_openmes(body, event_id):
        # Re-read per request so a rotated token file takes effect without a restart.
        token = token_file.read_text().strip()
        try:
            r = session.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=(3.05, 10),
                allow_redirects=False,
            )
            if r.status_code == 201:
                issue_id = str(r.json()["data"]["id"])
                store.mark(event_id, "delivered", issue_id)
                log.info("Delivered event=%s issue_id=%s", event_id, issue_id)
            elif r.status_code in (401, 403):
                store.mark(event_id, "blocked")
                log.error("Auth failure (%s). Fix token/permissions.", r.status_code)
            elif r.status_code in (400, 404, 422):
                store.mark(event_id, "rejected")
                log.error("Rejected event=%s (%s): %s", event_id, r.status_code, r.text[:300])
            else:
                store.mark(event_id, "ambiguous")
                log.error("Ambiguous event=%s (%s)", event_id, r.status_code)
        except requests.RequestException:
            store.mark(event_id, "ambiguous")
            log.error("HTTP failure event=%s (ambiguous)", event_id)

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            log.error("MQTT connect failed rc=%s", reason_code)
            return
        client.subscribe(topic, qos=1)
        log.info("Subscribed topic=%s", topic)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))

            label = ptr(payload, fields.get("label"), None) if fields.get("label") else None
            ts_val = first_ptr(payload, fields["timestamp"])
            observed_at = to_utc(ts_val, ts_format)
            item_id = ptr(payload, fields["item_id"], None) if fields.get("item_id") else None

            # Defect filter
            is_defect = False
            confidence = None

            if mode == "vision":
                confidence = float(ptr(payload, fields["confidence"]))
                is_defect = (label in defect_labels) and (confidence >= min_conf)
            else:
                flag = ptr(payload, fields["defect"])
                is_defect = (flag == defect_equals)

            if not is_defect:
                return

            label = label if label is not None else "anomaly"
            metadata = {
                "source_id": source_id,
                "modality": mode,
                "observed_at": observed_at,
                "defect_label": label,
                "item_id": item_id,
            }
            if confidence is not None:
                metadata["confidence"] = confidence

            # extra mapped metadata
            for k, p in cfg.get("details", {}).items():
                metadata[k] = ptr(payload, p, None)

            event_id = make_event_id(
                source_id, mode, work_order_id, issue_type_id, str(label), observed_at, item_id
            )
            metadata["event_id"] = event_id

            description = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
            if len(description) > 5000:
                log.error("Skipping oversize description (>5000 chars), event=%s", event_id)
                return

            body = {
                "work_order_id": work_order_id,
                "issue_type_id": issue_type_id,
                "title": f"[{mode}] {source_id}: {label}"[:255],
                "description": description,
            }
            if batch_step_id:
                body["batch_step_id"] = int(batch_step_id)

            is_new = store.insert_if_new(event_id, body)
            if not is_new:
                log.info("Duplicate event ignored: %s", event_id)
                return

            publish_to_openmes(body, event_id)

        except Exception as e:
            log.exception("Bad message, ignored: %s", e)

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=cfg["mqtt"]["client_id"],
        clean_session=False,
    )
    if cfg["mqtt"].get("username"):
        pw = Path(cfg["mqtt"]["password_file"]).read_text().strip()
        client.username_pw_set(cfg["mqtt"]["username"], pw)
    if cfg["mqtt"].get("tls", False):
        client.tls_set(ca_certs=cfg["mqtt"].get("ca_file"), cert_reqs=ssl.CERT_REQUIRED)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(cfg["mqtt"]["host"], int(cfg["mqtt"].get("port", 1883)), keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
