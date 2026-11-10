<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Skill Benchmark: edgemart-agent-mcp

**Agents**: Copilot (`claude-sonnet-5.5`)  
**Grader**: Copilot (`claude-sonnet-5.5`)  
**Date**: 2026-11-04T08:54:49Z  
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
| Copilot (`claude-sonnet-5.5`) | 50% ±46% | 100% ±0% | **+50pp ↑** |

### Time (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 189 s | 180 s | -10 s ↓ |

### Tokens (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-sonnet-5.5`) | 0 | 0 | +0 ↓ |

## Per-Eval Detail

> Each cell is PASS/FAIL for that run, with the count of expectations met in parentheses (e.g. `PASS (5/5)`); `n/a` means no grading.json was found for that (eval, config, agent) combination.

| Eval | Prompt | Copilot (w/) | Copilot (w/o) |
|---|---|---|---|
| 1 | Register the EdgeMart cafe sales MCP server with Hermes so the agent can answer ... | PASS (3/3) | FAIL (2/3) |
| 2 | My agent framework can't spawn child processes. How can it call the table occupa... | PASS (3/3) | PASS (3/3) |
| 3 | The agent keeps passing table_id to get_utilization and getting an error. Which ... | PASS (3/3) | FAIL (1/3) |
| 4 | Set up Hermes so the EdgeMart Agent Chat tab works with my local model. | PASS (3/3) | FAIL (0/3) |
| 5 | Ask the agent to clear table-7 and report how long tables stay dirty on average ... | PASS (3/3) | FAIL (0/3) |
| 6 | Write a new MCP server in Python that wraps a weather API. | PASS (1/1) | PASS (1/1) |
| | **Mean ±σ** | **100% ±0%** | **50% ±46%** |