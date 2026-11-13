---
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
name: manufacturing-ai-app-builder
description: >-
  Conversational orchestrator that turns a plain manufacturing-quality business
  objective into a working Intel Edge AI application by asking only business
  questions — never which framework, model, device, or whether the answer is
  "vision", "time series", or "both" — proposing a plan, and building the
  deliverable by DELEGATING to the right skill(s) after you confirm.
license: Apache-2.0
compatibility: >-
  External delegates require git/gh, github.com access, Node.js >= 22.20,
  and the pinned CLI `npx skills@1.7.4` (never @latest).
  `manufacturing-app-recipe` is installed with the same CLI from its folder
  URL when missing. Surface each delegate's Docker Compose v2 and Intel CPU/GPU/NPU
  requirements during planning; do not assume availability.
metadata:
  author: open-edge-platform
  tags: "orchestrator business-objective skill-discovery planning manufacturing time-series multimodal vision"
allowed-tools: bash git gh
---

# Manufacturing AI App Builder — business-objective orchestrator

Own the conversation: turn a manufacturing-quality business outcome into a
running Intel Edge AI application. Infer technology from the input signals
instead of asking the user to choose it, except for Step 1 Q8.

1. **Ask business questions** — outcome, what feeds the decision (camera,
   sensor, or both), deployment target, hardware, operations — never ask which
   framework/model/precision/device, or the modality, by name.
2. **Discover** the relevant skill(s) — the manufacturing recipe,
   or the vision-only skills, from
   [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) and
   [`references/DISCOVERY.md`](references/DISCOVERY.md).
3. **Propose a plan** — deliverable, which skill(s) will build it, and the
   technology you inferred — and **wait for explicit confirmation**.
4. **Build only after approval** by delegating to the chosen skill(s). Nothing
   is created before the user confirms.

## When to use this skill

Use for manufacturing defect detection, quality monitoring or predictive
maintenance when the user has not named a concrete skill. Clarify whether
the decision depends on camera data, sensor data or both correlated together,
then route to the appropriate delegate.

**Do not** use this skill when the user already named a specific skill
(invoke that skill directly), when the objective has nothing to do with
manufacturing quality/monitoring, or when the user wants a pure code answer
with no deployable artifact.

## Reference files (load on demand)

| File | Load when |
|---|---|
| [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) | Mapping a business objective → the delegate skill(s). Load in Step 2 (Discover). |
| [`references/DISCOVERY.md`](references/DISCOVERY.md) | Confirming a delegate is available locally, or fetching one that isn't. Load in Step 2 when the catalog is stale or a skill is missing. |

Do **not** load delegate skills' bodies yourself up front — you hand off to
them in Step 5 and *they* load their own references.

## Procedure

### Step 1 — Understand the business objective (Q&A)

Ask a **short, batched** set of business questions in ONE message (offer
sensible defaults in brackets; accept `go`/`defaults`/empty to take them).
Adapt the wording to the stated outcome, but cover these axes:

1. **Outcome** — what decision/insight/action do you want? (e.g. "flag a
   defective weld", "catch a bearing before it fails", "spot anomalous power
   output", "detect scratches on parts").
2. **What feeds the decision?** — a **camera/video feed** only, a
   **sensor stream** only (pressure, vibration, current, temperature, power,
   OPC-UA/MQTT tag), or **both together** (the camera and the sensor must
   agree/combine on one verdict)? If the user's outcome already implies one
   or two of these clearly, infer it and only confirm — don't force a
   redundant question.
3. **Inputs** — for a camera: an RTSP camera [default] or USB/sample/ONVIF
   camera; for a sensor: a real OPC-UA server/MQTT broker or a looping sample
   dataset [default].
4. **Deployment target** — a quick local demo/POC, or a single-host Docker
   Compose solution? [Docker Compose]
5. **Hardware** — Intel GPU (default) for vision, or Intel CPU/NPU?
6. **Operations** — needs a dashboard/UI vs just an alert; MQTT or OPC-UA
   alerting? Should confirmed defects also be logged as quality issues in
   an OpenMES system? [reasonable default per domain; OpenMES off unless
   asked]. If the user already asked for OpenMES (for example "log each
   defect in our OpenMES"), don't ask whether again; go straight to the
   details. Ask for: the OpenMES base URL, the **path** to a token file
   (never the token itself), an existing work order ID, a **non-blocking**
   issue type ID, and a station/line name. These are the user's own system
   details, not technology choices, so asking for them is allowed. Hand them
   over to `manufacturing-app-recipe` as `{{OPENMES_*}}` parameters; never
   invent them.
7. **Where to build it** — an absolute path to an existing checkout to add
   to (sensor-only recipe adds `apps/<name>/` to an existing
   `industrial-edge-insights-time-series` clone), or where to create a new
   standalone stack directory (multimodal recipe). Skip only if the invoking
   context already makes this unambiguous — never let the delegate default
   to the current working directory or invent a path.
8. **Explanation layer — ask by name** — whenever the decision fuses camera
    and sensor signals into one verdict, you MUST ask which deployment the
    user wants and name the three modes explicitly: `multimodal` (fused
    alert only, no language model), `vllm` (adds an Explainability
    dashboard where an operator picks a fused result and a vision-language
    model explains it from the stored frame and the sensor readings), or
    `agentic` (adds an Agentic dashboard where **Run Agentic Analysis**
    produces a policy decision, analysis and ticket for a time window; it
    includes the `vllm` layer). This is a deliberate
    exception to the "never name technology" rule: the explanation layers
    pull in a real LLM/VLM, extra hardware, and extra setup time, so the
    user has to opt in knowingly. Never skip this question, never assume
    `multimodal`, and never reword it into a generic "do you want
    explanations?" that hides the mode names.
    If the answer is `vllm` or `agentic`, also ask (as availability, not as
    a technology choice) whether the explanation models are already on the
    host or which Hugging Face/OpenVINO ids to fetch: one vision-language
    model (plus an optional fine-tuned adapter) for both modes, and a second
    agent LLM for `agentic`. The recipe never invents them. State the
    hardware gate in the same message: the vision-language model needs an
    Intel GPU and is validated on Core Ultra Series 3 with at least 32 GB RAM.

**Use business questions, not technology menus.** State inferred defaults
as decisions, then ask for confirmation or a business-fact override
("live camera or sample footage?"). Do not offer protocol, framework or
device menus. Only Q8's mode names and explanation-model availability/ids
may be technical questions ("already on the host, or which ids to fetch?").
Always request the **absolute build location** (Q7) and any missing business
inputs (and, when OpenMES is wanted, the base URL, token file *path*, work
order ID, non-blocking issue type ID, and station/line name) in this same
single message.

Keep questions to routing-relevant business facts. OpenMES connection
details identify the user's system and are permitted whenever it is wanted.

### Step 2 — Discover the relevant skill(s)

**Always open and read** [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md)
with the view tool in this step — even when the routing table below makes the
answer look obvious, and even when the user says nothing is installed or asks
for a plan only (reading a reference file is not building). Map the answers to
one **primary** skill (and any **supporting** skills), and record the catalog
row you matched so you can cite it in the plan. If the
objective is ambiguous or a delegate's availability is unclear, load
[`references/DISCOVERY.md`](references/DISCOVERY.md). Routing summary:

| What feeds the decision (Step 1, Q2) | Full stack + dashboard needed? | Route to |
|---|---|---|
| **Both** camera + sensor, one fused verdict | yes (always — this is the point of multimodal correlation) | **`manufacturing-app-recipe`**; choose `{{DEPLOYMENT}}` from Q8: `multimodal` for fused alerts only, `vllm` for written explanations, or `agentic` for agent-coordinated explanations (which includes the `vllm` layer) |
| **Sensor only** | yes — simulator/real ingest + Kapacitor UDF + Grafana + app registry | **`manufacturing-app-recipe`** (`{{DEPLOYMENT}}=ts`) |
| **Sensor only** | no — just a UDF/TICKscript against an already-running microservice | **`time-series-analytics-user`** |
| **Camera only** | yes — annotated video + dashboard + alerts, any vertical | **`metro-ai-app-recipe`** |
| **Camera only** | no — quick demo/PoC, custom pipeline code, or DeepStream migration | **`dlstreamer-coding-agent`** (or `metro-ai-app-recipe` demo mode) |
| **Camera only** | no — just deploy/operate the pipeline server via REST, no dashboard | **`dlsps-user`** |
| **Camera only**, multi-camera/spatial correlation (no sensor) | yes | **`scenescape-setup`** via `metro-ai-app-recipe`'s Scenescape path |

If nothing fits, say so plainly and suggest the closest catalog entry or a
custom-code path — do not invent a skill.

### Step 3 — Decide the deliverable & infer technology

From the answers decide the shape of the deliverable (quick single app vs
end-to-end multimodal/vision/sensor solution vs cluster deploy) and **silently
infer** every technical parameter the chosen delegate needs (vision model,
sensor UDF pattern, multimodal mode/tolerance, device, topics,
mode flags, etc.) using each recipe's own parameter table
(`{{OBJECT}}`, `{{APP_NAME}}`/`{{STACK_DIR}}`, `{{FUSION_MODE}}`, ...). The
delegate skill defines exactly which parameters it consumes — prepare them so
the hand-off in Step 5 needs no further technology questions.

For a fused full-stack objective, always ask Q8 **by name** before selecting
the deployment, and carry the user's answer through verbatim. Do not silently
default to `multimodal` or omit the explanation choice. Map Q8 to exactly one
of `multimodal`, `vllm`, or `agentic` — `agentic` already builds on the
`vllm` explanation layer, so never pass both as a pair. Explanation output is
supplemental and must not change the fused-alert decision.

**OpenMES (when Q6 says yes).** Set `{{OPENMES_ENABLED}}=yes` and pass the
user's details through verbatim: `{{OPENMES_BASE_URL}}`,
`{{OPENMES_TOKEN_FILE}}` (a path), `{{OPENMES_WORK_ORDER_ID}}`,
`{{OPENMES_ISSUE_TYPE_ID}}`, `{{OPENMES_SOURCE_ID}}`, and the optional
`{{OPENMES_BATCH_STEP_ID}}`. Infer the input silently from the route:

| Route | Publisher mode | What is reported |
|---|---|---|
| fused (`multimodal`/`vllm`/`agentic`) | `multimodal` | only confirmed fused defects (`fused_decision == 1`) from `{{FUSION_TOPIC}}`; never the camera-only or sensor-only topics |
| sensor only (`ts`) | `ts` | the MQTT sensor alert topic; needs MQTT alerting, not OPC-UA |
| camera only (`vision`) | `vision` | the vision metadata topic, filtered by defect labels and minimum confidence |

Any detail still missing stays an open question in the plan. Never use
placeholder IDs or URLs. The recipe's dummy OpenMES receiver is only for a
user who explicitly asks to test without a real OpenMES.

**Working directory:** carry Q7's approved path forward verbatim; never infer it.

### Step 4 — Propose the plan and WAIT for confirmation

Present a concise plan and **stop for approval**. Include:

- **Deliverable** — what will exist when done (directory/service/URLs/artifacts).
- **Routing source** — one line citing `references/SKILL_CATALOG.md` and the
  catalog row matched (for example "per SKILL_CATALOG.md, camera-only +
  full dashboard → `metro-ai-app-recipe`, not `manufacturing-app-recipe`
  vision demo or multimodal mode").
- **Primary + supporting skill(s)** and why each was chosen — explicitly state
  *why* this is vision-only, sensor-only, or fused (quote the business answer
  that drove it), since that routing decision is this skill's core value.
- **Inferred technology** — the concrete model/UDF-pattern/device/mode/topics
  you selected, shown as *decisions you made*, not questions.
- For a fused stack, state the Q8 after-alert choice and the single
  deployment mode it maps to; if that mode is `agentic`, note that the
  `vllm` explanation layer is included by default. For `vllm`/`agentic`,
  list what the user will see, matching the reference
  `industrial-edge-insights-multimodal` app: the base dashboard, the
  "... Explainability Dashboard" (`/insights-ui/`, **Explain** per result),
  and for `agentic` the "... - Agentic Dashboard" (`/agentic-ui/`, **Run
  Agentic Analysis**). Also list the models each needs and the hardware
  gate.
- **OpenMES** (only when requested): state that it is enabled, and what
  will be reported. For a fused stack that means **only confirmed fused
  defects** (camera and sensors agree, `fused_decision == 1`), as **one
  OpenMES Issue per confirmed defect**; camera-only or sensor-only alerts
  are never sent. Also give a volume warning: the camera runs at about 10
  fps, so one defective weld in view can create many Issues. List the
  OpenMES details received and those still needed (token by **file path
  only**). Note that the issue type must be non-blocking, and that OpenMES
  failures never stop inference or alerting.
- **Requirements/assumptions** — always list explicitly, from the
  delegate's `compatibility`: Docker + Docker Compose v2; Intel GPU/NPU
  device access and the host `video`/`render` group permissions (when a GPU is
  used); the exact ports that must be free (for example 80/443 or the Grafana
  port, the Coturn UDP port, OPC-UA port); and network/model-download access
  (outbound to Docker Hub, ghcr.io and Hugging Face for images, models and
  datasets, plus RTSP reachability for a camera). If the delegate is not yet
  installed locally, say its install step is deferred until approval.
- **Any skill that must be installed** with the exact `npx skills@1.7.4 add`
  command (only for delegates not already local — see
  [`DISCOVERY.md`](references/DISCOVERY.md); this includes
  `manufacturing-app-recipe` when it is missing).
- **Next action on approval** — close the plan with one explicit line naming
  what you will do the moment the user says `go`: *delegate to `<primary
  skill>` (then the supporting skills, in order) and verify the result
  against that delegate's own completion criteria*. State this as your
  committed next step even though you build nothing yet.

Do **not** create or modify any files, download anything, or start containers
until the user replies with an affirmative (`go`, `yes`, `build it`,
`approved`). If they change an answer — especially the "what feeds the
decision" answer, since it changes the primary skill entirely — re-plan and
re-confirm.

### Step 5 — Build by delegating

Only after confirmation:

1. Ensure the chosen skill(s) are available locally (see
   [`references/DISCOVERY.md`](references/DISCOVERY.md)); add any that
   aren't.
2. **Invoke the delegate skill**, passing the parameters you inferred in
   Step 3 **verbatim as the approved values** (checkout/output path, app
   name, ingestion transport, sensor fields and thresholds, alert channel,
   dashboard, test choice, `{{DEPLOYMENT}}`, OpenMES details) — for example a
   sensor-only app is `manufacturing-app-recipe` with `{{DEPLOYMENT}}=ts`
   and `production` sub-mode. Let it own the build — do not re-implement its work by hand.
   Chain supporting skills in dependency order (e.g.
   **`time-series-analytics-user` runs first** to author the UDF + TICKscript
   (e.g. a threshold rule on the approved field), and its output is then
   handed to `manufacturing-app-recipe` for the `ts`-mode `apps/<name>/`
   scaffold, packaging and deployment — never reimplement the delegate's work.
   The UDF pattern feeds into
   `manufacturing-app-recipe`'s `ts`-mode `apps/<name>/` scaffold, or its
   `multimodal`/`vllm`/`agentic`-mode sensor half; `dlsps-user` feeds the vision
   half).
3. Relay only the **business-relevant** progress to the user; keep the
   technical chatter to the delegate.

### Step 6 — Verify and hand back

Verify against the **delegate skill's own completion criteria** (each
delegate ships its own), citing real evidence rather than assuming success.
For a sensor path that means all of: the app is registered; ingestion is
healthy; sensor data is actually stored (rows present in the time-series
store); an actual alert is observed on the configured channel; the dashboard
shows the right data; and the generated tests pass (when requested). For
fused/vision stacks add the fused/vision topics and the UI endpoints. Then summarize for the user in business terms: what
was built, how to reach it (URLs/commands), and the immediate next action
(e.g. "open the Grafana dashboard", "check the fused-alert MQTT topic"). If a
step fails, report the failing delegate step and stop — do not loop.

If OpenMES was enabled, tell the user where the defect alerts can be seen:
- **dummy receiver** (only when the user asked to test without a real
  OpenMES): give the alerts page URL `http://<HOST_IP>:8099/`, say it is a
  read-only test page with dummy data and no login. Explain that the receiver
  and publisher run in separate foreground terminals; stop each with Ctrl-C;
- **real OpenMES**: say alerts appear as Issues on the configured work order,
  with the delivered count from the recipe's verification.

## Examples

See [`example-prompts/`](example-prompts/) for end-to-end walk-throughs:
- `01-sensor-only-anomaly.md` — pump vibration monitoring → `manufacturing-app-recipe` (`ts` mode).
- `02-vision-sensor-fusion.md` — weld defect detection → `manufacturing-app-recipe` (`multimodal` mode).
- `03-vision-only-inspection.md` — camera-only PCB defect detection → `metro-ai-app-recipe`.
- `04-ambiguous-modality.md` — vague "catch problems early" objective → clarify modality + route.

## Edge cases

- **User names a skill directly** → skip discovery; hand off to that skill.
- **Objective spans two skills** (e.g. bare UDF prototype now, full scaffolded
  app later) → sequence them in the plan and confirm the whole pipeline once.
- **Unclear correlation requirement** → route single-modality if the other
  signal is only context. Fused modes require both signals in one decision.
- **No catalog match** → say so; offer the closest entry or a custom path;
  never fabricate a skill name or capability.
- **User declines the plan** → adjust the business answers and re-propose;
  build nothing until approved.
- **Missing prerequisite** (no Docker, no GPU, no OPC-UA/MQTT source) →
  surface it in the plan (Step 4) and let the user decide, rather than
  failing mid-build.
- **OpenMES requested without its details** → plan it anyway, and list the
  missing details as open questions (base URL, token file path, work order
  ID, non-blocking issue type ID, station name). Never ask for or repeat
  the token value. Never fill in IDs or URLs yourself. Offer the recipe's
  dummy receiver only if the user wants to test without a real OpenMES.

## Notes

- The manufacturing-domain delegate (`manufacturing-app-recipe`, covering
  `vision`/`ts`/`multimodal`/`vllm`/`agentic` modes) may be absent when only
  this skill was installed — confirm and install it per
  [`DISCOVERY.md`](references/DISCOVERY.md) (folder-URL `npx skills@1.7.4 add`,
  never a clone) before delegating.
- `metro-ai-app-recipe`, `dlsps-user`, `dlstreamer-coding-agent`, and
  `time-series-analytics-user` live in **other** repos/suites, not under
  this suite's `.github/skills/` — do not assume they're present; always
  confirm per [`DISCOVERY.md`](references/DISCOVERY.md) and install on
  demand (Step 5) before delegating to one.
- Keep the catalog in
  [`references/SKILL_CATALOG.md`](references/SKILL_CATALOG.md) in sync with
  `manufacturing-app-recipe`'s own parameter table as it evolves.
