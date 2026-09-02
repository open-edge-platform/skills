# Release Notes

## release-2026.2.0

### New Skills

- **physicalai-runtime-adding-a-camera-backend** — Adds or modifies a camera backend under `physicalai.capture`.
- **physicalai-runtime-adding-a-robot-integration** — Adds or modifies robot hardware integrations under `physicalai.robot`.
- **physicalai-runtime-configuring-inference-pipeline** — Configures preprocessors, postprocessors, and runners around `InferenceModel`.
- **physicalai-runtime-loading-exported-policies** — Loads and validates policies exported from Physical AI Studio for Runtime deployment.
- **physicalai-runtime-running-policy-on-robot** — Runs exported policies on hardware with `PolicyRuntime` and execution modes.
- **physicalai-train-adding-a-policy** — Adds or modifies a Physical AI Studio policy under `library/src/physicalai/policies`.
- **physicalai-train-benchmarking-a-policy** — Benchmarks a trained Physical AI Studio policy in a simulation gym.
- **physicalai-train-exporting-and-validating** — Exports and validates Physical AI Studio policies for Runtime deployment.
- **physicalai-train-training-a-policy** — Trains, validates, tests, and runs prediction for Physical AI Studio policies.
- **physicalai-train-working-with-datasets** — Works with Physical AI Studio datasets and Lightning datamodules.
- **multimodal-dataprep-user** — Deploy and consume Intel Multimodal DataPrep from prebuilt images or a repository checkout.
- **multimodal-embedding-serving-user** — Deploy and consume the Multimodal Embedding Serving microservice.

### Improved

- Index maintenance workflow now batches installs by `(repo, ref)` to avoid redundant clones.
- Path-scoped fallback retry added for skills nested beyond the CLI's default scan depth.
- `update_skills_index.py` now detects stale skills from disk, independent of `skills-lock.json`.
