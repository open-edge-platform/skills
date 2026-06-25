# Agent Skills Guide

## Table of Contents

1. [What Are Agent Skills?](#1-what-are-agent-skills)
2. [Specification & SKILL.md Format](#2-specification--skillmd-format)
3. [Defining a Skill](#3-defining-a-skill)
4. [Creating a Skill](#4-creating-a-skill)
5. [Repo Structure](#5-repo-structure)
6. [Validation](#6-validation)
7. [Security Scanning](#7-security-scanning)
8. [Prompts: Showcasing & Evaluating Skills](#8-prompts-showcasing--evaluating-skills)
9. [Evaluations & Benchmarks](#9-evaluations--benchmarks)
10. [Managing Skills](#10-managing-skills)
11. [Publishing & Marketplaces](#11-publishing--marketplaces)

---

## 1. What Are Agent Skills?

Agent Skills are a lightweight, open format for extending AI agent capabilities
with specialized knowledge and workflows. At its core, a skill is a folder
containing a `SKILL.md` file with metadata and instructions that tell an agent
how to perform a specific task.

```
my-skill/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation loaded on demand
├── assets/           # Optional: templates, code models, data
├── evals/            # Optional: evaluation test cases
├── benchmark/        # Optional: raw grading outputs
├── BENCHMARK.md      # Optional: human-readable evaluation report
└── skill-card.md     # Optional: disclosure, use case, eval summary
```

### Why Skills?

Skills solve the problem of agents lacking domain context. They package
procedural knowledge into portable, version-controlled folders that agents load
on demand, providing:

- **Domain expertise** — Legal review processes, data pipelines, SDK patterns
- **Repeatable workflows** — Multi-step tasks as consistent, auditable procedures
- **Cross-product reuse** — Build once, use across 70+ skills-compatible agents

### How Agents Load Skills (Progressive Disclosure)

1. **Discovery** — At startup, agents load only `name` + `description` (~100 tokens
   per skill). No context cost until needed.
2. **Activation** — When a task matches a skill's description, the agent reads the
   full `SKILL.md` body into context (<5,000 tokens recommended).
3. **Execution** — The agent follows instructions and optionally loads files from
   `scripts/`, `references/`, or `assets/` as needed (unlimited size, loaded on demand).

### Supported Agents

Skills work across 70+ agents including Claude Code, GitHub Copilot, Cursor,
Gemini CLI, Codex, Windsurf, Cline, OpenCode, Goose, and many more. See
[skills.sh/agent](https://www.skills.sh/agent) for the full list.

---

## 2. Specification & SKILL.md Format

> Source: [agentskills.io/specification](https://agentskills.io/specification)

### Directory Structure

The only required file is `SKILL.md` at the skill root. Three optional
subdirectories are recognized by the spec and all compliant agents:

```
skill-name/
├── SKILL.md          # Required
├── scripts/          # Executable code (Python, Bash, JS)
├── references/       # Markdown docs loaded on demand
└── assets/           # Templates, data files, code models
```

> **Note**: Files or directories outside this structure (e.g., `evals/`,
> `benchmark/`, `README.md` at skill root) are non-standard per the spec. They
> work in many agents but may not be portable. Use `--allow-dirs=evals,benchmark`
> with `skill-validator` to suppress warnings for known non-standard directories.

### SKILL.md Format

Every `SKILL.md` must contain YAML frontmatter followed by Markdown content:

```yaml
---
name: dlstreamer-coding-agent
description: >
  Build new DL Streamer video-analytics applications (Python, C, C++ or
  GStreamer command line). USE FOR: vision AI pipelines, sample apps,
  detection/classification/VLM/tracking, custom GStreamer elements.
  DO NOT USE FOR: general OpenCV questions, non-GStreamer video processing.
license: Apache-2.0
compatibility: Requires Docker with intel/dlstreamer image; Intel GPU, NPU, or CPU
metadata:
  author: Intel Open Edge Platform Team
  version: "2026.1"
  tags:
    - video-analytics
    - gstreamer
    - python
---
```

### Frontmatter Field Reference

| Field           | Required | Constraints                                                                                                           | Purpose                                                            |
| --------------- | -------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `name`          | Yes      | 1–64 chars, lowercase `a-z 0-9` and hyphens only. No leading/trailing/consecutive hyphens. Must match directory name. | Unique identifier                                                  |
| `description`   | Yes      | 1–1024 chars, non-empty                                                                                               | Primary trigger — describes what the skill does AND when to use it |
| `license`       | No       | Short string or filename                                                                                              | License name or reference to bundled LICENSE file                  |
| `compatibility` | No       | 1–500 chars                                                                                                           | Environment requirements: product, packages, network access        |
| `metadata`      | No       | Key-value map                                                                                                         | Arbitrary metadata; use unique keys to avoid conflicts             |
| `allowed-tools` | No       | Space-separated string                                                                                                | Pre-approved tools (experimental; support varies by agent)         |


### Writing a Good Description

The description is the **primary triggering mechanism**. It determines whether
the agent loads the skill at all.

**Good:**
```yaml
description: >
  Build new DL Streamer video-analytics applications (Python, C, C++ or
  GStreamer command line). USE FOR: vision AI pipelines, creating sample apps,
  combining detection/classification/VLM/tracking/recording elements, converting
  DeepStream apps, adding custom GStreamer elements in Python or C++.
  DO NOT USE FOR: general OpenCV questions, non-pipeline video scripts, or
  tasks that don't involve GStreamer elements.
```

**Poor:**
```yaml
description: Helps with video processing.
```

**Guidelines:**
- State both *what* it does and *when* to use it
- Include domain-specific trigger keywords users would naturally type
- Add explicit `DO NOT USE FOR` to prevent false triggers
- Make descriptions slightly "pushy" — agents tend to undertrigger
- Avoid keyword stuffing (5+ quoted terms without prose context flags as spam)

### SKILL.md Body Content

The body contains instructions for the agent. Recommended sections:

```markdown
# Skill Name

Brief context paragraph.

## When to Use
Specific triggers and conditions.

## Instructions
Step-by-step, imperative form.

## Examples
Input/output pairs.

## Common Issues
Troubleshooting table.

## References
Links to bundled reference files.
```

**Writing style principles (Anthropic):**
- Use imperative form: "Run the solver", "Check the status", "Add a constraint"
- Explain *why* rules exist, not just *what* to do — agents follow reasoning
- Avoid rigid ALL-CAPS MUST/NEVER — explain the reasoning instead
- Keep under 500 lines / 5,000 tokens — move detail to `references/`
- If approaching 500 lines, add a table of contents and pointer sections

### Optional Directories

#### `scripts/`
Executable code the agent can run without loading into context. Must be self-contained
or clearly document dependencies. Common languages: Python, Bash, JavaScript.

#### `references/`
Additional docs loaded on demand. Keep individual files focused and under 300 lines
(include ToC if longer). Agents load these files when SKILL.md references them.

#### `assets/`
Static resources used in output: templates, code models, data files, schemas.

### Naming Conventions

```
# Valid
my-skill
dlstreamer-coding-agent

# Invalid
My-Skill           # uppercase
-pdf               # leading hyphen
pdf--processing    # consecutive hyphens
pdf_processing     # underscore (use hyphens)
```

---

## 3. Defining a Skill

### Before You Write Anything

Answer these questions. If you cannot answer all of them, the skill is not ready to write.

1. What should this skill enable the agent to do? (one sentence)
2. When should it trigger? (what user phrases / contexts)
3. What is the expected output format?
4. What knowledge does the agent lack without this skill?
5. Is that knowledge genuinely novel vs. what the LLM already knows from training?

> **The novelty test** (from agent-skill-analysis research on 42,447 public skills):
> Skills that provide genuinely novel information improve LLM outputs. Skills that
> restate common knowledge can *degrade* performance by cluttering context.
> Only build a skill if you have proprietary, specialized, or unpublished knowledge to share.

### Scope Discipline

| Signal                                           | Recommendation                      |
| ------------------------------------------------ | ----------------------------------- |
| The skill handles 5+ unrelated tasks             | Split into multiple focused skills  |
| The skill description is over 200 words          | Narrow the scope                    |
| The agent would know this from training          | Reconsider — add only novel details |
| The skill is for a single one-time workflow step | Consider a prompt instead           |

### Structure Decisions

| Content type                 | Where it goes                                  |
| ---------------------------- | ---------------------------------------------- |
| Step-by-step instructions    | `SKILL.md` body                                |
| API reference, large tables  | `references/api-reference.md`                  |
| Reusable code templates      | `assets/<model-name>/`                         |
| Helper script the agent runs | `scripts/extract.py`                           |
| Domain-specific deep docs    | `references/finance.md`, `references/legal.md` |

### Organizing Reference Files by Variant

When a skill spans multiple frameworks or languages, organize `references/` so
the agent reads only what's relevant:

```
cloud-deploy/
├── SKILL.md           # workflow + selection logic
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

---

## 4. Creating a Skill

Two paths exist. **Path A** uses the `skill-creator` skill — an AI-guided conversational
workflow. **Path B** is the manual approach. Both produce the same artifacts. Path A is
recommended for first-time skill authors.

---

### Path A: Using the `skill-creator` Skill

Install the skill-creator first:

```bash
npx skills add anthropics/skills --skill skill-creator -a claude-code
# or for GitHub Copilot:
npx skills add anthropics/skills --skill skill-creator -a github-copilot
```

Then start a conversation:

```
"I want to create a skill for X"
"Turn this workflow into a skill"
"Help me improve my existing skill at path/to/my-skill/"
```

The skill-creator guides you through 9 stages:

---

#### Stage 1: Capture Intent

If you are mid-conversation with a workflow already visible, the skill-creator
**extracts answers from the conversation history first** — tools used, sequence of steps,
corrections you made, input/output formats. You confirm before it proceeds.

Information gathered:

| Question                                       | Why it matters                                           |
| ---------------------------------------------- | -------------------------------------------------------- |
| What should this skill enable the agent to do? | Defines scope                                            |
| When should it trigger?                        | Drives the `description` field                           |
| What is the expected output format?            | Shapes the instructions                                  |
| Should we set up test cases?                   | Yes for verifiable outputs; optional for subjective ones |

---

#### Stage 2: Interview & Research

The skill-creator proactively gathers deeper information. Prepare these before your session:

```
DOMAIN KNOWLEDGE
  - What specialized knowledge does this skill encode?
  - What would the agent get wrong without it?
  - What is genuinely novel vs. what the LLM already knows?

INPUT / OUTPUT
  - What does the user typically provide as input?
  - What format should the output be in?
  - Common variations in how users phrase requests?

EDGE CASES
  - Boundary conditions?
  - Inputs that look similar but should NOT trigger the skill?
  - Most common agent mistakes without this skill?

EXAMPLES
  - 2–3 concrete input/output examples
  - Any existing code, documents, or workflows to reference

DEPENDENCIES
  - Required tools, packages, services, environment setup
  - Authentication or access requirements
  - Minimum versions or platform constraints

SUCCESS CRITERIA
  - What does a correct output look like?
  - What does a wrong output look like?
  - Are outputs objectively verifiable (code runs, file produced)?
    Or subjective (style, tone)?
```

The skill-creator also checks available MCPs and researches in parallel —
searching docs, finding similar skills, looking up best practices.

---

#### Stage 3: Write the SKILL.md

Based on the interview, the skill-creator drafts the full `SKILL.md` applying these
principles:

| Principle             | Detail                                                          |
| --------------------- | --------------------------------------------------------------- |
| Imperative form       | "Run the solver", "Check the status", not "You should run..."   |
| Explain the why       | LLMs follow reasoning, not just rules                           |
| Avoid rigid ALL-CAPS  | Reframe as explained reasoning instead                          |
| Size discipline       | Under 500 lines — move detail to `references/`                  |
| Novelty focus         | Only include what the agent could not produce from training     |
| No surprise principle | No malware, misleading content, or unauthorized access patterns |

After drafting, the skill-creator **reviews its own draft with fresh eyes** before
showing you — checking whether instructions are general enough to work across a million
different users, not just the session examples.

---

#### Stage 4: Write Test Cases

The skill-creator generates 2–3 realistic test prompts and shows them to you:

```
"Here are a few test cases I'd like to try. Do these look right,
or do you want to add more?"
```

Saved to `evals/evals.json` (assertions left empty at this stage):

```json
{
  "skill_name": "dlstreamer-coding-agent",
  "evals": [
    {
      "id": 1,
      "prompt": "Build a Python app that reads an RTSP stream, detects people with YOLOv8, and saves annotated video...",
      "expected_output": "Python application using gvadetect and DL Streamer pipeline patterns",
      "should_trigger": true,
      "files": [],
      "assertions": []
    }
  ]
}
```

---

#### Stage 5: Run Test Cases (Parallel)

The skill-creator spawns with-skill AND baseline runs **in the same turn** — never
sequentially. While runs execute, it drafts quantitative assertions and saves timing
data (`timing.json`) for each completed run:

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

Workspace structure created during runs:

```
my-skill-workspace/
└── iteration-1/
    ├── person-detection-rtsp/
    │   ├── with_skill/outputs/
    │   └── without_skill/outputs/
    └── multi-model-vlm-pipeline/
        ├── with_skill/outputs/
        └── without_skill/outputs/
```

---

#### Stage 6: Grade, Benchmark, and Review

1. **Grade** — evaluates each assertion, saves to `grading.json`:

```json
{
  "eval_id": 1,
  "eval_name": "person-detection-rtsp",
  "assertions": [
    {
      "text": "Uses gvadetect element for object detection",
      "passed": true,
      "evidence": "Found 'gvadetect model=...' in generated pipeline string"
    },
    {
      "text": "Does not use DeepStream element names",
      "passed": false,
      "evidence": "Found 'nvdsgst_' prefix at line 18 — should use DL Streamer elements"
    }
  ]
}
```

2. **Aggregate** — produces `benchmark.json` and `benchmark.md` with pass rate, time,
   and token usage for with-skill vs. baseline.

3. **Launch eval viewer** — browser UI with:
   - **Outputs tab**: each test case side by side, feedback textbox per case
   - **Benchmark tab**: quantitative comparison with per-eval breakdowns

4. **Analyst pass** — surfaces patterns: non-discriminating assertions (always pass),
   high-variance evals (flaky), token/time tradeoffs.

5. **You review and submit feedback** — click through, leave comments, click
   "Submit All Reviews". The skill-creator reads `feedback.json`.

---

#### Stage 7: Improve the Skill

Improvement principles:

| Principle                | What it means in practice                                             |
| ------------------------ | --------------------------------------------------------------------- |
| **Generalize**           | Fix the underlying pattern, not just the specific failing example     |
| **Keep lean**            | Remove instructions not pulling their weight                          |
| **Explain the why**      | Rewrite brittle MUSTs as explained reasoning                          |
| **Bundle repeated work** | If all 3 test runs wrote the same helper script, add it to `scripts/` |
| **Read transcripts**     | Check if the skill causes unproductive agent work                     |

After improvement: rerun → `iteration-2/` → review → repeat until satisfied.

---

#### Stage 8: Optimize the Description Trigger

After content is stable, optimize the `description` field for triggering accuracy.

**Step 1** — Generate 20 trigger eval queries (mix of should-trigger and should-not-trigger):

```json
[
  {
    "query": "i have an rtsp camera feed from our factory floor and i want to detect safety vest violations in real time and log alerts to a file",
    "should_trigger": true
  },
  {
    "query": "how do I read a video file frame by frame using cv2.VideoCapture and display it with imshow",
    "should_trigger": false
  }
]
```

Good trigger queries are: realistic and specific, mix of formal/casual phrasing,
near-misses for should-not-trigger, substantive enough to benefit from a skill.

**Step 2** — You review and edit queries in the HTML eval viewer.

**Step 3** — Run the optimization loop:

```bash
python -m scripts.run_loop \
  --eval-set evals/trigger-evals.json \
  --skill-path .github/skills/my-skill \
  --model claude-sonnet-4-5-20250929 \
  --max-iterations 5 \
  --verbose
```

Splits queries 60% train / 40% held-out test, evaluates each 3× for reliability,
proposes description improvements, selects `best_description` by test score.

**Step 4** — Apply `best_description` to `SKILL.md` frontmatter.

---

#### Stage 9: Package

```bash
python -m scripts.package_skill .github/skills/my-skill
# Produces: my-skill.skill (installable archive)
```

---

### Path B: Manual Step-by-Step

#### Step 1: Initialize

```bash
npx skills init my-skill
# Creates: my-skill/SKILL.md
```

#### Step 2: Pre-Writing Checklist

```
SCOPE
  [ ] What does this skill enable the agent to do? (one sentence)
  [ ] What would the agent get wrong without it?
  [ ] Can I name 3 specific tasks this skill handles?
  [ ] Can I name 2 tasks this skill should NOT handle?

NOVELTY — answer YES to at least one, or reconsider the skill
  [ ] Does this encode proprietary API patterns not in public docs?
  [ ] Does this encode internal conventions or unpublished workflows?
  [ ] Does this encode domain expertise the LLM demonstrably lacks?

NAME & DESCRIPTION
  [ ] Is the name lowercase, hyphenated, under 64 chars, matching the dir?
  [ ] Does the description include USE FOR: and DO NOT USE FOR: sections?
  [ ] Does the description include specific domain keywords users would type?
  [ ] Is the description between 150–500 chars? (optimal trigger range)

STRUCTURE
  [ ] What goes in SKILL.md body? (core instructions, <500 lines)
  [ ] What goes in references/? (detailed API docs, domain guides)
  [ ] What goes in assets/? (templates, code models)
  [ ] What goes in scripts/? (executable helpers the agent runs)

EXAMPLES
  [ ] Do I have 2–3 concrete input/output examples?
  [ ] Are my examples realistic (not toy problems)?

SUCCESS CRITERIA
  [ ] What does a correct output look like?
  [ ] What does a wrong output look like?
  [ ] Are outputs objectively verifiable or subjective?
```

#### Step 3: Write the SKILL.md

```markdown
---
name: my-skill
description: >
  [What it does]. USE FOR: [specific A], [specific B], [specific C].
  DO NOT USE FOR: [anti-trigger A], [anti-trigger B].
license: Apache-2.0
metadata:
  author: Your Team
  version: "1.0"
---

# Skill Name

[Context paragraph]

## When to Use
- [Trigger condition A]
- [Trigger condition B]

## Instructions

[Step 1 — imperative, explain the why]

[Step 2 — imperative, explain the why]

## Examples

**Example 1:**
Input: [realistic input]
Output: [expected output]

## Common Issues

| Problem | Cause | Fix |
|---|---|---|
| [symptom] | [root cause] | [resolution] |

## References
- See [references/api-reference.md](references/api-reference.md) for full API details
- See [assets/](assets/) for canonical code models
```

#### Step 4: Add Reference Files

```bash
mkdir -p my-skill/references
# Create: references/api-reference.md, references/advanced-patterns.md
```

Add a ToC at the top of any reference file over 300 lines.
Reference from `SKILL.md` with relative paths.

#### Step 5: Add Code Models to `assets/`

```bash
mkdir -p my-skill/assets/basic-example
# Create: assets/basic-example/model.py, assets/basic-example/README.md
```

#### Step 6: Write Evals

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "prompt_file": "basic-use-case.prompt.md",
      "prompt": "Realistic user request that requires this skill...",
      "expected_output": "Description of what correct output looks like",
      "should_trigger": true,
      "assertions": [
        { "name": "key-api-present", "type": "contains", "value": "api.method()" },
        { "name": "wrong-pattern-absent", "type": "not_contains", "value": "wrong.api()" }
      ]
    }
  ]
}
```

#### Step 7: Validate

```bash
skill-validator check --strict --allow-dirs=evals,benchmark my-skill/
skill-validator analyze content my-skill/
skill-validator score evaluate my-skill/
```

#### Step 8: Security Scan

```bash
skillspector scan my-skill/ --no-llm
# Fix any HIGH or CRITICAL findings before proceeding
```

#### Step 9: Run Evals & Iterate

See [Section 9: Evaluations & Benchmarks](#9-evaluations--benchmarks).

---

### Key Information: What to Have Ready Before Creating Any Skill

```
REQUIRED
────────────────────────────────────────────────────────────────────
Skill name          lowercase-hyphenated, matches directory name
Scope               One sentence: what does it enable the agent to do?
Trigger description USE FOR + DO NOT USE FOR + domain keywords
Novel knowledge     What does the agent get wrong without this skill?
2–3 examples        Realistic input/output pairs

RECOMMENDED
────────────────────────────────────────────────────────────────────
Environment reqs    Packages, Python version, auth, network access
Reference docs      URLs or files for detailed API documentation
Code models         Canonical implementations to bundle in assets/
Edge cases          Boundary conditions and common failure modes
Success criteria    How to tell if agent output is correct

FOR EVALS (needed before Stage 4 / Step 6)
────────────────────────────────────────────────────────────────────
Test prompts        2–3 realistic user requests
Expected outputs    What correct results look like
Assertions          Specific verifiable patterns in the output
Negative prompts    Requests that look similar but should NOT trigger skill
```

---

## 5. Repo Structure

### Canonical Layout

```
repo-root/ # this layout can also live in a subfolder within the repository
│
├── .github/
│   ├── skills/                        ← all skill directories
│   │   └── my-skill/
│   │       ├── SKILL.md               ← required
│   │       ├── references/            ← docs loaded on demand
│   │       │   └── api-reference.md
│   │       ├── assets/                ← templates, code models
│   │       │   └── basic-example/
│   │       │       ├── model.py
│   │       │       └── README.md
│   │       ├── scripts/               ← executable helpers
│   │       │   └── validate-output.py
│   │       ├── evals/                 ← machine-readable test cases
│   │       │   └── evals.json
│   │       ├── benchmark/             ← raw grading outputs per iteration
│   │       │   └── iteration-1/
│   │       ├── BENCHMARK.md           ← human-readable eval report
│   │       └── skill-card.md          ← disclosure & eval summary
```

## 6. Validation

> Tool: [github.com/agent-ecosystem/skill-validator](https://github.com/agent-ecosystem/skill-validator)

### Install

```bash
# Homebrew
brew tap agent-ecosystem/tap && brew install skill-validator

# Go
go install github.com/agent-ecosystem/skill-validator/cmd/skill-validator@latest
```

### Command Map — Lifecycle Stages

| Development stage | Command                 | What it checks                                                     |
| ----------------- | ----------------------- | ------------------------------------------------------------------ |
| Scaffolding       | `validate structure`    | Spec compliance, frontmatter, tokens, internal links, orphan files |
| Writing content   | `analyze content`       | Density, specificity, imperative ratio, section structure          |
| Adding examples   | `analyze contamination` | Cross-language contamination risk                                  |
| Review            | `validate links`        | External HTTP/HTTPS links                                          |
| Quality scoring   | `score evaluate`        | LLM-as-judge: clarity, actionability, novelty, token efficiency    |
| Comparing models  | `score report`          | Cross-provider score comparison                                    |
| Pre-publish       | `check --strict`        | All checks combined, warnings as errors                            |

### Common Commands

```bash
# Run all checks on a single skill
skill-validator check .github/skills/my-skill/

# Strict mode (warnings = errors) for CI
skill-validator check --strict .github/skills/my-skill/

# Allow non-standard directories (evals, benchmark)
skill-validator check --allow-dirs=evals,benchmark .github/skills/my-skill/

# Check all skills in a directory
skill-validator check .github/skills/

# Analyze content quality
skill-validator analyze content .github/skills/my-skill/

# LLM scoring (requires API key)
export ANTHROPIC_API_KEY=sk-ant-...
skill-validator score evaluate .github/skills/my-skill/

# Or use Claude CLI (no key needed if authenticated)
skill-validator score evaluate --provider claude-cli .github/skills/my-skill/

# JSON output for tooling
skill-validator check -o json .github/skills/my-skill/ | jq '.content_analysis'

# Markdown output for GitHub Actions summary
skill-validator check -o markdown .github/skills/ >> $GITHUB_STEP_SUMMARY
```

### Exit Codes

| Code | Meaning                                   |
| ---- | ----------------------------------------- |
| 0    | Clean pass — no errors, no warnings       |
| 1    | Validation errors present                 |
| 2    | Warnings present, no errors               |
| 3    | CLI/usage error (bad flags, missing args) |

### What It Checks — Structure Validation

- `SKILL.md` exists at skill root
- Only recognized directories (`scripts/`, `references/`, `assets/`)
- Frontmatter: required fields present, `name` valid format, matches directory name
- Token counts: SKILL.md body warns >5,000 tokens; per reference file warns >10,000
- No unclosed code fences (breaks agent parsing — reported as errors, not warnings)
- Internal relative links resolve
- Orphan file detection (files in `scripts/`, `references/`, `assets/` not reachable from SKILL.md)

### Content Analysis Metrics

| Metric                  | What it measures                                      |
| ----------------------- | ----------------------------------------------------- |
| Word count              | Total words                                           |
| Code block ratio        | Proportion of fenced code blocks                      |
| Imperative ratio        | Sentences starting with imperative verbs              |
| Information density     | `(code_block_ratio × 0.5) + (imperative_ratio × 0.5)` |
| Instruction specificity | Strong directive markers / (strong + weak)            |
| Section count           | H2+ headers                                           |
| List item count         | Bullet and numbered items                             |

### LLM Scoring Dimensions

| Dimension           | Description                                      |
| ------------------- | ------------------------------------------------ |
| Clarity             | How clear and unambiguous are the instructions?  |
| Actionability       | Can an agent follow them step-by-step?           |
| Token Efficiency    | Does every token earn its place in context?      |
| Scope Discipline    | Does it stay focused on its stated purpose?      |
| Directive Precision | Precise directives vs vague suggestions?         |
| **Novelty**         | **How much goes beyond what LLMs already know?** |

> **Novelty is the key predictor of skill value** (from agent-skill-analysis research).
> Skills scoring low on novelty may hurt performance rather than help it.

### CI Integration

```yaml
# .github/workflows/validate-skills.yml
name: Validate Skills
on:
  pull_request:
    paths:
      - ".github/skills/**"

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install skill-validator
        run: brew install agent-ecosystem/tap/skill-validator

      - name: Validate published skills (strict)
        run: |
          skill-validator check \
            --strict \
            --emit-annotations \
            --allow-dirs=evals,benchmark \
            .github/skills/
          skill-validator check \
            --strict \
            --allow-dirs=evals,benchmark \
            -o markdown \
            .github/skills/ >> "$GITHUB_STEP_SUMMARY"

      - name: Validate draft skills (non-blocking)
        run: |
          skill-validator check \
            --emit-annotations \
            --allow-dirs=evals,benchmark \
            .github/skills/drafts/
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/agent-ecosystem/skill-validator
    rev: v1.5.6
    hooks:
      - id: skill-validator-claude      # Claude Code (.claude/skills/)
      - id: skill-validator-copilot     # GitHub Copilot (.agents/skills/)
```

---

## 7. Security Scanning

> Tool: [github.com/NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector)

### Background

Research on 42,447 public skills found:
- **26.1%** contain at least one vulnerability
- **5.2%** show likely malicious intent
- Skills with executable scripts are **2.12× more likely** to be vulnerable

Always scan skills before installing from external sources.

### Install

```bash
# Python (recommended)
git clone https://github.com/NVIDIA/skillspector.git && cd skillspector
uv venv .venv && source .venv/bin/activate
make install

# Docker (no Python required)
make docker-build
```

### Basic Usage

```bash
# Scan a local skill directory
skillspector scan .github/skills/my-skill/

# Static analysis only (fast, no LLM needed)
skillspector scan .github/skills/my-skill/ --no-llm

# Scan a GitHub repository
skillspector scan https://github.com/user/my-skill

# Output formats
skillspector scan .github/skills/my-skill/ --format json --output report.json
skillspector scan .github/skills/my-skill/ --format sarif --output report.sarif
```

### LLM-Enhanced Analysis

```bash
export SKILLSPECTOR_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
skillspector scan .github/skills/my-skill/
```

| Provider    | Env var                | Default model                 |
| ----------- | ---------------------- | ----------------------------- |
| `anthropic` | `ANTHROPIC_API_KEY`    | claude-opus-4-6               |
| `openai`    | `OPENAI_API_KEY`       | gpt-5.4                       |
| `nv_build`  | `NVIDIA_INFERENCE_KEY` | deepseek-ai/deepseek-v4-flash |

### Vulnerability Categories (64 Patterns, 16 Categories)

| Category              | Patterns | Key risks                                                            |
| --------------------- | -------- | -------------------------------------------------------------------- |
| Prompt Injection      | 5        | Instruction override, hidden directives, behavior manipulation       |
| Data Exfiltration     | 4        | Env var harvesting, file enumeration, context leakage                |
| Privilege Escalation  | 3        | Excessive permissions, sudo execution, credential access             |
| Supply Chain          | 6        | Unpinned deps, `curl \| bash`, obfuscated code, known CVEs (OSV.dev) |
| Excessive Agency      | 4        | Unrestricted tool access, autonomous high-impact decisions           |
| Output Handling       | 3        | Unvalidated output injection, unbounded output                       |
| System Prompt Leakage | 3        | Direct exposure, indirect extraction, tool-based exfil               |
| Memory Poisoning      | 3        | Persistent context injection, context window stuffing                |
| Tool Misuse           | 3        | Parameter abuse, chaining abuse, unsafe defaults                     |
| Rogue Agent           | 2        | Self-modification, unauthorized cron/startup persistence             |
| Trigger Abuse         | 3        | Overly broad trigger, shadow command, keyword baiting                |
| Behavioral AST        | 8        | `exec()`, `eval()`, `subprocess`, `os.system` detection              |
| Taint Tracking        | 5        | Credential exfiltration chains, file-to-network flows                |
| YARA Signatures       | 4        | Malware, webshells, cryptominers, exploit tools                      |
| MCP Least Privilege   | 4        | Underdeclared capabilities, wildcard permissions                     |
| MCP Tool Poisoning    | 4        | Hidden instructions, unicode deception, description mismatch         |

### Risk Score

| Score  | Severity | Recommendation            |
| ------ | -------- | ------------------------- |
| 0–20   | LOW      | SAFE                      |
| 21–50  | MEDIUM   | CAUTION — review findings |
| 51–80  | HIGH     | DO NOT INSTALL            |
| 81–100 | CRITICAL | DO NOT INSTALL            |

Score weights: CRITICAL +50, HIGH +25, MEDIUM +10, LOW +5.
Skills with executable scripts receive a **1.3× multiplier**.

### CI Integration (SARIF)

```yaml
- name: Security scan skills
  run: |
    skillspector scan \
      .github/skills/ \
      --no-llm \
      --format sarif \
      --output security-report.sarif

- name: Upload SARIF results
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: security-report.sarif
```

---

## 8. Prompts: Showcasing & Evaluating Skills

Prompts demonstrate (a) when the skill should trigger and (b) what “good output” looks like. The `skill-creator` skill (**Stage 4**) generates these automatically; you can also write them manually.

### Via `skill-creator` (Recommended)

The `skill-creator` drafts 2–3 realistic test prompts based on the interview from Stage 2 and presents them for your review before saving:

```
"Here are a few test cases I'd like to try. Do these look right,
or do you want to add more?"
```

Install and invoke:

```bash
npx skills add anthropics/skills --skill skill-creator -a claude-code
# or for GitHub Copilot:
npx skills add anthropics/skills --skill skill-creator -a github-copilot
```

Then say: `"Create prompts for my skill at path/to/my-skill/"`

The `skill-creator` saves prompts to `evals/evals.json` with `expected_output` descriptions and leaves `assertions` empty for grading in Stage 6.

### Manually

Create `evals/evals.json` in your skill directory with at least:

- 2 should-trigger prompts covering the core use case
- 1 should-not-trigger near-miss to guard against false activation

For each prompt, include an `expected_output` description and 2–5 concrete `assertions` — prefer `contains`/`not_contains` checks over subjective criteria. See [Section 9](#9-evaluations--benchmarks) for the full schema and grading workflow.

---

## 9. Evaluations & Benchmarks

Evaluations compare agent output with and without the skill loaded to measure quality, token usage, and latency. The `skill-creator` skill automates this across **Stages 5–7**; the steps below describe the manual equivalent.

### Via `skill-creator` (Recommended)

| Stage | What happens |
| ----- | ------------ |
| **Stage 5 — Run** | Spawns with-skill and baseline runs in parallel; saves `timing.json` per run under `benchmark/iteration-N/` |
| **Stage 6 — Grade** | Evaluates assertions, produces `grading.json`, `benchmark.json`, and `BENCHMARK.md`; launches a browser eval viewer for side-by-side review |
| **Stage 7 — Improve** | Applies your feedback to `SKILL.md`, re-runs into a new `benchmark/iteration-N+1/` folder, repeats until satisfied |

```bash
npx skills add anthropics/skills --skill skill-creator -a claude-code
# Then say: "Run evals for my skill at path/to/my-skill/"
```

### Manually

**Step 1 — Run with-skill and baseline**

Run your agent on each prompt in `evals/evals.json` twice and save outputs:

```
benchmark/
└── iteration-1/
    └── <eval-name>/
        ├── with_skill/
        │   ├── output.md
        │   └── timing.json
        └── without_skill/
            ├── output.md
            └── timing.json
```

**Step 2 — Grade assertions**

Check each assertion against the with-skill output and record results in `benchmark/iteration-1/grading.json`:

```json
[
  {
    "eval_id": 1,
    "assertions": [
      { "name": "key-pattern-present",  "passed": true, "evidence": "Found at line 4" },
      { "name": "wrong-pattern-absent", "passed": true, "evidence": "Not found" }
    ]
  }
]
```

**Step 3 — Summarize in `BENCHMARK.md`**

Document pass rate, token delta, and latency per iteration:

```markdown
## Iteration 1

| Eval   | With Skill            | Without Skill | Delta |
| ------ | --------------------- | ------------- | ----- |
| eval-1 | 2/2 assertions passed | 0/2           | +2    |
| eval-2 | 1/2 assertions passed | 1/2           | 0     |

**Overall pass rate (with skill):** 75%
**Avg token overhead:** +1,200 tokens
```

**Step 4 — Iterate**

Update `SKILL.md` based on failures, increment to `benchmark/iteration-2/`, and re-run.


## 10. Managing Skills

> Tool: [github.com/vercel-labs/skills](https://github.com/vercel-labs/skills)

### Install and Add Skills

```bash
# Add from a GitHub repo (interactive)
npx skills add owner/repo

# Add specific skills
npx skills add owner/repo --skill my-skill --skill another-skill

# Add to specific agents only
npx skills add owner/repo -a claude-code -a github-copilot

# Add globally (all projects)
npx skills add owner/repo -g

# Non-interactive (CI/CD)
npx skills add owner/repo --skill my-skill -g -a claude-code -y

# From local path
npx skills add ./my-local-skills

# List available skills without installing
npx skills add owner/repo --list
```

### Installation Scope

| Scope   | Flag      | Location            | Use case                       |
| ------- | --------- | ------------------- | ------------------------------ |
| Project | (default) | `./<agent>/skills/` | Team-shared, committed to repo |
| Global  | `-g`      | `~/<agent>/skills/` | Personal, all projects         |

### Installation Method

| Method                | How                                | Use when                                       |
| --------------------- | ---------------------------------- | ---------------------------------------------- |
| Symlink (recommended) | Creates symlinks to canonical copy | Default — single source of truth, easy updates |
| Copy                  | `--copy` flag                      | Symlinks not supported in your environment     |

### Agent Installation Paths

| Agent          | Project path        | Global path                   |
| -------------- | ------------------- | ----------------------------- |
| Claude Code    | `.claude/skills/`   | `~/.claude/skills/`           |
| GitHub Copilot | `.agents/skills/`   | `~/.copilot/skills/`          |
| Cursor         | `.agents/skills/`   | `~/.cursor/skills/`           |
| Codex          | `.agents/skills/`   | `~/.codex/skills/`            |
| Gemini CLI     | `.agents/skills/`   | `~/.gemini/skills/`           |
| Windsurf       | `.windsurf/skills/` | `~/.codeium/windsurf/skills/` |
| Cline          | `.agents/skills/`   | `~/.agents/skills/`           |
| OpenCode       | `.agents/skills/`   | `~/.config/opencode/skills/`  |

### Other CLI Commands

```bash
# List installed skills
npx skills list
npx skills ls -g                          # global only
npx skills ls -a claude-code              # specific agent

# Find skills
npx skills find                           # interactive fuzzy search
npx skills find typescript                # keyword search

# Update
npx skills update                         # all skills
npx skills update my-skill               # specific skill
npx skills update -y                      # non-interactive

# Remove
npx skills remove my-skill
npx skills remove my-skill -a claude-code # from specific agent
npx skills remove --all                   # remove everything

# Use without installing
npx skills use owner/repo --skill my-skill | claude
npx skills use owner/repo --skill my-skill --agent claude-code
```

### Internal / WIP Skills

Mark in-progress or team-only skills to hide from normal discovery:

```yaml
---
name: my-internal-skill
description: An internal skill not shown by default
metadata:
  internal: true
---
```

Install with: `INSTALL_INTERNAL_SKILLS=1 npx skills add owner/repo --list`

---

## 11. Publishing & Marketplaces

### Pre-Publication Checklist

```bash
# 1. Validate structure
skill-validator check --strict --allow-dirs=evals,benchmark .github/skills/my-skill/

# 2. Check external links still resolve
skill-validator validate links .github/skills/my-skill/

# 3. LLM quality score (aim for ≥3.5/5 on Novelty)
skill-validator score evaluate .github/skills/my-skill/

# 4. Security scan
skillspector scan .github/skills/my-skill/ --no-llm

# 5. Run eval suite and update BENCHMARK.md
# (see Section 9)
```

### Packaging

```bash
python -m scripts.package_skill .github/skills/my-skill
# Produces: my-skill.skill (installable archive)
```

### skills.sh (Vercel-backed, CLI-first)

**URL**: [skills.sh](https://skills.sh)

- 796,000+ indexed skills; 70+ supported agents
- CLI: `npx skills add owner/repo`
- Auto-indexes public GitHub repos containing valid `SKILL.md` files
- No manual submission — make your repo public and it appears
- Leaderboard with install counts

### skillsmp.com (Discovery-first, SOC-categorized)

**URL**: [skillsmp.com](https://skillsmp.com)

- 1.7M+ indexed skills
- Organized by occupation (SOC categories) and creator
- REST API for search and analytics
- Browse by category: Tools, Business, Development, Testing & Security, Data & AI

---

## Key Resources

| Resource                                  | URL                                                |
| ----------------------------------------- | -------------------------------------------------- |
| Agent Skills Specification                | https://agentskills.io/specification               |
| Anthropic skills (skill-creator, evals)   | https://github.com/anthropics/skills               |
| Microsoft skills (prompts, agents, tests) | https://github.com/microsoft/skills                |
| NVIDIA skills (BENCHMARK.md, skill-card)  | https://github.com/NVIDIA/skills                   |
| Google skills                             | https://github.com/google/skills                   |
| Skills CLI                                | https://github.com/vercel-labs/skills              |
| skill-validator                           | https://github.com/agent-ecosystem/skill-validator |
| SkillSpector                              | https://github.com/NVIDIA/SkillSpector             |
| skills.sh marketplace                     | https://skills.sh                                  |
| skillsmp.com marketplace                  | https://skillsmp.com                               |