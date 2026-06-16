---
# Required. Max 64 chars. Lowercase letters, numbers, and hyphens only.
# Must not start/end with a hyphen or contain consecutive hyphens (--).
# Must match the parent directory name.
name: skill-name

# Required. Max 1024 chars. Describe what the skill does AND when to use it.
# Include specific keywords that help agents identify relevant tasks.
description: >-
  Replace with a description of what this skill does and when it should be used.
  Include trigger keywords so the agent reliably activates this skill.

# Optional. License name or path to a bundled license file (e.g. "Apache-2.0" or "LICENSE").
license: Apache-2.0

# Optional. Max 500 chars. Describe environment requirements only if the skill
# has specific needs: intended product, required system packages, network access, etc.
compatibility: >-
  Requires: gh CLI authenticated to GitHub. Network access to api.github.com.

# Optional. Arbitrary key-value map for additional metadata.
# Use reasonably unique key names to avoid conflicts across skills.
metadata:
  author: open-edge-platform
  version: "1.0.0"
  tags: "replace with space-separated topic tags"
  internal: true # Hidden from normal discovery — this is a template, not an installable skill.

# Optional (Experimental). Space-separated list of tools pre-approved for this skill.
# Support varies between agent implementations.
allowed-tools: bash git gh
---

# Skill Title

One-sentence summary of what this skill accomplishes.

## When to Use

Bullet list of situations that should trigger this skill:

- User asks to ...
- User wants to ...
- The codebase contains ... and needs ...

## Procedure

Step-by-step instructions for the agent. Be explicit and unambiguous.

### Step 1 — ...

Description of the step.

```bash
# Example command
```

### Step 2 — ...

Description of the step.

### Step 3 — ...

Description of the step.

## Examples

### Example: ...

**Input:** ...

**Expected output:** ...

## Edge Cases

- If ... then ...
- If ... then ...

## Notes

- Any important caveats or constraints
- Link to [reference material](references/REFERENCE.md) if needed