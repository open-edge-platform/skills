<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Skill Benchmark: edgemart-stack-deploy

**Agents**: Copilot (`claude-sonnet-5.5`)  
**Grader**: Copilot (`claude-sonnet-5.5`)  
**Date**: 2026-11-04T08:51:32Z  
**Evals**: 1, 2, 3, 4, 5, 6 (1 run per configuration)

## Summary

> Skill lift = with skill − without skill. ↑ = better, ↓ = higher cost (expected).

### Evals passed

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 5 / 6 | 6 / 6 | **+1 ↑** |

### Pass rate (avg ± σ across evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 94% ±13% | 100% ±0% | **+6pp ↑** |

### Time (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 286 s | 193 s | -93 s ↓ |

### Tokens (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 0 | 0 | +0 ↓ |

## Per-Eval Detail

> Each cell is PASS/FAIL for that run, with the count of expectations met in parentheses (e.g. `PASS (5/5)`); `n/a` means no grading.json was found for that (eval, config, agent) combination.

| Eval | Prompt | Copilot (w/) | Copilot (w/o) |
|---|---|---|---|
| 1 | I cloned qsr-store-pos-agent and ran docker compose up but it exits immediately ... | PASS (3/3) | PASS (3/3) |
| 2 | I edited backend/src/table-occupancy-service/index.js and ran docker compose up ... | PASS (3/3) | FAIL (2/3) |
| 3 | The Agent Chat tab says the gateway is disconnected, but the backend container i... | PASS (3/3) | PASS (3/3) |
| 4 | Our network needs a proxy. How do I build the images for the store event service... | PASS (2/2) | PASS (2/2) |
| 5 | I changed database/cafe/schema.sql but the running Postgres container doesn't ha... | PASS (3/3) | PASS (3/3) |
| 6 | How do I write a docker-compose file for a generic Node and Redis app? | PASS (1/1) | PASS (1/1) |
| | **Mean ±σ** | **100% ±0%** | **94% ±14%** |