# Agent Skills Guide

## Table of Contents

1. [What Are Agent Skills?](#1-what-are-agent-skills)
2. [Specification & SKILL.md Format](#2-specification--skillmd-format)
3. [Defining a Skill](#3-defining-a-skill)
4. [Prompts: Showcasing & Evaluating Skills](#4-prompts-showcasing--evaluating-skills)
5. [Creating a Skill](#5-creating-a-skill)
6. [Repo Structure](#6-repo-structure)
7. [Validation](#7-validation)
8. [Security Scanning](#8-security-scanning)
9. [Evaluations & Benchmarks](#9-evaluations--benchmarks)
10. [Managing Skills](#10-managing-skills)
11. [Agent-Specific Best Practices](#11-agent-specific-best-practices)
12. [Key Resources](#key-resources)

## 1. What Are Agent Skills?

Agent Skills are a lightweight, open format for extending AI agent capabilities
with specialized knowledge and workflows. At its core, a skill is a folder
containing a `SKILL.md` file with metadata and instructions that tell an agent
how to perform a specific task. See [Section 6: Repo Structure](#6-repo-structure)
for the full canonical skill directory layout, including required and optional files.

### Why Skills?

Skills solve the problem of agents lacking domain context. They package
procedural knowledge into portable, version-controlled folders that agents load
on demand, providing:

- **Domain expertise** — Legal review processes, data pipelines, SDK patterns
- **Repeatable workflows** — Multi-step tasks as consistent, auditable procedures
- **Cross-product reuse** — Build once, use across 70+ skills-compatible agents

### How Agents Load Skills (Progressive Disclosure)

1. **Discovery** — At startup, agents load only `name` + `description` (~75 words
   per skill). No context cost is incurred until the skill is activated.
2. **Activation** — When a task matches a skill's description, the agent reads the
   full `SKILL.md` body into context (under 4,000 words recommended).
3. **Execution** — The agent follows instructions and optionally loads files from
   `scripts/`, `references/`, or `assets/` as needed (unlimited size, loaded on demand).

---

## 2. Specification & SKILL.md Format

> Source: [agentskills.io/specification](https://agentskills.io/specification)

> **Note**: The spec recognizes only `scripts/`, `references/`, and `assets/` as
> standard subdirectories. Directories such as `evals/`, `benchmark/`, and
> `example-prompts/` are non-standard per the spec — they work in many agents but
> may not be portable. Use `--allow-dirs=evals,benchmark,example-prompts` with
> `skill-validator` to suppress warnings for these known non-standard directories.

### SKILL.md Format

Every `SKILL.md` **MUST** contain YAML frontmatter followed by Markdown content:

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
  tags:
    - video-analytics
    - gstreamer
    - python
---
```

### Frontmatter Field Reference

| Field           | Required | Constraints                                                                                                           | Purpose                                                            |
| --------------- | -------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `name`          | Yes      | 1–64 chars, lowercase `a-z 0-9` and hyphens only. No leading/trailing/consecutive hyphens. **MUST** match directory name. | Unique identifier                                                  |
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
- In agent-facing instruction text, prefer explanatory prose over bare ALL-CAPS directives
  (MUST/NEVER) — agents follow reasoning more reliably than terse imperatives
- Keep under 500 lines / 5,000 tokens — move detail to `references/`
- If approaching 500 lines, add a table of contents and pointer sections

### Optional Directories

#### `scripts/`
Executable code the agent can run without loading into context. Scripts **MUST** be self-contained
or clearly document dependencies. Common languages: Python, Bash, JavaScript.

#### `references/`
Additional docs loaded on demand. Keep individual files focused and under 300 lines
(include ToC if longer). Agents load these files when SKILL.md references them.

> **Rule: never copy existing documentation into the skill directory.**
> Copying creates two versions of the same content that will inevitably diverge
> and conflict. Instead, use GitHub URLs to redirect the agent to the canonical
> source (e.g. `https://github.com/org/repo/blob/main/docs/guide.md`). Relative
> paths and symlinks to files outside the skill folder break when the skill is
> installed via `npx skills add` — only the skill folder itself is copied.
>
> Only create new files inside `references/` for knowledge that has **no existing
> written form** anywhere — proprietary workflows, unpublished internal conventions,
> or context the LLM demonstrably lacks. If the documentation already exists,
> link to it; do not reproduce it.

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

| Content type                 | Where it goes                                                                    |
| ---------------------------- | -------------------------------------------------------------------------------- |
| Step-by-step instructions    | `SKILL.md` body                                                                  |
| API reference, large tables  | GitHub URL in `SKILL.md` — never copy into `references/`                         |
| Reusable code templates      | `assets/<model-name>/` (only if no existing example exists in the repo)          |
| Helper script the agent runs | `scripts/extract.py`                                                             |
| Domain-specific deep docs    | GitHub URL in `SKILL.md` — never copy existing docs into `references/`           |

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

## 4. Prompts: Showcasing & Evaluating Skills

Prompts serve two purposes: they demonstrate when the skill should trigger and what good
output looks like, and they act as ready-to-use starting points for skill consumers.
Each prompt maps to an entry in `evals/evals.json`, keeping showcase and testing in sync.

When you run the `skill-creator` skill (covered in [Section 5](#5-creating-a-skill)),
it generates both artifacts automatically at
[Stage 4](#stage-4-write-test-cases-and-example-prompts) of the creation workflow,
using the 5+ scenarios you defined in your opening prompt. Each scenario produces:

**`example-prompts/`** — one self-contained `.md` file per scenario, ready for consumers
to `@`-mention or paste directly into their agent without reading `SKILL.md`:

```
my-skill/example-prompts/
├── 01-<scenario-a-slug>.md
├── 02-<scenario-b-slug>.md
├── 03-<scenario-c-slug>.md
├── 04-<scenario-d-slug>.md
└── 05-<scenario-e-slug>.md
```

**`evals/evals.json`** — the same scenarios registered as machine-readable eval cases,
with `prompt_file` linking back to the corresponding `example-prompts/` file so both
stay in sync. Assertions are left empty at [Stage 4](#stage-4-write-test-cases-and-example-prompts)
and filled automatically during [Stage 6](#stage-6-grade-benchmark-and-review) grading.

> **Tip:** Before saving, skill-creator presents all prompts for your review and asks
> whether you want to adjust any before they are written to disk.

To add prompts to an existing skill, install skill-creator and use this opening prompt:

```bash
npx skills add anthropics/skills --skill skill-creator -a claude-code
# for GitHub Copilot: -a github-copilot
```

Then say:

```
Create example prompts for my skill at path/to/my-skill/ — here are 5 scenarios
it must handle: [list them]. Save each as a .md under example-prompts/ and
register all in evals/evals.json with prompt_file back-references.
```

---

## 5. Creating a Skill

Use the `skill-creator` skill to build a new skill from scratch. It guides you
through 9 structured stages and produces all required artifacts automatically:
`SKILL.md`, `example-prompts/`, `evals/`, and `BENCHMARK.md`.

**Start here:** gather the inputs below before opening a skill-creator session.

### What to Have Ready Before Starting

```
REQUIRED
────────────────────────────────────────────────────────────────────
5+ distinct scenarios   Different workflows, input types, edge cases
Skill name              lowercase-hyphenated, matches directory name
Scope                   One sentence: what does it enable the agent to do?
Trigger description     USE FOR + DO NOT USE FOR + domain keywords
Novel knowledge         What does the agent get wrong without this skill?

RECOMMENDED
────────────────────────────────────────────────────────────────────
Environment reqs        Packages, Python version, auth, network access
Reference doc URLs      GitHub URLs to existing API docs (do not copy docs into skill)
Edge cases              Boundary conditions and common failure modes
Success criteria        How to tell if agent output is correct
Negative prompts        Requests that look similar but should NOT trigger skill
```

---

### Using the `skill-creator` Skill

Install the skill-creator first:

```bash
npx skills add anthropics/skills --skill skill-creator -a claude-code
# or for GitHub Copilot:
npx skills add anthropics/skills --skill skill-creator -a github-copilot
```

Then start a conversation with a **scope-first prompt**. The key principle: define at
least 5 distinct use cases the skill must handle *before* writing any instructions.
Starting with a single workflow produces a point-solution that is hard to generalize
later; starting with a broad, diverse set of scenarios forces the skill to be generic
from the outset.

**Recommended opening prompt:**

Provide this as your first message to skill-creator. It sets scope, seeds all artifacts,
and ensures the skill is generic from the outset. Copy and fill in the placeholders:

```
I want to create a skill for <domain>.

Before writing any instructions, here are 5+ distinct scenarios this skill must handle.
These cover different workflows, input types, and user levels — not variations of the same task.

1. <realistic user request A — core workflow, typical user>
2. <realistic user request B — different input type or data source>
3. <realistic user request C — edge case, advanced use, or unusual constraint>
4. <realistic user request D — beginner or first-time task>
5. <realistic user request E — integration, combination, or multi-step scenario>
[add more if you have them — more diversity = better generalization]

Please:
- Derive the skill scope and a one-sentence capability statement from these scenarios,
  not from the first scenario alone
- Design the SKILL.md description to trigger on all of them
- Save each scenario as a self-contained .md file under example-prompts/ (named
  01-<slug>.md, 02-<slug>.md, … so consumers can run them directly)
- Register each scenario in evals/evals.json with a prompt_file field pointing to
  the corresponding example-prompts/ file
- Show me the derived scope and all 5 example prompts for review before proceeding
  to write the SKILL.md body
```

Example for a DL Streamer skill:

```
I want to create a skill for DL Streamer video analytics.

Here are 5 distinct scenarios it must handle — these are meaningfully different,
not variations of the same pipeline:

1. Detect people in a live RTSP camera feed and save an annotated video clip to disk
2. Run a multi-model pipeline (detect → classify → track objects) on a local video file
3. Add a custom Python GStreamer element that post-processes inference metadata in-place
4. Convert an existing NVIDIA DeepStream pipeline definition to DL Streamer equivalents
5. Benchmark inference throughput and latency across CPU, Intel GPU, and NPU backends

Please:
- Derive the skill scope from all five scenarios, not just the first one
- Design the description field to trigger on all five classes of request
- Save each scenario as a self-contained .md prompt under example-prompts/
  (01-rtsp-person-detection.md, 02-multi-model-pipeline.md, etc.)
- Register all five in evals/evals.json with prompt_file pointing back to example-prompts/
- Show me the derived scope statement and all 5 example-prompts for review before
  writing the SKILL.md body
```

To improve an existing skill, use this form instead:

```
"Help me improve my existing skill at path/to/my-skill/ — here are 5 use cases
 it currently handles poorly or not at all: [list them].
 Save improved prompts to example-prompts/ and update evals/evals.json."
```

The skill-creator guides you through 9 stages:

| Stage | Name | What happens |
| ----- | ---- | ------------ |
| 1 | Capture Intent | Derives skill scope from your 5+ scenarios |
| 2 | Interview & Research | Gathers domain knowledge, edge cases, dependencies |
| 3 | Write the SKILL.md | Drafts and self-reviews the skill body |
| 4 | Example Prompts & Evals | Saves scenarios to `example-prompts/` and `evals/evals.json` |
| 5 | Run Test Cases | Parallel with-skill vs. baseline execution |
| 6 | Grade & Review | Grades assertions, produces `BENCHMARK.md`, browser eval viewer |
| 7 | Improve | Applies feedback, reruns; repeats until pass rate is satisfactory |
| 8 | Optimize Trigger | Tunes the `description` field for activation accuracy |
| 9 | Package | Bundles skill into installable `.skill` archive |

---

#### Stage 1: Capture Intent

The skill-creator reads the 5+ use cases you provided and derives the full scope
before writing a single line of instructions. If you arrived mid-conversation with
a workflow already visible, it extracts steps and formats from the history — but
will still ask you to supply additional distinct scenarios to ensure generality.
You confirm the derived scope before it proceeds.

Information gathered:

| Question                                                 | Why it matters                                           |
| -------------------------------------------------------- | -------------------------------------------------------- |
| What are 5+ distinct scenarios this skill must handle?   | Ensures the skill is generic, not a point-solution       |
| What should this skill enable the agent to do?           | Defines scope in one sentence                            |
| When should it trigger?                                  | Drives the `description` field                           |
| What is the expected output format?                      | Shapes the instructions                                  |
| Should we set up test cases?                             | Yes for verifiable outputs; optional for subjective ones |

---

#### Stage 2: Interview & Research

The skill-creator proactively gathers deeper information. Prepare these before your session:

**Domain knowledge**
- What specialized knowledge does this skill encode?
- What would the agent get wrong without it?
- What is genuinely novel vs. what the LLM already knows?

**Input / output**
- What does the user typically provide as input?
- What format should the output be in?
- Common variations in how users phrase requests?

**Edge cases**
- Boundary conditions?
- Inputs that look similar but should NOT trigger the skill?
- Most common agent mistakes without this skill?

**Examples**
- 2–3 concrete input/output examples
- Any existing code, documents, or workflows to reference

**Dependencies**
- Required tools, packages, services, environment setup
- Authentication or access requirements
- Minimum versions or platform constraints

**Success criteria**
- What does a correct output look like?
- What does a wrong output look like?
- Are outputs objectively verifiable (code runs, file produced)? Or subjective (style, tone)?

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

#### Stage 4: Write Test Cases and Example Prompts

The 5+ scenarios you defined in Stage 1 are now turned into two artifacts in
parallel — consumer-facing example prompts and machine-readable eval cases:

**`example-prompts/`** — one `.md` file per scenario, written as a ready-to-use
prompt that a skill consumer can paste or `@`-mention directly in their agent:

```
my-skill/example-prompts/
├── 01-<scenario-a-slug>.md
├── 02-<scenario-b-slug>.md
├── 03-<scenario-c-slug>.md
├── 04-<scenario-d-slug>.md
└── 05-<scenario-e-slug>.md
```

Each file contains the full prompt text with any necessary context so the user
can run it without reading `SKILL.md`. This is done automatically when you
include the directives in your opening prompt (see above).

**`evals/evals.json`** — the same prompts registered as eval cases (assertions
left empty at this stage, filled during Stage 6):

```json
{
  "skill_name": "dlstreamer-coding-agent",
  "evals": [
    {
      "id": 1,
      "prompt_file": "example-prompts/01-rtsp-person-detection.md",
      "prompt": "Build a Python app that reads an RTSP stream, detects people with YOLOv8, and saves annotated video...",
      "expected_output": "Python application using gvadetect and DL Streamer pipeline patterns",
      "should_trigger": true,
      "files": [],
      "assertions": []
    }
  ]
}
```

Note the `prompt_file` field — it links the eval entry back to the corresponding
file in `example-prompts/` so both stay in sync. The skill-creator shows you all
generated prompts before saving:

```
"Here are the 5 example prompts I've written, one per scenario. Do these look right,
or do you want to adjust any before I save them?"
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



---

## 6. Repo Structure

### Canonical Layout

```
repo-root/ # this layout can also live in a subfolder within the repository
│
├── .github/
│   ├── skills/                        ← all skill directories
│   │   └── my-skill/
│   │       ├── SKILL.md               ← required:  metadata + instructions
│   │       ├── evals/                 ← required*: automated test cases and assertions (CI quality gate)
│   │       │   └── evals.json
│   │       ├── example-prompts/       ← required*: ready-to-use .md prompts for skill consumers
│   │       │   ├── basic-usage.md
│   │       │   └── advanced-usage.md
│   │       ├── BENCHMARK.md           ← required*: human-readable evaluation report
│   │       ├── references/            ← optional:  docs loaded on demand
│   │       │   └── api-reference.md
│   │       ├── assets/                ← optional:  templates, code models, data
│   │       │   └── basic-example/
│   │       │       ├── model.py
│   │       │       └── README.md
│   │       ├── scripts/               ← optional:  executable helpers
│   │       │   └── validate-output.py
│   │       ├── benchmark/             ← optional:  raw grading outputs (produced by skill-creator)
│   │       │   └── iteration-1/
│   │       └── skill-card.md          ← optional:  disclosure & eval summary
```

> **Quality mandate**: `evals/`, `example-prompts/`, and `BENCHMARK.md` are marked
> `Required*` — optional per the [Agent Skills Specification](https://agentskills.io/specification)
> but **REQUIRED in this repository** for any skill targeting production use or public distribution.
>
> - **`evals/`** contains machine-readable test cases with assertions used by CI to
>   verify that the skill produces correct outputs. Without it there is no automated
>   quality gate.
> - **`example-prompts/`** contains one or more `.md` files that users can `@`-mention
>   directly in their agent to start using the skill immediately. Publishing a skill
>   without ready-to-use prompts implies no quality expectations for the consumer
>   experience.
> - **`BENCHMARK.md`** summarises eval results so reviewers and consumers can assess
>   skill quality before installing.

---

## 7. Validation

> Tool: [github.com/agent-ecosystem/skill-validator]
> (https://github.com/agent-ecosystem/skill-validator)

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

# Allow non-standard directories (evals, benchmark, example-prompts)
skill-validator check --allow-dirs=evals,benchmark,example-prompts .github/skills/my-skill/

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
            --allow-dirs=evals,benchmark,example-prompts \
            .github/skills/
          skill-validator check \
            --strict \
            --allow-dirs=evals,benchmark,example-prompts \
            -o markdown \
            .github/skills/ >> "$GITHUB_STEP_SUMMARY"

      - name: Validate draft skills (non-blocking)
        run: |
          skill-validator check \
            --emit-annotations \
            --allow-dirs=evals,benchmark,example-prompts \
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

## 8. Security Scanning

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

## 9. Evaluations & Benchmarks

Evaluations compare agent output with and without the skill loaded to measure quality, token
usage, and latency. The `skill-creator` skill automates this across **Stages 5–7**:

| Stage | What happens |
| ----- | ------------ |
| **Stage 5 — Run** | Spawns with-skill and baseline runs in parallel; saves `timing.json` per run under `benchmark/iteration-N/` |
| **Stage 6 — Grade** | Evaluates assertions, produces `grading.json`, `benchmark.json`, and `BENCHMARK.md`; launches a browser eval viewer for side-by-side review |
| **Stage 7 — Improve** | Applies your feedback to `SKILL.md`, re-runs into a new `benchmark/iteration-N+1/` folder, repeats until satisfied |

```bash
npx skills add anthropics/skills --skill skill-creator -a claude-code
# Then say: "Run evals for my skill at path/to/my-skill/"
```

For the full `evals/evals.json` schema, grading output format, and `BENCHMARK.md` structure,
see [Stage 4](#stage-4-write-test-cases-and-example-prompts) and
[Stage 6](#stage-6-grade-benchmark-and-review) in Section 5.


### Cross-Agent Benchmarking

`skill-creator` runs Stages 5–7 within a single agent session — it cannot spawn
eval runs across Claude Code, Codex, and Copilot simultaneously. Cross-agent
comparison is done by running the same `evals/evals.json` suite separately in
each target agent and comparing the resulting `benchmark/` outputs.

**Two levels of comparison are available:**

#### 1. LLM-as-Judge Quality Scoring (skill-validator)

Scores the SKILL.md content itself — clarity, novelty, actionability — using
different underlying LLMs as evaluators. Fast, no task execution required.

```bash
# Score with Claude as judge
skill-validator score evaluate --provider claude-cli .github/skills/my-skill/

# Score with OpenAI as judge
export OPENAI_API_KEY=sk-...
skill-validator score evaluate --provider openai .github/skills/my-skill/

# Aggregate into a cross-provider comparison table
skill-validator score report .github/skills/my-skill/
```

This tells you whether the skill instructions are clear and novel, but does not
measure actual task execution quality on each agent.

#### 2. Execution Quality Comparison (manual, per-agent)

Measures how well each agent actually performs the skill tasks. The workflow:

**Step 1** — In each target agent, install skill-creator and run evals:

```bash
# Repeat for each agent: -a claude-code | -a codex | -a github-copilot
npx skills add anthropics/skills --skill skill-creator -a <agent>
# Then say: "Run evals for my skill at path/to/my-skill/"
```

Save outputs under agent-named subdirectories so runs do not overwrite each other
(e.g. `benchmark/claude-code/iteration-1/`, `benchmark/codex/iteration-1/`).

**Step 2** — Compare `BENCHMARK.md` outputs across agents. Key metrics to compare:

| Metric | What it reveals |
|--------|----------------|
| Assertion pass rate (with skill) | Which agent benefits most from the skill |
| Assertion pass rate (without skill) | Which agent needs the skill least (already knows the domain) |
| Token overhead | Cost of loading the skill per agent |
| Trigger accuracy (Stage 8) | Whether the description fires correctly on each agent |

**Step 3** — Identify the lowest-performing agent and iterate on the SKILL.md to
close the gap. A skill is portable when pass rates are within 10–15% across agents.

### Ready to Publish?

Run these checks before making the skill public. Each step maps to a section of
this guide where the tool is documented in full.

```bash
# 1. Validate structure (Section 7)
skill-validator check --strict --allow-dirs=evals,benchmark,example-prompts .github/skills/my-skill/

# 2. Check external links still resolve (Section 7)
skill-validator validate links .github/skills/my-skill/

# 3. LLM quality score — aim for ≥3.5/5 on Novelty (Section 7)
skill-validator score evaluate .github/skills/my-skill/

# 4. Security scan (Section 8)
skillspector scan .github/skills/my-skill/ --no-llm

# 5. Run eval suite and update BENCHMARK.md (Stages 5–7 above)
npx skills add anthropics/skills --skill skill-creator -a claude-code
# Then say: "Run evals for my skill at path/to/my-skill/"
```

Publish by making the repo public — both [skills.sh](https://skills.sh) and
[skillsmp.com](https://skillsmp.com) auto-index public GitHub repos containing
a valid `SKILL.md`. No manual submission required.

---

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

## 11. Agent-Specific Best Practices

Skills are portable across 70+ agents, but each agent has implementation
differences that affect authoring choices. The table below summarises the key
differences; for per-agent deep-dives (companion config mechanics, monorepo
layouts, token budget guidance) see [AGENT_COMPAT.md](AGENT_COMPAT.md).

### Summary

| Agent          | Project skills path     | `allowed-tools` | Script execution | Always-loaded companion config              |
| -------------- | ----------------------- | --------------- | ---------------- | ------------------------------------------- |
| Claude Code    | `.claude/skills/`       | Supported       | bash / Python    | `CLAUDE.md` (repo + parents + `~/.claude/`) |
| GitHub Copilot | `.agents/skills/`       | Not supported   | Via MCP tools    | `.github/copilot-instructions.md`           |
| Codex          | `.agents/skills/`       | Not tested      | bash / Python    | —                                           |
| Cursor         | `.agents/skills/`       | Not supported   | Via terminal     | `.cursor/rules/*.mdc` (`alwaysApply: true`) |
| Gemini CLI     | `.agents/skills/`       | Not tested      | bash / Python    | —                                           |


### Cross-Agent Tips

- **Test trigger accuracy on each target agent early.** A skill that activates
  correctly in Claude Code may not trigger in GitHub Copilot due to description
  parsing differences. Use Stage 8 trigger evals to validate across agents before
  publishing.
- **Avoid agent-specific syntax in `SKILL.md`.** Do not hardcode Copilot-specific
  references (e.g., `@workspace`) or Claude-specific tool names in the skill body —
  skills are meant to be portable.
- **Use the `compatibility` field for hard agent requirements.** If a skill requires
  bash tool access or a specific agent capability, declare it:
  ```yaml
  compatibility: Requires an agent with bash tool access (Claude Code, Codex, Gemini CLI)
  ```
- **Check the install paths table** in [Section 10](#10-managing-skills) for the
  canonical per-agent skill directory locations.
- **Benchmark across agents before publishing.** A skill that scores well on
  Claude Code may underperform on Codex or Copilot. Run the same `evals/evals.json`
  suite in each target agent and compare pass rates. See the
  [Cross-Agent Benchmarking](#cross-agent-benchmarking) subsection in Section 9
  for the recommended workflow and directory layout.

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
| GitHub Copilot plugins marketplace        | https://awesome-copilot.github.com/plugins/        |
| Claude plugins marketplace                | https://claude.com/plugins                         |
| Model Context Protocol (MCP) spec         | https://modelcontextprotocol.io                     |
| Agent Compatibility Reference             | [AGENT_COMPAT.md](AGENT_COMPAT.md)                 |