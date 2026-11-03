<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Skill Benchmark: manufacturing-app-recipe

**Agents**: Copilot (`claude-sonnet-5.5`)  
**Grader**: Copilot (`claude-sonnet-5.5`)  
**Date**: 2026-11-03T05:35:11Z  
**Evals**: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 (1 run per configuration)

## Summary

> Skill lift = with skill − without skill. ↑ = better, ↓ = higher cost (expected).

### Evals passed

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 2 / 19 | 19 / 19 | **+17 ↑** |

### Pass rate (avg ± σ across evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 44% ±31% | 100% ±0% | **+56pp ↑** |

### Time (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 538 s | 776 s | +238 s ↓ |

### Tokens (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 0 | 0 | +0 ↓ |

## Per-Eval Detail

> Each cell is PASS/FAIL for that run, with the count of expectations met in parentheses (e.g. `PASS (5/5)`); `n/a` means no grading.json was found for that (eval, config, agent) combination.

| Eval | Prompt | Copilot (w/) | Copilot (w/o) |
|---|---|---|---|
| 1 | Show the proposed files and deployment procedure for a ts production app named p... | PASS (10/10) | FAIL (6/10) |
| 2 | Build a ts production app called gearbox-health in my existing time-series stack... | PASS (4/4) | PASS (4/4) |
| 3 | Describe the proposed multimodal stack in /work/stacks/weld-quality-stack. Assum... | PASS (8/8) | FAIL (1/8) |
| 4 | Show the configuration and deployment design for a vllm-mode stack at /work/stac... | PASS (8/8) | FAIL (1/8) |
| 5 | Show the proposed agentic deployment at /work/stacks/part-quality-stack for a ca... | PASS (7/7) | FAIL (0/7) |
| 6 | Explain the vision-mode DL Streamer/GStreamer demo sub-path for classifying scra... | PASS (4/4) | FAIL (3/4) |
| 7 | Set up Prometheus and OpenTelemetry with Grafana dashboards for request latency ... | PASS (2/2) | PASS (2/2) |
| 8 | My ts app pump-pressure is already scaffolded and registered in an existing time... | PASS (5/5) | FAIL (2/5) |
| 9 | Describe the complete multimodal deployment design for CNC inspection at /work/s... | PASS (10/10) | FAIL (1/10) |
| 10 | Review these proposed multimodal production settings before deployment: FUSION_M... | PASS (6/6) | FAIL (4/6) |
| 11 | Explain the recipe's fusion result for these cases, without running code or serv... | PASS (5/5) | FAIL (2/5) |
| 12 | My ts app pump-vibration-monitor uses the shared bundled MQTT publisher without ... | PASS (5/5) | FAIL (1/5) |
| 13 | For a ts production pump app, I want Telegraf to read a real OPC-UA gateway inst... | PASS (5/5) | FAIL (2/5) |
| 14 | Select ts demo mode, not production. I only need a bare pressure_bar threshold U... | PASS (3/3) | FAIL (2/3) |
| 15 | Explain the recipe's test-generation behavior for two otherwise complete product... | PASS (3/3) | FAIL (2/3) |
| 16 | I have fully scaffolded multimodal, vllm, and agentic stacks with all required m... | PASS (12/12) | FAIL (2/12) |
| 17 | Use the manufacturing recipe for my quality-monitoring project. I have camera fo... | PASS (3/3) | FAIL (2/3) |
| 18 | Show the OpenMES additions for my multimodal weld stack at /work/stacks/weld-def... | PASS (11/11) | FAIL (2/11) |
| 19 | Create an agentic stack for CNC tool wear at /work/stacks/cnc-tool-wear-stack fr... | PASS (7/7) | FAIL (1/7) |
| | **Mean ±σ** | **100% ±0%** | **43% ±31%** |