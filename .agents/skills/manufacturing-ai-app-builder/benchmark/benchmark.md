<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Skill Benchmark: manufacturing-ai-app-builder

**Agents**: Copilot (`claude-sonnet-5.5`)  
**Grader**: Copilot (`claude-sonnet-5.5`)  
**Date**: 2026-11-03T04:11:52Z  
**Evals**: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 (1 run per configuration)

## Summary

> Skill lift = with skill − without skill. ↑ = better, ↓ = higher cost (expected).

### Evals passed

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 3 / 12 | 12 / 12 | **+9 ↑** |

### Pass rate (avg ± σ across evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 55% ±34% | 100% ±0% | **+45pp ↑** |

### Time (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 234 s | 311 s | +77 s ↓ |

### Tokens (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 0 | 0 | +0 ↓ |

## Per-Eval Detail

> Each cell is PASS/FAIL for that run, with the count of expectations met in parentheses (e.g. `PASS (5/5)`); `n/a` means no grading.json was found for that (eval, config, agent) combination.

| Eval | Prompt | Copilot (w/) | Copilot (w/o) |
|---|---|---|---|
| 1 | I want to catch bearing wear before a pump fails using vibration readings, and I... | PASS (3/3) | FAIL (0/3) |
| 2 | For weld inspection, combine a camera and pressure sensor so we alert only when ... | PASS (7/7) | FAIL (2/7) |
| 3 | I need a camera-only demo that spots scratches on metal parts. No sensor data is... | PASS (3/3) | FAIL (2/3) |
| 4 | I want to catch problems early on our production line. What can you build? | PASS (4/4) | PASS (4/4) |
| 5 | Use the time-series-analytics-user skill directly to write a threshold UDF for m... | PASS (2/2) | PASS (2/2) |
| 6 | Detect scratches using only my factory RTSP camera and show annotated video, def... | PASS (7/7) | FAIL (2/7) |
| 7 | Our pump already sends vibration readings to a running analytics microservice. I... | PASS (4/4) | FAIL (1/4) |
| 8 | We have completed the business Q&A and I approved this plan: a sensor-only pump ... | PASS (7/7) | FAIL (4/7) |
| 9 | You proposed a sensor-only pump dashboard in /work/industrial-edge-insights-time... | PASS (4/4) | FAIL (3/4) |
| 10 | Completed business answers: my camera and temperature sensor must both flag a de... | PASS (7/7) | FAIL (2/7) |
| 11 | Track the same forklift across three factory cameras so it is counted once as it... | PASS (4/4) | FAIL (2/4) |
| 12 | Build a chatbot that answers HR questions from our employee-policy PDFs. It has ... | PASS (2/2) | PASS (2/2) |
| | **Mean ±σ** | **100% ±0%** | **55% ±34%** |