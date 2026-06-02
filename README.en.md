# Reflection Mode

<p align="center">
  <img src="assets/reflection-mode-icon.png" alt="Reflection Mode icon" width="160" />
</p>

[中文](README.md) | English

`reflection-mode` is a local plugin for Codex and Claude Code. It turns completed tasks, user corrections, and repeated failure patterns into reusable agent judgment.

Reflection Mode helps agents extract reusable lessons from completed tasks, user corrections, and recurring failure patterns. It also decides whether each lesson should not be persisted, should remain a candidate for confirmation, or should be written automatically when it meets the auto-write threshold and the host allows persistence.

## What It Does

- Reflects on completed work, corrections, rework, and repeated mistakes.
- Extracts reusable lessons that can change future judgment or execution.
- Distinguishes one-off incidents from durable operating guidance.
- Classifies persistence decisions as `do not persist`, `candidate for confirmation`, or `auto-write`.
- Supports both Codex and Claude Code from the same skill payload.

## Project Structure

```text
reflection-mode/
├── assets/
│   ├── reflection-mode-icon.png
│   └── reflection-mode-icon-small.png
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── llms.txt
├── README.md
├── README.en.md
└── skills/reflection-mode/
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── assets/
    │   ├── reflection-mode-icon.png
    │   └── reflection-mode-icon-small.png
    └── references/
        ├── reflective-practice.md
        ├── persistence-decision.md
        └── output-contract.md
```

## Runtime Entries

- `skills/reflection-mode/SKILL.md`: trigger boundaries, core workflow, and runtime rules.
- `references/reflective-practice.md`: reflection method and lesson quality standards.
- `references/persistence-decision.md`: persistence decision rules.
- `references/output-contract.md`: structured output and persistence handling format.
- `agents/openai.yaml`: Codex skill list metadata.
- `assets/`: plugin card icons.

## Installation

For agent-assisted installation, paste [llms.txt](llms.txt) into your coding agent and ask it to install Reflection Mode for Codex, Claude Code, or both.

For local Codex development, if you already have a personal marketplace entry for `reflection-mode`, refresh the local source from the repository root with:

```bash
rsync -a --delete --exclude .git \
  ./ \
  "$HOME/plugins/reflection-mode/"

codex plugin add reflection-mode@personal
```

After installation, start a new Codex thread so the plugin context is loaded.

## Validation

```bash
python3 -m json.tool .codex-plugin/plugin.json
python3 -m json.tool .claude-plugin/plugin.json
ruby -e 'require "yaml"; text=File.read("skills/reflection-mode/SKILL.md"); YAML.load(text.split(/^---\s*$/,3)[1]); YAML.load_file("skills/reflection-mode/agents/openai.yaml"); puts "yaml ok"'
git diff --check
```

If `PyYAML` is available locally, you can also run:

```bash
python3 /Users/guobing/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```
