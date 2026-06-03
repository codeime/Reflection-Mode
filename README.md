# Reflection Mode

<p align="center">
  <img src="assets/reflection-mode-icon.png" alt="Reflection Mode icon" width="160" />
</p>

[中文](README.zh-CN.md) | English

`reflection-mode` is a local plugin for Codex and Claude Code. It turns completed tasks, user corrections, and repeated failure patterns into reusable agent judgment.

Reflection Mode helps agents extract reusable lessons from completed tasks, user corrections, and recurring failure patterns. It also decides whether each lesson can be skipped, should remain a candidate for confirmation, or should be written automatically when it meets the auto-write threshold and the host allows persistence.

## Inspiration

Reflection Mode started from a simple observation: people grow by reflecting on past experience. Without reflection, the same mistakes tend to repeat. AI agents have a similar problem. They can finish a task, receive corrections, or fail in a familiar way, but still lose the lesson unless it is turned into reusable guidance.

This plugin was built to make that learning loop explicit. It treats completed tasks, user corrections, and repeated failures as evidence, then extracts lessons that can change future behavior. When a lesson is durable enough, Reflection Mode also decides whether to skip saving it, keep it as a candidate, or write it automatically when the host allows it.

## What It Does

- Reflects on completed work, corrections, rework, and repeated mistakes.
- Extracts reusable lessons that can change future judgment or execution.
- Distinguishes one-off incidents from durable operating guidance.
- Classifies persistence decisions as `skip`, `candidate for confirmation`, or `auto-write`.
- Grades each candidate with `signal_strength: high | medium | low` before persistence.
- Carries metadata such as evidence count, timestamps, scope, and stale-review hints when writing or returning candidates.
- Supports a lightweight pending-candidate JSONL queue when the host and user permissions allow it.
- Supports both Codex and Claude Code from the same skill payload.

## Reliability Rules

- Auto-write is intentionally strict: it requires `signal_strength: high`, at least two evidence points, a clear target, and explicit host permission.
- If the host write capability is unknown or policy-limited, Reflection Mode returns a candidate instead of writing.
- Saved lessons include freshness metadata so older repo, API, or workflow assumptions can be marked for review.
- Status or list requests only read real host-accessible records; the plugin should not invent reflection history.

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
├── README.zh-CN.md
├── scripts/
│   └── validate_plugin.py
├── schemas/
│   ├── candidate-record.schema.json
│   └── event-record.schema.json
├── .github/workflows/
│   └── validate.yml
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
- `scripts/validate_plugin.py`: repository-level contract checks for manifests, docs, and runtime references.
- `schemas/`: JSON Schemas for pending candidates and reflection event records.

## Installation

The intended installation path is agent-assisted: open [llms.txt](llms.txt), paste its full contents into your coding agent, and ask it to install Reflection Mode for Codex, Claude Code, or both.

The agent should handle the whole flow: cloning this repository, preparing the local marketplace, installing the plugin, and running the validation checks. You should not need to copy individual shell commands from the README unless your agent asks for approval or reports that a CLI is unavailable.

After installation, start a new Codex thread so the plugin context is loaded.

## Validation

```bash
python3 scripts/validate_plugin.py
python3 -m json.tool .codex-plugin/plugin.json
python3 -m json.tool .claude-plugin/plugin.json
ruby -e 'require "yaml"; text=File.read("skills/reflection-mode/SKILL.md"); YAML.load(text.split(/^---\s*$/,3)[1]); YAML.load_file("skills/reflection-mode/agents/openai.yaml"); puts "yaml ok"'
git diff --check
```

If you maintain the plugin with Codex's plugin creator tooling, run its plugin validation script from your local tool installation as an additional check.
