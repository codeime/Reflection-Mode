# Reflection Mode

<p align="center">
  <img src="assets/reflection-mode-icon.png" alt="Reflection Mode icon" width="160" />
</p>

[中文](README.zh-CN.md) | English

`reflection-mode` is a local plugin for Codex and Claude Code. It turns completed tasks, user corrections, and repeated failure patterns into reviewable guidance for future agent work.

Reflection Mode helps agents extract reusable lessons from concrete evidence. It does not train the model, change model weights, or guarantee that future sessions will remember a lesson. A lesson only affects future work after it is confirmed and written into a real host memory surface, project document, or skill reference that the next session actually loads.

## Inspiration

Reflection Mode started from a simple observation: people grow by reflecting on past experience. Without reflection, the same mistakes tend to repeat. AI agents have a similar problem. They can finish a task, receive corrections, or fail in a familiar way, but still lose the lesson unless it is turned into reusable guidance.

This plugin was built to make that review loop explicit. It treats completed tasks, user corrections, and repeated failures as evidence, then extracts lessons that can change future behavior when they are later confirmed and placed in a loaded context. When a lesson is durable enough, Reflection Mode also decides whether to skip saving it, keep it as a candidate, or write it when the host and user permit it.

## What It Does

- Reflects on completed work, corrections, rework, and repeated mistakes.
- Extracts reusable lessons that can be confirmed and placed in future context.
- Distinguishes one-off incidents from durable operating guidance.
- Classifies persistence decisions as `skip`, `candidate inbox`, or host-authorized write.
- Grades each candidate with `signal_strength: high | medium | low` and keeps the supporting evidence explicit.
- Carries metadata such as evidence count, timestamps, project scope, dedupe keys, and stale-review hints when writing or returning candidates.
- Supports a lightweight pending-candidate inbox when the host and user permissions allow it.
- Provides Codex and Claude Code manifests from the same skill payload; platform behavior still depends on each host's plugin, context, and permission model.

## Persistence Guardrails

- Reflection candidates are an inbox, not memory. Pending records do not improve future work unless a user or host-approved flow confirms them and writes them to a loaded target.
- Automatic writing is intentionally narrow: it requires `signal_strength: high`, at least two structured evidence items, a clear target, dedupe metadata, and explicit host permission.
- Project-specific records should stay under the project-local `.reflection-mode/` queue. Global queues are reserved for stable user preferences or cross-project process rules.
- Saved lessons include freshness metadata so older repo, API, or workflow assumptions can be marked for review.
- Status or list requests only read real host-accessible records; the plugin should not invent reflection history.
- The JSONL queue has no standalone retrieval engine. Use `scripts/reflection_queue.py` to list, confirm, skip, dedupe, export, and garbage-collect records before promoting them to memory or docs.

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
├── .github/workflows/
│   └── validate.yml
├── scripts/
│   ├── reflection_queue.py
│   └── validate_plugin.py
└── skills/reflection-mode/
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── assets/
    │   ├── reflection-mode-icon.png
    │   └── reflection-mode-icon-small.png
    ├── references/
    │   ├── reflective-practice.md
    │   ├── persistence-decision.md
    │   └── output-contract.md
    └── schemas/
        ├── candidate-record.schema.json
        └── event-record.schema.json
```

## Runtime Entries

- `skills/reflection-mode/SKILL.md`: trigger boundaries, core workflow, and runtime rules.
- `references/reflective-practice.md`: reflection method and lesson quality standards.
- `references/persistence-decision.md`: persistence decision rules.
- `references/output-contract.md`: structured output and persistence handling format.
- `agents/openai.yaml`: Codex skill list metadata.
- `assets/`: plugin card icons.
- `scripts/reflection_queue.py`: queue management for listing, confirming, skipping, exporting, deduping, and trimming candidate inbox records.
- `scripts/validate_plugin.py`: repository-level contract checks for manifests, docs, and runtime references.
- `skills/reflection-mode/schemas/`: JSON Schemas for pending candidates and reflection event records.

## Installation

The intended installation path is agent-assisted, but `llms.txt` is an installation plan, not a trusted script. Open [llms.txt](llms.txt), ask your agent to summarize the commands and target paths first, then approve the write steps only after reviewing them.

The agent should handle the flow with explicit checkpoints: verifying the repository URL, cloning or updating the source, preparing a local marketplace, installing the plugin, and running validation checks. Do not paste unknown `llms.txt` content into an agent and allow shell execution without review, especially when it contains `git`, `rsync --delete`, marketplace registration, or plugin install commands.

After installation, start a new Codex thread so the plugin context is loaded.

## Validation

```bash
python3 scripts/validate_plugin.py
python3 -m json.tool .codex-plugin/plugin.json
python3 -m json.tool .claude-plugin/plugin.json
python3 -m json.tool skills/reflection-mode/schemas/candidate-record.schema.json
python3 -m json.tool skills/reflection-mode/schemas/event-record.schema.json
ruby -e 'require "yaml"; text=File.read("skills/reflection-mode/SKILL.md"); YAML.load(text.split(/^---\s*$/,3)[1]); YAML.load_file("skills/reflection-mode/agents/openai.yaml"); puts "yaml ok"'
git diff --check
```

If you maintain the plugin with Codex's plugin creator tooling, run its plugin validation script from your local tool installation as an additional check.
