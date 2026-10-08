# Competitive Skill Metrics

**Purpose.** Replace raw skill-count comparisons (e.g. vs [NVIDIA/skills](https://github.com/NVIDIA/skills)) with measures of **jobs covered**, **depth**, **granularity fitness**, **progressive disclosure**, and **outcome quality**.

Refresh with the `competitive-skill-metrics` skill (`scripts/refresh_scorecard.py`).

<!-- BEGIN GENERATED:SNAPSHOT -->
**Snapshot (2026-10-07).**

| Catalog | Products | Skills (raw) | Notes |
|---------|----------|--------------|-------|
| open-edge-platform/skills | 16 families / see README | **39** | Index in repo README; meta skill excluded |
| NVIDIA/skills | **50** | **~396** | Catalog README; top: TAO Toolkit ~76, DOCA ~60, Jetson BSP ~24 |

Raw count favors API/docs sharding. This document defines a shared **job taxonomy** and a **scorecard** so both catalogs are judged on the same unit of value: a user job.

Companion data: [`data/job-catalog.csv`](data/job-catalog.csv) · [`data/scorecard.json`](data/scorecard.json).
<!-- END GENERATED:SNAPSHOT -->

---

## 1. Headline scorecard (use these five)

<!-- BEGIN GENERATED:SCORECARD -->
| # | Metric | How to compute | OEP (this snapshot) | NVIDIA (same job set) | Why it beats count |
|---|--------|----------------|---------------------|------------------------|--------------------|
| 1 | **Jobs covered** | Jobs with ≥1 mapped skill / total jobs | **39 / 44 (88.6%)** | **28 / 44 (63.6%)** | Same denominator |
| 2 | **E2E jobs covered** | Jobs marked end-to-end with a full path | **30** | (see taxonomy; shards may stop at install/API) | “Can finish the outcome” |
| 3 | **Median skill depth** | Median `SKILL.md` words of mapped skills | **~702 words** | **~1592 words** (n=398) | Hard to fake with empty folders |
| 4 | **Granularity health** | Mean skills-per-job; target band 1–3 | **1.00** | **~1.96**; ≥3 on VIS-01, VIS-02, SPA-01, VSS-01, VSS-03, VSS-06, CVT-03, PAI-11 | Detects over-split |
| 5 | **Entry / routing coverage** | Domains with an orchestrator or clear progressive entry | `metro-ai-app-builder` | Mostly leaf catalog; few business-intent routers | Users need not know leaf names |

OEP depth floor (words ≥500 or refs >0): **76.9%**. NVIDIA depth floor: **100%**.

**Optional sixth (governance):** % of skills with evals + security scan + skill card / signature. NVIDIA markets this heavily; track it so the debate does not shift to “unverified.”
<!-- END GENERATED:SCORECARD -->

---

## 2. Scoring rubric

### 2.1 Job coverage

| Score | Criterion |
|-------|-----------|
| **Covered** | ≥1 skill can complete the job’s success criterion |
| **E2E** | Path reaches a running/verified artifact (deploy up, model exported, policy on robot, etc.), not only “how to call an API” |
| **Partial** | Skill helps but user must leave the skill path for a critical step |
| **Gap** | No skill maps |

**Catalog score:** `jobs_covered / jobs_in_taxonomy` and `e2e_jobs / jobs_in_taxonomy`.

Only compare on the **shared taxonomy** (this doc). Do not invent NVIDIA-only CUDA/DOCA jobs into the denominator when arguing OEP coverage, and do not hide OEP gaps in VSS alerts / RAG eval / sim-synth.

### 2.2 Depth (complexity proxy)

Per skill, compute:

| Signal | Weight | Pass heuristic |
|--------|--------|----------------|
| `SKILL.md` word count | medium | ≥500 preferred; &lt;300 + no refs = **thin** |
| On-demand files (`references/`, `scripts/`, `assets/`) | high | ≥1 deferred file = uses progressive disclosure payload |
| Decision branches (deploy variants, devices, modes) | high | ≥2 meaningful paths |
| Explicit failure / “do not use” | medium | present |
| Runnable verification steps | high | health checks, smoke commands, evals |

**Catalog aggregates:**

- Median / p90 word count  
- **Depth floor %** = skills with (words ≥500 **OR** refs &gt; 0)  
- **Thin %** = words &lt;400 **AND** refs = 0  

OEP snapshot: depth floor **~78%**; thin examples concentrated in some `getitune-*` and `physicalai-runtime-*` leaves.

### 2.3 Granularity fitness

For each job:

| skills_per_job | Interpretation | Action |
|----------------|----------------|--------|
| 0 | Gap | Add skill or accept out-of-scope |
| 1–2 | Fit (default) | Keep |
| 3–4 | Watch | Justify split (tools/audience/failure modes differ) or merge behind entry + refs |
| ≥5 | Likely over-split | Prefer one skill + deferred refs, or orchestrator → leaves |

For each skill:

| jobs_per_skill | Interpretation | Action |
|----------------|----------------|--------|
| 1 | Fit | Keep |
| 2–4 related | OK if progressive disclosure inside | Document load-when table |
| ≥5 unrelated | Monolith smell | Split by job boundary |

**Additional signals:**

- **Description overlap** — high embedding/Jaccard similarity between peer skills ⇒ redundant shards.  
- **Co-activation** — skills that routinely fire together in successful sessions ⇒ merge or make parent/child.  
- **Handoff tax** — extra turns spent selecting the next skill vs doing work.

**Split vs merge rule (normative):**

- **Split** when paths differ in tools, permissions, failure modes, or audience.  
- **Do not split** when paths only differ by parameter (model name, one API, install flavor). Prefer branches + `references/<variant>.md`.  
- **Orchestrate** when the user cannot know which leaf they need from the start (`metro-ai-app-builder` pattern).

### 2.4 Progressive disclosure / routing

| Metric | Good | Bad |
|--------|------|-----|
| Entry-skill ratio | Domain has a router or “start here” skill for non-experts | User must pick among N near-duplicate leaves |
| Deferred load ratio | Large tables/scripts in refs; body stays navigational | Entire API encyclopedia in always-loaded `SKILL.md` |
| Clarifying-question protocol | Asks business/context before tech | Demands skill name or framework up front |
| Wrong-skill rejection | Clear “do not use when” | Overlapping triggers, silent mis-route |
| Leaf reachability | Direct name **and** description match **and** orchestrator path | Leaf only reachable if user already knows the name |

Progressive disclosure is not an excuse for 40 peer shards of the same job.

### 2.5 Trigger quality (eval harness)

On a fixed prompt set (train/held-out):

| Metric | Definition |
|--------|------------|
| Precision@1 | Top selected skill is correct for the job |
| Recall | Correct skill is selected when it should be |
| Under-trigger / over-trigger rates | Missed useful skill vs spurious load |
| Turns-to-first-correct-skill | Discoverability |

### 2.6 Outcome quality (closing metric)

| Metric | Definition |
|--------|------------|
| Task success rate | Same agent harness, same scenarios, pack A vs B |
| Turns / time / token cost to success | Efficiency |
| Human interventions | Clarifications the skill should have asked or inferred |
| Artifact validity | Health checks pass, export loads, robot runs |
| Eval pass rate | Skills with automated evals that pass |

If leadership needs one number for a bakeoff, use **task success rate on the shared job taxonomy**, not skill count.

---

## 3. Job taxonomy

**Unit of value:** one user-intent job with one success criterion.  
**Audience:** customer-facing Edge AI outcomes (not internal contributor chores), except where contributor skills are already published (anomalib extend, physicalai add-policy).

Domains:

| Domain | Focus |
|--------|--------|
| orchestration | Business-intent → skill routing |
| vision-deploy / vision-build / vision-ops | Live CV apps, DL Streamer, pipeline server |
| spatial | Multi-camera scene understanding |
| vss | Video search & summarization |
| rag | ChatQnA / retrieval apps |
| multimodal | Embeddings + dataprep |
| models | Download / convert |
| timeseries | Time-series analytics microservice |
| cv-train | Geti / GetiTune training lifecycle |
| anomaly | Anomalib |
| pai-train / pai-runtime / pai-sim | Physical AI train, runtime, sim/synth |
| platform | Open Edge Platform installer CLI |
| uav | UAV mission compute SDK |

### 3.1 Full job list

Success criteria are intentionally short so evals can assert them.

| ID | Domain | Job | E2E? | OEP skill(s) | NVIDIA comparable (illustrative) | Fit note |
|----|--------|-----|------|--------------|----------------------------------|----------|
| ORCH-01 | orchestration | Turn a business objective into a working Intel Edge AI app without naming a skill | Y | metro-ai-app-builder | — | Entry / progressive disclosure exemplar |
| VIS-01 | vision-deploy | Stand up live CV analytics (cameras → annotated WebRTC + alerts) | Y | metro-ai-app-recipe | deepstream-generate-pipeline, deepstream-run-mv3dt, rtvi-cv-scaffold-vss-service | NV over-split risk |
| VIS-02 | vision-build | Build a custom vision pipeline app (Python/C/C++/gst-launch) | Y | dlstreamer-coding-agent | deepstream-dev, deepstream-generate-pipeline, deepstream-import-vision-model | OEP consolidates; NV shards |
| VIS-03 | vision-ops | Deploy & operate pipeline server via REST | Y | dlsps-user | deepstream-sop, rtvi-cv-scaffold-vss-service | Fit |
| VIS-04 | vision-ops | Profile / tune vision pipeline performance | N | — | deepstream-profile-pipeline | **OEP gap** |
| SPA-01 | spatial | Deploy multi-camera SceneScape from streams → tracking verified | Y | scenescape-setup | amc-setup-calibration-stack, amc-run-video-calibration, deepstream-run-mv3dt | OEP one deep skill |
| VSS-01 | vss | Deploy VSS locally (Compose, modes, health) | Y | vss-deploy | vss-deploy-profile, vss-deploy-dense-captioning, vss-deploy-video-embedding, vss-deploy-detection-tracking-2d/3d | NV profile shards |
| VSS-02 | vss | Deploy VSS on Kubernetes (Helm) | Y | vss-deploy-helm | vss-deploy-profile | Fit (variant split OK: Compose vs Helm) |
| VSS-03 | vss | Summarize a video via Pipeline Manager | Y | vss-summarize-video | vss-summarize-video, vss-ask-video, vss-generate-video-report | Watch NV adjacent shards |
| VSS-04 | vss | Search a video library with natural language | Y | vss-search-index | vss-search-archive | Fit |
| VSS-05 | vss | Manage alerts / incidents | N | — | vss-manage-alerts | **OEP gap** |
| VSS-06 | vss | Query analytics / sensors / behavior APIs | N | — | vss-query-analytics, vss-setup-video-analytics-api, vss-setup-behavior-analytics | **OEP gap**; NV fragmented |
| RAG-01 | rag | Deploy ChatQnA / RAG (Docker) | Y | chatqna-docker-deploy | rag-blueprint, nemo-retriever | Fit; aiq-deploy removed upstream |
| RAG-02 | rag | Deploy ChatQnA / RAG (Helm) | Y | chatqna-helm-deploy | rag-blueprint | Variant split OK |
| RAG-03 | rag | Evaluate RAG quality / performance | N | — | rag-eval, rag-perf | **OEP gap** |
| MM-01 | multimodal | Deploy multimodal embedding serving | Y | multimodal-embedding-serving-user | vss-deploy-video-embedding (partial) | Fit |
| MM-02 | multimodal | Ingest media into vector/media store | Y | multimodal-dataprep-user | vss-manage-video-io-storage (partial) | Fit |
| MOD-01 | models | Download & convert models for edge (OVMS/OpenVINO) | Y | model-download-user | deepstream-import-vision-model, tao-run-inference-service | Fit |
| TS-01 | timeseries | Build time-series analytics use case on microservice | Y | time-series-analytics-user | — | OEP-only on this taxonomy |
| CVT-01 | cv-train | Discover GetiTune models / recipes | N | getitune-discovering-models | tao-list-capabilities | Lifecycle leaf; thin risk |
| CVT-02 | cv-train | Prepare CV training dataset | N | getitune-preparing-datasets | tao-convert-dataset-format, tao-validate-dataset-format | Fit |
| CVT-03 | cv-train | Train / fine-tune CV model | Y | getitune-training-a-model | tao-train-single-step, tao-finetune-huggingface-model, tao-run-automl | NV model-sharding elsewhere |
| CVT-04 | cv-train | Export model (OpenVINO IR / ONNX) | Y | getitune-exporting-a-model | (partial via TAO export/infer paths) | Fit |
| CVT-05 | cv-train | Quantize / optimize exported model | Y | getitune-optimizing-a-model | — | OEP strength |
| CVT-06 | cv-train | Run inference / evaluate | Y | getitune-running-inference | tao-run-inference-service | Thin risk |
| CVT-07 | cv-train | Geti app E2E (project → annotate → train → deploy) | Y | geti-using-the-pipeline | — | OEP-only |
| ANM-01 | anomaly | Train anomalib model | Y | anomalib-training | physical-ai-defect-image-generation (adjacent) | Fit; paidf-anomalygen removed upstream |
| ANM-02 | anomaly | Add anomalib model architecture | N | anomalib-adding-a-model | — | Contributor job |
| ANM-03 | anomaly | Add anomalib datamodule | N | anomalib-adding-a-datamodule | — | Contributor job |
| ANM-04 | anomaly | Benchmark anomalib grid | Y | anomalib-benchmarking | — | Fit |
| ANM-05 | anomaly | Tiled ensemble high-res detection | Y | anomalib-tiled-ensemble | — | Fit |
| PAI-01 | pai-train | Prepare policy datasets (LeRobot) | N | physicalai-train-working-with-datasets | i4h-workflow-dataset-* | Fit |
| PAI-02 | pai-train | Train robot policy | Y | physicalai-train-training-a-policy | i4h-workflow-finetune, i4h-workflow | Fit |
| PAI-03 | pai-train | Add new policy family | N | physicalai-train-adding-a-policy | — | Contributor job |
| PAI-04 | pai-train | Benchmark policy in sim | Y | physicalai-train-benchmarking-a-policy | i4h-workflow-validate | Fit |
| PAI-05 | pai-train | Export & validate policy for runtime | Y | physicalai-train-exporting-and-validating | i4h-workflow-e2e | Fit |
| PAI-06 | pai-runtime | Load exported policy in runtime | Y | physicalai-runtime-loading-exported-policies | — | Fit; thin risk |
| PAI-07 | pai-runtime | Configure inference pre/post pipeline | N | physicalai-runtime-configuring-inference-pipeline | — | Thin risk |
| PAI-08 | pai-runtime | Run policy on robot hardware | Y | physicalai-runtime-running-policy-on-robot | i4h-catheter-navigation, i4h-workflow-e2e | Thin risk |
| PAI-09 | pai-runtime | Add camera backend | N | physicalai-runtime-adding-a-camera-backend | — | Contributor; thin |
| PAI-10 | pai-runtime | Add robot integration | N | physicalai-runtime-adding-a-robot-integration | — | Contributor; thin |
| PAI-11 | pai-sim | CAD→sim, neural recon, synthetic/augment/auto-label | N | — | omniverse-*, physical-ai-*, paidf-* | **NVIDIA-only on taxonomy** |
| CLI-01 | platform | Install / manage OEP components and profiles via openedge-cli | Y | openedge-cli | — | OEP-only |
| UAV-01 | uav | Operate UAV Mission Compute SDK (PX4 telemetry, cameras, missions, edge AI demos) | Y | uav-mission-compute-sdk | — | OEP-only |

Machine-readable copy: [`data/job-catalog.csv`](data/job-catalog.csv).

### 3.2 Snapshot aggregates

<!-- BEGIN GENERATED:AGGREGATES -->
| Measure | OEP | NVIDIA (on this taxonomy) |
|---------|-----|---------------------------|
| Jobs covered | 39 / 44 | 28 / 44 |
| OEP-only jobs | 16 | — |
| NVIDIA-only jobs | — | 5 (VIS-04, VSS-05, VSS-06, RAG-03, PAI-11) |
| Overlap jobs | 23 | 23 |
| Mean skills / covered job | **1.00** | **~1.96** |
| Jobs with NVIDIA skills/job ≥ 3 | — | VIS-01, VIS-02, SPA-01, VSS-01, VSS-03, VSS-06, CVT-03, PAI-11 |
| OEP skills mapped | 39 / 39 | — |
| OEP jobs/skill > 1 | 0 (none) | — |

**Reading:** Compare on jobs and skills-per-job. NVIDIA raw skill count is dominated by products outside this taxonomy (DOCA, Jetson BSP, NeMo MBridge, per-model TAO trains).
<!-- END GENERATED:AGGREGATES -->

---

## 4. How to present this to management

**Do not lead with:** “We have 39, they have ~396.”

**Lead with:**

1. **Jobs covered on a shared taxonomy** (88.6% vs 63.6% on this snapshot).  
2. **Skills per job** (1.0 vs ~1.96; several NVIDIA jobs at 3–5 shards).  
3. **Median depth / depth-floor %** (OEP ~702 words / 76.9% vs NVIDIA ~1592 / 100%; close the depth gap on thin skills).  
4. **Entry skill** — business users hit `metro-ai-app-builder` instead of browsing ~396 names.  
5. **Bakeoff plan** — task success on ORCH/VIS/VSS/RAG/CVT/PAI subset.

**Acknowledge gaps (builds credibility):** VIS-04 profiling, VSS alerts/analytics APIs, RAG eval/perf, Physical AI sim/synth (PAI-11). Decide expand vs out-of-scope.

**Acknowledge internal hygiene:** thin `getitune-*` / `physicalai-runtime-*` leaves — candidates to deepen with refs **or** merge into lifecycle entry skills with progressive disclosure (not to multiply further for count parity).

---

## 5. Operating process

### 5.1 Quarterly scorecard

1. Freeze taxonomy version (`job-catalog.csv` + date).  
2. Remap OEP + NVIDIA skills (1–2 days).  
3. Recompute coverage, skills/job, depth floor, thin %.  
4. Run trigger eval + a **12–20 job** outcome bakeoff if budget allows.  
5. Publish one-pager: five headline metrics + gap list + merge/split recommendations.

### 5.2 Skill PR checklist (granularity gate)

Before merging a new skill, require answers:

1. Which **job ID(s)** does this cover?  
2. Is there already a skill for that job? If yes, why not extend + `references/`?  
3. Can a non-expert reach this via description or orchestrator without knowing the name?  
4. Depth floor: ≥500 words **or** deferred refs **or** evals?  
5. Clear “do not use when” vs neighbors?

Reject PRs whose only justification is “parity with NVIDIA skill count.”

### 5.3 Merge / split review triggers

| Trigger | Review |
|---------|--------|
| New leaf with high description overlap to existing | Merge or parent/child |
| Two skills co-activated &gt;50% in eval traces | Merge or orchestrate |
| One skill maps to ≥5 unrelated jobs | Split |
| Install-only variants (wheel/conda/apt) as separate top-level skills | Prefer one skill + variant refs (Holoscan-style anti-pattern) |
| One skill per model/API symbol | Prefer discover + parameterized workflow (TAO/DOCA anti-pattern) |

---

## 6. Suggested bakeoff suite (minimal)

Run the same agent + prompts against OEP pack vs NVIDIA pack where products overlap:

| Job ID | Prompt gist | Success check |
|--------|-------------|-----------------|
| ORCH-01 | “I want to detect people on my factory cameras on Intel hardware” | Plan + correct delegate skill(s); no framework quiz |
| VIS-01 / VIS-02 | “Build/deploy a detection pipeline on my RTSP streams” | Running pipeline or compose; correct stack |
| VSS-01 + VSS-03 | “Deploy VSS and summarize this video” | Healthy deploy + summary text |
| RAG-01 | “Deploy ChatQnA over my PDFs on CPU” | Stack healthy; answer grounded |
| CVT-03 + CVT-04 | “Train then export OpenVINO for my detection dataset” | Checkpoint + IR/ONNX |
| PAI-02 + PAI-05 | “Train and export a policy for runtime” | Export validates |

Record: success, turns, interventions, whether the **correct** skill(s) fired.

---

## 7. Maintenance

| Artifact | Owner | Update when |
|----------|-------|-------------|
| This doc | Skills PM / architect | Taxonomy or rubric changes |
| `data/job-catalog.csv` | Same | Skill add/remove/rename; quarterly NVIDIA remap |
| `data/scorecard.json` | `refresh_scorecard.py` | Every metrics refresh |
| Depth stats | Script / CI optional | On index sync or competitive review |
| Bakeoff results | Eng | Each competitive review |

Use the **`competitive-skill-metrics`** skill to refresh inventories and patch generated sections. NVIDIA skill lists drift daily via their sync pipeline; always date-stamp remaps.

### Drift report (auto)

<!-- BEGIN GENERATED:DRIFT -->
_Generated 2026-10-07T18:25:57Z_.

- **Unmapped OEP skills** (0): none
- **Stale OEP refs in CSV** (0): none
- **Stale / unresolved NVIDIA refs** (0): none
- **OEP thin skills** (words <400 and no refs): `getitune-discovering-models`, `getitune-running-inference`, `openedge-cli`, `physicalai-runtime-adding-a-camera-backend`, `physicalai-runtime-configuring-inference-pipeline`, `physicalai-runtime-running-policy-on-robot`
- **Unmapped NVIDIA overlap-product skills** (sample, review for remap): `amc-run-rtsp-calibration`, `amc-run-sample-calibration`, `i4h-lerobot-viz`, `i4h-workflow-create`, `i4h-workflow-dataset-annotate`, `i4h-workflow-dataset-mimic`, `i4h-workflow-dataset-replay`, `i4h-workflow-scene-edit`, `i4h-workflow-setup`, `i4h-workflow-train-rl`, `nemo-retriever-mcp`, `omniverse-realtime-viewer`, `omniverse-usd-performance-tuning`, `paidf-cosmos-predict`, `paidf-orchestration-setup` … +25 more
<!-- END GENERATED:DRIFT -->

---

## 8. One-paragraph thesis

**Skill count measures packaging choices, not capability.** NVIDIA’s catalog count is inflated by API-, model-, and install-variant shards; OEP packs more work per skill and routes non-experts through progressive disclosure. Compete on **jobs covered**, **skills per job**, **depth**, **routing quality**, and **task success** — and use the job taxonomy as the shared denominator whenever count-for-count appears in a slide.
