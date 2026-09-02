# Get Started

- **Time to Complete:** 5 minutes
- **Tool:** `npx skills` (ships with Node.js)

## Prerequisites

### Node.js

`npx` ships with Node.js. Install it from [nodejs.org](https://nodejs.org/) (LTS recommended) or via a version manager:

```bash
# Download and install nvm:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.6/install.sh | bash
# Activate nvm without restarting the shell:
\. "$HOME/.nvm/nvm.sh"
# Install Node.js:
nvm install 24
# Verify versions:
node -v    # v24.x.x
npm -v     # 11.x.x
npx -v     # 11.x.x
npx skills -v  # 1.5.23
```

> **Note:** If `npx skills add` fails, install the pinned CLI version first:
> ```bash
> npm install -g skills@1.5.23
> ```

### Installation Modes

| Mode | Flag | Effect |
|------|------|--------|
| **Symlink** *(default)* | *(none)* | Creates symlinks pointing to a shared location — updates propagate automatically |
| **Copy** | `--copy` | Copies files directly into each agent directory — self-contained, no shared state |

## Install All Skills from This Repo

```bash
# Symlink — interactive (recommended for local development)
npx skills add open-edge-platform/skills#release-2026.2.0

# Symlink — non-interactive, all agents
npx skills add open-edge-platform/skills#release-2026.2.0 --all

# Copy — non-interactive, all agents (portable, no symlinks)
npx skills add open-edge-platform/skills#release-2026.2.0 --all --copy

# Copy — specific agent only (e.g. Claude Code)
npx skills add open-edge-platform/skills#release-2026.2.0 --agent claude-code --copy --yes
```

## Install a Specific Skill

```bash
# Symlink a single skill (interactive agent selection)
npx skills add open-edge-platform/skills#release-2026.2.0 --skill dlstreamer-coding-agent

# Copy a single skill to a specific agent
npx skills add open-edge-platform/skills#release-2026.2.0 --skill dlstreamer-coding-agent --agent claude-code --copy --yes

# Install directly from the skill's source repo
npx skills add open-edge-platform/dlstreamer --skill dlstreamer-coding-agent --copy --yes

# Install from a skill directory when the product repo uses a custom layout
npx skills add https://github.com/openvinotoolkit/physicalai/tree/main/skills/inference/physicalai-runtime-loading-exported-policies \
  --skill physicalai-runtime-loading-exported-policies --copy --yes
```

## List Installed Skills

```bash
npx skills list           # project-level skills
npx skills list -g        # globally installed skills
npx skills list --json    # machine-readable output
```

## Update Skills to the Latest Version

```bash
npx skills update                          # update all project skills
npx skills update dlstreamer-coding-agent  # update a single skill
npx skills update -g                       # update all global skills
```

## Remove a Skill

```bash
npx skills remove dlstreamer-coding-agent                              # interactive
npx skills remove dlstreamer-coding-agent --agent claude-code --yes   # targeted
```

## Restore Skills from the Lock File

If a repo already has a `skills-lock.json`, restore all pinned skills in one command:

```bash
npx skills experimental_install
```

> **Tip:** Use `--agent universal` to install into `.agents/skills/` only (no symlinks to other agent directories).

## Supporting Resources

- [Overview](./index.md)
- [How It Works](./how-it-works.md)
- [How to Configure](./how-to-configure.md)
