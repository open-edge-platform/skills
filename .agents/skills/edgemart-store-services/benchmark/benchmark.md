<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Skill Benchmark: edgemart-store-services

**Agents**: Copilot (`claude-sonnet-5.5`)  
**Grader**: Copilot (`claude-sonnet-5.5`)  
**Date**: 2026-11-04T08:58:15Z  
**Evals**: 1, 2, 3, 4, 5, 6 (1 run per configuration)

## Summary

> Skill lift = with skill − without skill. ↑ = better, ↓ = higher cost (expected).

### Evals passed

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 2 / 6 | 6 / 6 | **+4 ↑** |

### Pass rate (avg ± σ across evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 42% ±49% | 100% ±0% | **+58pp ↑** |

### Time (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 180 s | 196 s | +15 s ↓ |

### Tokens (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 0 | 0 | +0 ↓ |

## Per-Eval Detail

> Each cell is PASS/FAIL for that run, with the count of expectations met in parentheses (e.g. `PASS (5/5)`); `n/a` means no grading.json was found for that (eval, config, agent) combination.

| Eval | Prompt | Copilot (w/) | Copilot (w/o) |
|---|---|---|---|
| 1 | We have a real camera pipeline that detects people entering zones. How do I feed... | PASS (4/4) | FAIL (0/4) |
| 2 | POST /store-activity/ingest returns 409. Why? | PASS (2/2) | FAIL (1/2) |
| 3 | I need 30 days of table history to demo utilization charts. How do I preload it? | PASS (2/2) | FAIL (0/2) |
| 4 | My dashboard subscribes to the table occupancy SSE stream and misses events when... | PASS (3/3) | FAIL (0/3) |
| 5 | I'm benchmarking the store-activity service and want clean results with no MQTT ... | PASS (2/2) | PASS (2/2) |
| 6 | Add a new product category to the grocery POS frontend. | PASS (1/1) | PASS (1/1) |
| | **Mean ±σ** | **100% ±0%** | **42% ±49%** |