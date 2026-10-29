# Video search — find moments in an archive → vss

**User (business objective):**
> I have hundreds of recorded videos and want to type "forklift near a person"
> and jump to the matching clips.

**Orchestrator (Step 1 — business Q&A):**
1. Outcome — natural-language search that returns ranked clips? [yes]
2. Inputs — a folder/library of MP4s to index? [yes, provide path]
3. Also want auto-summaries of videos, or search only? [search only]
4. Deployment — Docker or Kubernetes? [Docker]
5. Hardware — Intel GPU (default), Intel CPU/NPU, or vLLM available? [Intel GPU]

**Discovery (Step 2):** verb *search* + object *video library* → primary
**`vss-deploy`** (search mode), supporting **`multimodal-dataprep-user`**
(media preparation) and **`vss-search-index`** (query). k8s → `vss-deploy-helm`. Add
`vss-summarize-video` only if summaries were requested.

**Plan (Step 4 — awaits confirmation):**
- Deliverable: VSS app in **search** mode via Docker Compose; the library
  ingested and indexed; a working natural-language query returning ranked clips.
- Skills (sequence): `multimodal-dataprep-user` (prepare media) →
  `multimodal-embedding-serving-user` (embeddings) → `vss-deploy` (`--search`) →
  `vss-search-index` (query).
- Inferred technology: OpenVINO GPU, multimodal embeddings, VDMS vector DB.
- Install after approval:
  - `npx skills@1.5.23 add https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/visual-data-preparation-for-retrieval/multimodal-dataprep/.github/skills/multimodal-dataprep-user`
  - `npx skills@1.5.23 add https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/multimodal-embedding-serving/.github/skills/multimodal-embedding-serving-user`
  - `npx skills@1.5.23 add https://github.com/open-edge-platform/edge-ai-libraries/tree/main/sample-applications/video-search-and-summarization/.github/skills/vss-deploy`
  - `npx skills@1.5.23 add https://github.com/open-edge-platform/edge-ai-libraries/tree/main/sample-applications/video-search-and-summarization/.github/skills/vss-search-index`
- Requirements: Docker + Compose v2; disk for the video library + vectors.

**Build (Step 5, after approval):** prepare the media with
`multimodal-dataprep-user`, deploy embeddings with
`multimodal-embedding-serving-user`, bring up the app with
`vss-deploy --search`, run a sample query with `vss-search-index`, then hand the
user the search UI/endpoint.
