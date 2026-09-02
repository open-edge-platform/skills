# Open Edge Platform — Agent Skills Index

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/skills">GitHub</a>
  <a class="icon_document" href="https://github.com/open-edge-platform/skills/blob/release-2026.2.0/README.md">Readme</a>
</div>
hide_directive-->

This repository is the central hub for **external-facing agent skills** used by customers to build solutions with Open Edge Platform products.

A **skill** is a `SKILL.md` file that gives a coding agent focused, task-specific instructions. When a prompt matches a skill's description, the agent loads that skill's guidance automatically.

## Key Features

- **Focused guidance**: Each skill contains task-specific instructions tailored to a product or workflow.
- **Automatic loading**: Agents match your prompt to the appropriate skill and load it automatically.
- **Multi-agent support**: Skills work across GitHub Copilot, Claude Code, and OpenAI Codex CLIs.
- **Symlink or copy install**: Install via `npx skills` in symlink mode (updates propagate automatically) or copy mode (self-contained, no shared state).
- **Lock file support**: `skills-lock.json` pins exact skill versions so installs are reproducible.

## List of Agent Skills

For the current catalog of available skills, see the [Skills Index](https://github.com/open-edge-platform/skills/tree/release-2026.2.0#open-edge-platform--agent-skills-index)

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-it-works
Release Notes <release-notes>

:::
hide_directive-->
