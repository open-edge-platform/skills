# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Dummy OpenMES receiver: test target for openmes_publisher.py, with a live alert view.

Implements the subset of the OpenMES Issues API that the publisher uses:
  POST /api/v1/issues       -> 201 {"data": {...}}   (bearer token required)
  GET  /api/v1/issues       -> 200 {"data": [...]}   (bearer token required)
  GET  /api/v1/issues/<id>  -> 200 {"data": {...}}   (bearer token required)
Validation follows the real contract: work_order_id / issue_type_id must
exist, batch_step_id must exist if given, title <= 255 chars, description
<= 5000 chars, and unknown top-level fields are rejected with 422.

It also serves a read-only, auto-refreshing alert page at "/" and prints one
console line per received alert.

This is a stand-in for local testing only. It is not OpenMES. The page has
no login, so keep the default --host 127.0.0.1, or bind a LAN address only on
a trusted network.

Run:
  (umask 277; openssl rand -hex 24 > openmes_token)   # created read-only (0400)
  python dummy_openmes_receiver.py --token-file ./openmes_token
  # then open http://127.0.0.1:8099/ and point openmes-publisher.json at
  #   "base_url": "http://127.0.0.1:8099", "work_order_id": 1001, "issue_type_id": 7
"""

import argparse
import hmac
import json
import logging
import re
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

log = logging.getLogger("dummy-openmes")

ALLOWED_FIELDS = {"work_order_id", "issue_type_id", "title", "description", "batch_step_id"}
MAX_BODY_BYTES = 64 * 1024
UI_PAGE_LIMIT = 200


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class IssueStore:
    """Thread-safe in-memory issue store with an optional append-only JSONL log."""

    def __init__(self, max_issues, log_file):
        self.lock = threading.Lock()
        self.issues = deque(maxlen=max_issues)
        self.next_id = 1
        self.by_label = Counter()
        self.received_times = deque(maxlen=10_000)
        self.rejected = Counter()
        self.log_file = Path(log_file) if log_file else None

    def add(self, body, issue_type):
        details = parse_description(body.get("description"))
        with self.lock:
            issue = {
                "id": self.next_id,
                "work_order_id": body["work_order_id"],
                "issue_type_id": body["issue_type_id"],
                "issue_type": issue_type,
                "batch_step_id": body.get("batch_step_id"),
                "title": body["title"],
                "description": body.get("description"),
                "status": "OPEN",
                "reported_at": utc_now(),
                "created_at": utc_now(),
            }
            self.next_id += 1
            self.issues.append(issue)
            self.by_label[str(details.get("defect_label") or "unknown")] += 1
            self.received_times.append(time.time())
            if self.log_file:
                with self.log_file.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(issue, ensure_ascii=False) + "\n")
        return issue, details

    def get(self, issue_id):
        with self.lock:
            return next((i for i in self.issues if i["id"] == issue_id), None)

    def snapshot(self, since_id=0, limit=UI_PAGE_LIMIT):
        now = time.time()
        with self.lock:
            newer = [i for i in self.issues if i["id"] > since_id][-limit:] if limit > 0 else []
            per_min = sum(1 for t in self.received_times if now - t <= 60)
            return {
                "issues": newer,
                "total": self.next_id - 1,
                "held": len(self.issues),
                "per_minute": per_min,
                "by_label": dict(self.by_label.most_common()),
                "rejected": dict(self.rejected),
                "last_id": self.next_id - 1,
            }


def parse_description(desc):
    """The publisher stores event metadata as compact JSON in description."""
    if not isinstance(desc, str):
        return {}
    try:
        value = json.loads(desc)
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def validate(body, work_orders, issue_types, batch_steps):
    errors = {}
    for field in sorted(set(body) - ALLOWED_FIELDS):
        errors[field] = [f"The {field} field is prohibited."]
    for field, table in (("work_order_id", work_orders), ("issue_type_id", issue_types)):
        value = body.get(field)
        if value is None:
            errors[field] = [f"The {field} field is required."]
        elif isinstance(value, bool) or not isinstance(value, int) or value not in table:
            errors[field] = [f"The selected {field} is invalid."]
    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        errors["title"] = ["The title field is required."]
    elif len(title) > 255:
        errors["title"] = ["The title field must not be greater than 255 characters."]
    desc = body.get("description")
    if desc is not None and (not isinstance(desc, str) or len(desc) > 5000):
        errors["description"] = ["The description field must not be greater than 5000 characters."]
    step = body.get("batch_step_id")
    if step is not None and (isinstance(step, bool) or not isinstance(step, int) or step not in batch_steps):
        errors["batch_step_id"] = ["The selected batch_step_id is invalid."]
    return errors


def make_handler(cfg, store):
    token_file = Path(cfg.token_file)
    work_orders = set(cfg.work_order_id)
    issue_types = {tid: {"id": tid, "name": f"Quality - AI detected ({tid})", "is_blocking": False}
                   for tid in cfg.issue_type_id}
    batch_steps = set(cfg.batch_step_id)

    class Handler(BaseHTTPRequestHandler):
        server_version = "DummyOpenMES/1.0"

        def _send(self, code, payload, content_type="application/json"):
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if content_type.startswith("text/html"):
                self.send_header("Content-Security-Policy",
                                 "default-src 'none'; script-src 'self' 'unsafe-inline'; "
                                 "style-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self):
            # Re-read per request so a rotated token file works without a restart.
            try:
                expected = token_file.read_text().strip()
            except OSError:
                expected = ""
            got = self.headers.get("Authorization", "")
            if not expected or not got.startswith("Bearer ") or not hmac.compare_digest(
                    got[7:].strip().encode(), expected.encode()):
                with store.lock:
                    store.rejected["401"] += 1
                self._send(401, {"message": "Unauthenticated."})
                return False
            return True

        def do_GET(self):
            url = urlparse(self.path)
            path = url.path.rstrip("/") or "/"
            if path == "/":
                return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            if path == "/health":
                return self._send(200, {"status": "ok", "issues": store.snapshot(limit=0)["total"]})
            if path == "/ui/api/issues":
                q = parse_qs(url.query)
                try:
                    since = max(0, int(q.get("since_id", ["0"])[0]))
                except ValueError:
                    since = 0
                return self._send(200, store.snapshot(since_id=since))
            m = re.fullmatch(r"/api/v1/issues(?:/(\d+))?", path)
            if m:
                if not self._authorized():
                    return
                if m.group(1):
                    issue = store.get(int(m.group(1)))
                    return self._send(200, {"data": issue}) if issue else self._send(404, {"message": "Not Found"})
                return self._send(200, {"data": store.snapshot(limit=10_000)["issues"]})
            self._send(404, {"message": "Not Found"})

        def do_POST(self):
            if urlparse(self.path).path.rstrip("/") != "/api/v1/issues":
                return self._send(404, {"message": "Not Found"})
            if not self._authorized():
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY_BYTES:
                return self._send(413, {"message": "Payload too large."})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self._send(400, {"message": "Malformed JSON body."})
            errors = validate(body, work_orders, issue_types, batch_steps)
            if errors:
                with store.lock:
                    store.rejected["422"] += 1
                log.warning("Rejected issue (422): %s", errors)
                return self._send(422, {"message": "The given data was invalid.", "errors": errors})
            issue, d = store.add(body, issue_types[body["issue_type_id"]])
            log.info("ALERT #%d | %s | defect=%s | source=%s | observed=%s | camera=%s sensor=%s",
                     issue["id"], issue["title"], d.get("defect_label", "-"), d.get("source_id", "-"),
                     d.get("observed_at", "-"), d.get("vision_classification", "-"),
                     d.get("timeseries_classification", "-"))
            self._send(201, {"data": issue})

        def log_message(self, fmt, *args):
            log.debug("%s %s", self.address_string(), fmt % args)

    return Handler


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Dummy OpenMES - received alerts</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;background:#111827;color:#e5e7eb}
 header{padding:14px 20px;background:#1f2937;border-bottom:1px solid #374151;display:flex;gap:24px;align-items:center;flex-wrap:wrap}
 h1{font-size:18px;margin:0}.muted{color:#9ca3af;font-size:12px}
 .stat{font-size:13px}.stat b{font-size:20px;display:block;color:#f9fafb}
 #labels span{display:inline-block;background:#374151;border-radius:10px;padding:2px 8px;margin:2px;font-size:12px}
 button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:6px 12px;cursor:pointer}
 table{width:100%;border-collapse:collapse;font-size:13px}
 th,td{padding:6px 10px;border-bottom:1px solid #1f2937;text-align:left;vertical-align:top}
 th{position:sticky;top:0;background:#111827;color:#9ca3af;font-weight:600}
 tr.row{cursor:pointer}tr.row:hover{background:#1f2937}
 tr.new{animation:flash 2s ease-out}@keyframes flash{from{background:#7f1d1d}to{background:transparent}}
 .defect{color:#fca5a5;font-weight:600}pre{margin:0;white-space:pre-wrap;color:#d1d5db;background:#0b1220;padding:8px;border-radius:6px}
 .banner{padding:6px 20px;background:#78350f;color:#fde68a;font-size:12px}
</style></head><body>
<div class="banner">Dummy OpenMES for local testing - not a real MES. Read-only view; issues are created by openmes_publisher.py.</div>
<header>
 <div><h1>Received defect alerts</h1><div class="muted" id="status">connecting...</div></div>
 <div class="stat">Total<b id="total">0</b></div>
 <div class="stat">Last minute<b id="permin">0</b></div>
 <div class="stat">Rejected (401/422)<b id="rejected">0</b></div>
 <div id="labels"></div>
 <div style="margin-left:auto"><button id="pause">Pause</button></div>
</header>
<table><thead><tr><th>#</th><th>Received (local)</th><th>Defect</th><th>Camera</th><th>Sensor</th>
<th>Confidence</th><th>Observed at (UTC)</th><th>Source</th><th>Work order</th><th>Status</th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
(function(){
 const rows=document.getElementById('rows'); let lastId=0, paused=false, first=true; const MAX_ROWS=500;
 const td=t=>{const c=document.createElement('td'); c.textContent=(t===undefined||t===null||t==='')?'-':String(t); return c;};
 function details(i){try{return JSON.parse(i.description||'{}')}catch(e){return {}}}
 function add(i){
  const d=details(i), tr=document.createElement('tr'); tr.className='row'+(first?'':' new');
  const defect=td(d.defect_label||i.title); defect.className='defect';
  const conf=(typeof d.fusion_confidence==='number')?d.fusion_confidence.toFixed(3):(d.confidence??'');
  tr.append(td(i.id),td(new Date(i.created_at).toLocaleTimeString()),defect,td(d.vision_classification),
            td(d.timeseries_classification),td(conf),td(d.observed_at),td(d.source_id),td(i.work_order_id),td(i.status));
  const det=document.createElement('tr'); det.hidden=true; const c=document.createElement('td'); c.colSpan=10;
  const pre=document.createElement('pre'); pre.textContent=JSON.stringify({title:i.title,issue_type:i.issue_type,description:d},null,2);
  c.append(pre); det.append(c); tr.onclick=()=>{det.hidden=!det.hidden};
  rows.prepend(det); rows.prepend(tr);
  while(rows.children.length>MAX_ROWS*2) rows.lastElementChild.remove();
 }
 async function poll(){
  if(!paused){
   try{
    const r=await fetch('/ui/api/issues?since_id='+lastId,{cache:'no-store'}); const s=await r.json();
    s.issues.forEach(add); if(s.issues.length) lastId=s.issues[s.issues.length-1].id; first=false;
    document.getElementById('total').textContent=s.total;
    document.getElementById('permin').textContent=s.per_minute;
    document.getElementById('rejected').textContent=(s.rejected['401']||0)+' / '+(s.rejected['422']||0);
    const lab=document.getElementById('labels'); lab.replaceChildren();
    Object.entries(s.by_label).forEach(([k,v])=>{const e=document.createElement('span'); e.textContent=k+': '+v; lab.append(e);});
    document.getElementById('status').textContent='live - updated '+new Date().toLocaleTimeString();
   }catch(e){document.getElementById('status').textContent='receiver unreachable: '+e;}
  }
  setTimeout(poll,2000);
 }
 document.getElementById('pause').onclick=e=>{paused=!paused; e.target.textContent=paused?'Resume':'Pause';};
 poll();
})();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Dummy OpenMES receiver with a live alert view")
    ap.add_argument("--host", default="127.0.0.1", help="bind address (default loopback; the alert page has no login)")
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--token-file", required=True, help="file holding the bearer token the publisher sends")
    ap.add_argument("--work-order-id", type=int, action="append", help="accepted work order id (repeatable; default 1001, 2001)")
    ap.add_argument("--issue-type-id", type=int, action="append", help="accepted non-blocking issue type id (repeatable; default 7)")
    ap.add_argument("--batch-step-id", type=int, action="append", help="accepted batch step id (repeatable; default 501)")
    ap.add_argument("--max-issues", type=int, default=5000, help="issues kept in memory (oldest dropped)")
    ap.add_argument("--log-file", default="dummy_openmes_issues.jsonl", help="append-only JSONL log of issues ('' to disable)")
    ap.add_argument("--verbose", action="store_true", help="also log every HTTP request")
    cfg = ap.parse_args()
    cfg.work_order_id = cfg.work_order_id or [1001, 2001]
    cfg.issue_type_id = cfg.issue_type_id or [7]
    cfg.batch_step_id = cfg.batch_step_id or [501]

    logging.basicConfig(level=logging.DEBUG if cfg.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        if not Path(cfg.token_file).read_text().strip():
            raise SystemExit(f"Token file {cfg.token_file} is empty")
    except OSError as exc:
        raise SystemExit(f"Cannot read token file {cfg.token_file}: {exc}") from None

    store = IssueStore(cfg.max_issues, cfg.log_file)
    server = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(cfg, store))
    server.daemon_threads = True
    log.info("Dummy OpenMES receiver on http://%s:%d/  (API: /api/v1/issues, work orders %s, issue types %s)",
             cfg.host, cfg.port, cfg.work_order_id, cfg.issue_type_id)
    if cfg.host not in ("127.0.0.1", "localhost", "::1"):
        log.warning("Bound to %s: the read-only alert page is reachable without login on that network.", cfg.host)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
