# Competitive Skill Metrics

**Purpose.** Replace raw skill-count comparisons (vs [NVIDIA/skills](https://github.com/NVIDIA/skills), [amd/skills](https://github.com/amd/skills), [qualcomm/skills](https://github.com/qualcomm/skills)) with measures of **jobs covered**, **depth**, **granularity fitness**, **progressive disclosure**, and **outcome quality**.

Refresh with the `competitive-skill-metrics` skill (`.agents/skills/competitive-skill-metrics/scripts/refresh_scorecard.py`).

<!-- BEGIN GENERATED:SNAPSHOT -->
**Snapshot (2026-10-16).**

| Catalog | Products | Skills (raw) | Notes |
|---------|----------|--------------|-------|
| open-edge-platform/skills | 16 families / see README | **39** | Index in repo README; meta skill excluded |
| [NVIDIA/skills](https://github.com/NVIDIA/skills) | **48** | **~387** | Catalog README; top: TAO Toolkit ~76, DOCA ~60, Jetson BSP ~24 |
| [amd/skills](https://github.com/amd/skills) | **3** | **11** | published=11; planned_excluded=hrr-replay-analysis |
| [qualcomm/skills](https://github.com/qualcomm/skills) | **1** | **8** | logical=2; version_shards≈7 |

Raw count favors API/docs/board sharding. This document defines a shared **job taxonomy** and a **scorecard** so catalogs are judged on the same unit of value: a user job.

Companion data: [`data/job-catalog.csv`](data/job-catalog.csv) · [`data/scorecard.json`](data/scorecard.json).
<!-- END GENERATED:SNAPSHOT -->

---

## 1. Headline scorecard (use these five)

<!-- BEGIN GENERATED:SCORECARD -->
| # | Metric | OEP | NVIDIA | AMD | Qualcomm |
|---|--------|-----|--------|-----|----------|
| 1 | **Jobs covered** | **39 / 50 (78%)** | **28 / 50 (56%)** | **4 / 50 (8%)** | **2 / 50 (4%)** |
| 2 | **E2E jobs (OEP)** | **30** | — | — | — |
| 3 | **Median skill depth** | **~712 words** | n/a — `--clone-nvidia-depth` | n/a — `--clone-amd-depth` | n/a — `--clone-qualcomm-depth` |
| 4 | **Mean skills / covered job** | **1.00** | **~1.96** (≥3: VIS-01, VIS-02, SPA-01, VSS-01, VSS-03, VSS-06, CVT-03, PAI-11) | **~2.75** (≥3: AMD-01, AMD-02, AMD-04) | **~4.00** (≥3: QC-01) |
| 5 | **Entry / routing** | `metro-ai-app-builder` | leaf catalog | leaf catalog | board-variant shards |

OEP depth floor (words ≥500 or refs >0): **76.9%**. NVIDIA: **n/a**. AMD: **n/a**. Qualcomm: **n/a**.

**Reading:** AMD/Qualcomm currently cover different product surfaces (LLM/ROCm serve; QLI board bring-up) than OEP’s Edge CV/VSS/RAG taxonomy — low jobs-covered % is expected until they publish overlapping Edge AI jobs. Do not inflate OEP coverage by shrinking the shared denominator.

**Optional sixth (governance):** % of skills with evals + security scan + skill card / signature.
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

Compare on the **shared taxonomy** (this doc). Competitor-only rows (AMD LLM/ROCm, Qualcomm Linux board bring-up, NVIDIA PAI-11 sim/synth) stay in the denominator so gaps stay visible — do not shrink the job set to inflate OEP %. Do not invent CUDA/DOCA-only vanity jobs either.

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
| llm-serve / llm-local / llm-quantize / amd-gpu-ops | AMD Instinct/EPYC LLM serve, Lemonade local AI, Quark PTQ, ROCm ops (competitor surface) |
| qcom-linux | Qualcomm Linux / Dragonwing board bring-up (competitor surface) |

### 3.1 Full job list

Success criteria are intentionally short so evals can assert them.

| ID | Domain | Job | E2E? | OEP | NVIDIA | AMD | Qualcomm | Fit note |
|----|--------|-----|------|-----|--------|-----|----------|----------|
| ORCH-01 | orchestration | Turn a business objective into a working Intel Edge AI app without naming a skill | Y | metro-ai-app-builder | — | — | — | Entry / progressive disclosure exemplar |
| VIS-01 | vision-deploy | Stand up live CV analytics (cameras → annotated WebRTC + alerts) | Y | metro-ai-app-recipe | deepstream-*, rtvi-cv-* | — | — | NV over-split risk |
| VIS-02 | vision-build | Build a custom vision pipeline app (Python/C/C++/gst-launch) | Y | dlstreamer-coding-agent | deepstream-dev, deepstream-generate-pipeline, … | — | — | OEP consolidates; NV shards |
| VIS-03 | vision-ops | Deploy & operate pipeline server via REST | Y | dlsps-user | deepstream-sop, rtvi-cv-* | — | — | Fit |
| VIS-04 | vision-ops | Profile / tune vision pipeline performance | N | — | deepstream-profile-pipeline | — | — | **OEP gap** |
| SPA-01 | spatial | Deploy multi-camera SceneScape from streams → tracking verified | Y | scenescape-setup | amc-*, deepstream-run-mv3dt | — | — | OEP one deep skill |
| VSS-01–06 | vss | Deploy / summarize / search / alerts / analytics | Y/N | vss-* | vss-* | — | — | See CSV; several **OEP gaps** |
| RAG-01–03 | rag | Deploy ChatQnA (Compose/Helm) / RAG eval | Y/N | chatqna-* | rag-blueprint, nemo-retriever, rag-eval | — | — | RAG-03 **OEP gap** |
| MM-01–02 | multimodal | Embedding serving / media ingest | Y | multimodal-* | vss-* (partial) | — | — | Fit |
| MOD-01 | models | Download & convert models for edge (OVMS/OpenVINO) | Y | model-download-user | deepstream-import-*, tao-run-inference-service | — | — | Fit |
| TS-01 | timeseries | Build time-series analytics use case | Y | time-series-analytics-user | — | — | — | OEP-only |
| CVT-01–07 | cv-train | GetiTune / Geti lifecycle | Y/N | getitune-*, geti-* | tao-* | — | — | See CSV; thin risk on some leaves |
| ANM-01–05 | anomaly | Anomalib train / extend / benchmark / tiled | Y/N | anomalib-* | physical-ai-defect-* (adjacent) | — | — | Fit |
| PAI-01–11 | pai-* | Physical AI train / runtime / sim | Y/N | physicalai-* | i4h-*, omniverse-*, paidf-* | — | — | PAI-11 **NVIDIA-only** |
| CLI-01 | platform | Install / manage OEP via openedge-cli | Y | openedge-cli | — | — | — | OEP-only |
| UAV-01 | uav | Operate UAV Mission Compute SDK | Y | uav-mission-compute-sdk | — | — | — | OEP-only |
| AMD-01 | llm-serve | Serve LLMs on Instinct GPU or EPYC CPU | Y | — | — | serving-llms-on-*; hyperloom-* | — | **AMD-only** |
| AMD-02 | llm-local | Local AI routing / cloud+local integration | Y | — | — | local-ai-*; lemonade-router-builder | — | **AMD-only** (Lemonade) |
| AMD-03 | llm-quantize | Quark install + LLM PTQ | Y | — | — | quark-* | — | **AMD-only**; adjacent to CVT-05 stack-wise |
| AMD-04 | amd-gpu-ops | ROCm diagnose + kernel/trace eval | N | — | — | rocm-doctor; magpie-*; tracelens-* | — | **AMD-only** |
| QC-01 | qcom-linux | Configure Ethernet on Qualcomm Linux / Dragonwing | Y | — | — | — | configure-ethernet* | **QC-only**; board-variant over-split |
| QC-02 | qcom-linux | Configure AMC6821 fan controller | Y | — | — | — | configure-fan-controller | **QC-only** |

Full skill lists and wildcards: [`data/job-catalog.csv`](data/job-catalog.csv).

### 3.2 Snapshot aggregates

<!-- BEGIN GENERATED:AGGREGATES -->
| Measure | OEP | NVIDIA | AMD | Qualcomm |
|---------|-----|--------|-----|----------|
| Jobs covered | 39 / 50 | 28 / 50 | 4 / 50 | 2 / 50 |
| Vendor-only jobs (no OEP map) | — | 5 (VIS-04, VSS-05, VSS-06, RAG-03, PAI-11) | 4 (AMD-01, AMD-02, AMD-03, AMD-04) | 2 (QC-01, QC-02) |
| OEP∩NVIDIA overlap jobs | 23 | 23 | — | — |
| Mean skills / covered job | **1.00** | **~1.96** | **~2.75** | **~4.00** |
| Jobs with skills/job ≥ 3 | — | VIS-01, VIS-02, SPA-01, VSS-01, VSS-03, VSS-06, CVT-03, PAI-11 | AMD-01, AMD-02, AMD-04 | QC-01 |
| OEP skills mapped | 39 / 39 | — | — | — |

**Reading:** Compare on jobs and skills-per-job. NVIDIA raw count is dominated by products outside Edge AI overlap (DOCA, Jetson BSP, TAO model shards). AMD is LLM/ROCm-centric. Qualcomm IOT skills are early and board-variant heavy.
<!-- END GENERATED:AGGREGATES -->

---

## 4. How to present this to management

**Do not lead with:** “We have 39, NVIDIA ~387, AMD 11, Qualcomm 8.”

**Lead with:**

1. **Jobs covered on a shared taxonomy** (this snapshot: OEP 78% vs NVIDIA 56% vs AMD 8% vs Qualcomm 4% — AMD/QC low % reflects different product surfaces, not OEP theater).  
2. **Skills per job** (OEP 1.0 vs NVIDIA ~1.96 vs AMD ~2.75 vs Qualcomm ~4.0 on QC-01 board shards).  
3. **Median depth / depth-floor %** — close OEP thin-skill gap; clone vendor repos for peer depth when presenting.  
4. **Entry skill** — `metro-ai-app-builder` vs leaf catalogs (NVIDIA) / board shards (Qualcomm).  
5. **Bakeoff plan** — task success on ORCH/VIS/VSS/RAG/CVT/PAI subset where NVIDIA overlaps; treat AMD LLM and QC Linux as adjacent markets unless leadership expands scope.

**Acknowledge gaps (builds credibility):** VIS-04 profiling, VSS alerts/analytics APIs, RAG eval/perf, Physical AI sim/synth (PAI-11). AMD LLM serve / Quark / Lemonade and Qualcomm Linux bring-up are **competitor-only** today — decide expand vs out-of-scope.

**Acknowledge internal hygiene:** thin `getitune-*` / `physicalai-runtime-*` leaves — deepen with refs **or** merge into lifecycle entry skills (not more shards for count parity). Qualcomm’s per-board Ethernet skills are the anti-pattern to avoid.

---

## 5. Operating process

### 5.1 Quarterly scorecard

1. Freeze taxonomy version (`job-catalog.csv` + date).  
2. Remap OEP + NVIDIA + AMD + Qualcomm skills (1–2 days).  
3. Recompute coverage, skills/job, depth floor, thin %.  
4. Run trigger eval + a **12–20 job** outcome bakeoff if budget allows.  
5. Publish one-pager: five headline metrics + multi-vendor gap list + merge/split recommendations.

### 5.2 Skill PR checklist (granularity gate)

Before merging a new skill, require answers:

1. Which **job ID(s)** does this cover?  
2. Is there already a skill for that job? If yes, why not extend + `references/`?  
3. Can a non-expert reach this via description or orchestrator without knowing the name?  
4. Depth floor: ≥500 words **or** deferred refs **or** evals?  
5. Clear “do not use when” vs neighbors?

Reject PRs whose only justification is “parity with NVIDIA / AMD / Qualcomm skill count.”

### 5.3 Merge / split review triggers

| Trigger | Review |
|---------|--------|
| New leaf with high description overlap to existing | Merge or parent/child |
| Two skills co-activated &gt;50% in eval traces | Merge or orchestrate |
| One skill maps to ≥5 unrelated jobs | Split |
| Install-only variants (wheel/conda/apt) as separate top-level skills | Prefer one skill + variant refs (Holoscan-style anti-pattern) |
| One skill per model/API symbol | Prefer discover + parameterized workflow (TAO/DOCA anti-pattern) |
| One skill per board/devkit for the same procedure | Prefer one skill + device refs (Qualcomm Ethernet anti-pattern) |

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
| `data/job-catalog.csv` | Same | Skill add/remove/rename; quarterly NVIDIA/AMD/Qualcomm remap |
| `data/scorecard.json` | `refresh_scorecard.py` | Every metrics refresh |
| `data/*-skills-*.cache.*` | Script | Auto-refreshed on live fetch |
| Depth stats | Script / CI optional | On index sync or competitive review |
| Bakeoff results | Eng | Each competitive review |

Use the **`competitive-skill-metrics`** skill to refresh inventories and patch generated sections. Vendor catalogs drift (NVIDIA sync pipeline; AMD federation; Qualcomm IOT skills.json); always date-stamp remaps.

### Drift report (auto)

<!-- BEGIN GENERATED:DRIFT -->
_Generated 2026-10-16T01:04:38Z_.

- **Unmapped OEP skills** (0): none
- **Stale OEP refs in CSV** (0): none
- **Stale / unresolved NVIDIA refs** (0): none
- **Stale / unresolved AMD refs** (0): none
- **Stale / unresolved Qualcomm refs** (0): none
- **OEP thin skills** (words <400 and no refs): `getitune-discovering-models`, `getitune-running-inference`, `openedge-cli`, `physicalai-runtime-adding-a-camera-backend`, `physicalai-runtime-configuring-inference-pipeline`, `physicalai-runtime-running-policy-on-robot`
- **Unmapped NVIDIA overlap-product skills** (sample): `amc-run-rtsp-calibration`, `amc-run-sample-calibration`, `i4h-lerobot-viz`, `i4h-workflow-create`, `i4h-workflow-dataset-annotate`, `i4h-workflow-dataset-mimic`, `i4h-workflow-dataset-replay`, `i4h-workflow-scene-edit`, `i4h-workflow-setup`, `i4h-workflow-train-rl`, `nemo-retriever-mcp`, `omniverse-realtime-viewer` … +28 more
- **Unmapped AMD skills** (0): none
- **Unmapped Qualcomm logical skills** (0): none
<!-- END GENERATED:DRIFT -->

---

## 8. One-paragraph thesis

**Skill count measures packaging choices, not capability.** NVIDIA’s catalog is inflated by API/model/install shards; Qualcomm’s early catalog shards one Ethernet job across board variants; AMD’s smaller catalog is deep on LLM/ROCm but barely overlaps Edge CV. OEP packs more work per skill on the shared Edge AI taxonomy and routes non-experts through progressive disclosure. Compete on **jobs covered**, **skills per job**, **depth**, **routing quality**, and **task success** — never raw folder count.
