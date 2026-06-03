#!/usr/bin/env python3
"""Validate Reflection Mode plugin packaging and runtime contracts."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_json(path: str) -> dict:
    with (ROOT / path).open(encoding="utf-8") as handle:
        return json.load(handle)


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_markdown_fences(path: str, errors: list[str]) -> None:
    stack: list[tuple[str, int, int]] = []
    fence_re = re.compile(r"^(`{3,}|~{3,})")
    for lineno, line in enumerate(read_text(path).splitlines(), start=1):
        match = fence_re.match(line)
        if not match:
            continue

        marker = match.group(1)
        char = marker[0]
        length = len(marker)
        if stack and stack[-1][0] == char and length >= stack[-1][1]:
            stack.pop()
        else:
            stack.append((char, length, lineno))

    check(not stack, f"{path}: unclosed markdown fence opened at line {stack[-1][2] if stack else '?'}", errors)


def check_trailing_whitespace(path: str, errors: list[str]) -> None:
    for lineno, line in enumerate(read_text(path).splitlines(), start=1):
        check(line.rstrip(" \t") == line, f"{path}: trailing whitespace at line {lineno}", errors)


def json_blocks(path: str) -> list[tuple[int, str]]:
    blocks: list[tuple[int, str]] = []
    in_json = False
    start_line = 0
    current: list[str] = []

    for lineno, line in enumerate(read_text(path).splitlines(), start=1):
        if not in_json and line == "```json":
            in_json = True
            start_line = lineno + 1
            current = []
            continue
        if in_json and line == "```":
            blocks.append((start_line, "\n".join(current)))
            in_json = False
            continue
        if in_json:
            current.append(line)

    return blocks


def parse_frontmatter(path: str, errors: list[str]) -> dict[str, str]:
    text = read_text(path)
    parts = text.split("---", 2)
    check(text.startswith("---"), f"{path}: missing YAML frontmatter", errors)
    check(len(parts) >= 3, f"{path}: incomplete YAML frontmatter", errors)
    if len(parts) < 3:
        return {}

    frontmatter: dict[str, str] = {}
    for line in parts[1].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            errors.append(f"{path}: invalid frontmatter line: {line}")
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip()
    return frontmatter


def validate_manifests(errors: list[str]) -> None:
    codex = load_json(".codex-plugin/plugin.json")
    claude = load_json(".claude-plugin/plugin.json")

    for key in ("name", "version", "description", "skills"):
        check(codex.get(key) == claude.get(key), f"manifest mismatch for {key}", errors)

    check(codex.get("name") == "reflection-mode", "Codex manifest name must be reflection-mode", errors)
    check(codex.get("skills") == "./skills/", "Codex manifest skills path must be ./skills/", errors)
    check("interface" in codex, "Codex manifest must include interface metadata", errors)
    check("interface" not in claude, "Claude manifest must not include Codex-only interface metadata", errors)
    check(
        re.match(r"^\d+\.\d+\.\d+\+codex\.\d{14}$", str(codex.get("version", ""))) is not None,
        "manifest version must include +codex.YYYYMMDDHHMMSS cachebuster",
        errors,
    )


def validate_skill(errors: list[str]) -> None:
    fm = parse_frontmatter("skills/reflection-mode/SKILL.md", errors)
    check(fm.get("name") == "reflection-mode", "SKILL.md frontmatter name must be reflection-mode", errors)
    check(bool(fm.get("description")), "SKILL.md frontmatter description is required", errors)

    skill = read_text("skills/reflection-mode/SKILL.md")
    for required in (
        "signal_strength",
        "evidence_count >= 2",
        "stale_review",
        "宿主写入能力未知",
        "references/persistence-decision.md",
        "references/output-contract.md",
    ):
        check(required in skill, f"SKILL.md missing required contract text: {required}", errors)

    agent_yaml = read_text("skills/reflection-mode/agents/openai.yaml")
    for required in ("display_name:", "short_description:", "default_prompt:", "allow_implicit_invocation: true"):
        check(required in agent_yaml, f"agents/openai.yaml missing {required}", errors)


def validate_references(errors: list[str]) -> None:
    persistence = read_text("skills/reflection-mode/references/persistence-decision.md")
    for required in (
        "## 信号强度",
        "`signal_strength`",
        "`evidence_count >= 2`",
        "宿主写入权限",
        "pending.jsonl",
        "events.jsonl",
        "stale_after_days",
        "stale_review",
    ):
        check(required in persistence, f"persistence-decision.md missing {required}", errors)

    output = read_text("skills/reflection-mode/references/output-contract.md")
    for required in (
        "`signal_strength`",
        "candidate_record",
        "schemas/candidate-record.schema.json",
        "schemas/event-record.schema.json",
        "experience_type",
        "code-pattern",
        "$reflection-list",
        "/reflect status",
    ):
        check(required in output, f"output-contract.md missing {required}", errors)

    reflective = read_text("skills/reflection-mode/references/reflective-practice.md")
    for required in ("reflection_depth_score", "## 效果追踪", "跨会话重复模式"):
        check(required in reflective, f"reflective-practice.md missing {required}", errors)


def validate_schemas(errors: list[str]) -> None:
    candidate = load_json("schemas/candidate-record.schema.json")
    event = load_json("schemas/event-record.schema.json")

    for schema_name, schema in (
        ("candidate-record.schema.json", candidate),
        ("event-record.schema.json", event),
    ):
        check(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{schema_name}: wrong draft", errors)
        check(schema.get("type") == "object", f"{schema_name}: root type must be object", errors)
        check(schema.get("additionalProperties") is False, f"{schema_name}: additionalProperties must be false", errors)
        check(isinstance(schema.get("required"), list) and schema["required"], f"{schema_name}: required fields missing", errors)
        check(isinstance(schema.get("properties"), dict) and schema["properties"], f"{schema_name}: properties missing", errors)

    candidate_required = set(candidate.get("required", []))
    event_required = set(event.get("required", []))

    for required in (
        "schema_version",
        "id",
        "created_at",
        "last_seen",
        "decision",
        "signal_strength",
        "evidence_count",
        "correction_count",
        "experience_type",
        "scope",
        "stale_after_days",
        "applies_to",
        "lesson",
        "next_action",
        "target",
        "evidence",
        "status",
    ):
        check(required in candidate_required, f"candidate schema missing required field {required}", errors)

    for required in ("schema_version", "id", "created_at", "event_type", "scope", "summary"):
        check(required in event_required, f"event schema missing required field {required}", errors)


def validate_type(value: object, expected_type: object) -> bool:
    if isinstance(expected_type, list):
        return any(validate_type(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True


def validate_date_time(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "T" in value


def validate_instance(instance: object, schema: dict, name: str, errors: list[str]) -> None:
    expected_type = schema.get("type")
    if expected_type is not None:
        check(validate_type(instance, expected_type), f"{name}: expected type {expected_type}", errors)
        if not validate_type(instance, expected_type):
            return

    if "const" in schema:
        check(instance == schema["const"], f"{name}: expected const {schema['const']!r}", errors)
    if "enum" in schema:
        check(instance in schema["enum"], f"{name}: value {instance!r} is not in enum", errors)
    if "minimum" in schema and isinstance(instance, (int, float)) and not isinstance(instance, bool):
        check(instance >= schema["minimum"], f"{name}: value is below minimum {schema['minimum']}", errors)
    if "minLength" in schema and isinstance(instance, str):
        check(len(instance) >= schema["minLength"], f"{name}: string shorter than minLength", errors)
    if "pattern" in schema and isinstance(instance, str):
        check(re.match(schema["pattern"], instance) is not None, f"{name}: value does not match pattern", errors)
    if schema.get("format") == "date-time":
        check(validate_date_time(instance), f"{name}: value is not date-time", errors)

    if isinstance(instance, list):
        if "minItems" in schema:
            check(len(instance) >= schema["minItems"], f"{name}: array shorter than minItems", errors)
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                validate_instance(item, item_schema, f"{name}[{index}]", errors)

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for field in required:
            check(field in instance, f"{name}: missing required field {field}", errors)
        if schema.get("additionalProperties") is False:
            allowed = set(schema.get("properties", {}).keys())
            for field in instance:
                check(field in allowed, f"{name}: unexpected field {field}", errors)
        for field, field_schema in schema.get("properties", {}).items():
            if field in instance and isinstance(field_schema, dict):
                validate_instance(instance[field], field_schema, f"{name}.{field}", errors)


def validate_output_contract_examples(errors: list[str]) -> None:
    blocks = json_blocks("skills/reflection-mode/references/output-contract.md")
    check(len(blocks) == 1, "output-contract.md must contain exactly one JSON example", errors)
    if not blocks:
        return

    line, text = blocks[0]
    try:
        example = json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"output-contract.md:{line}: invalid JSON example: {exc}")
        return

    validate_instance(example, load_json("schemas/candidate-record.schema.json"), f"output-contract.md:{line}", errors)


def validate_docs(errors: list[str]) -> None:
    readme = read_text("README.md")
    readme_zh = read_text("README.zh-CN.md")
    for required in ("## What It Does", "## Project Structure", "schemas/", "## Installation", "## Validation"):
        check(required in readme, f"README.md missing {required}", errors)
    for required in ("## 项目结构", "schemas/", "## 关键规则", "## 安装", "## 验证"):
        check(required in readme_zh, f"README.zh-CN.md missing {required}", errors)

    check("GitHub About" not in readme, "README.md must not include GitHub About text", errors)
    check("GitHub About" not in readme_zh, "README.zh-CN.md must not include GitHub About text", errors)

    llms = read_text("llms.txt")
    for required in (
        "pending.jsonl",
        "validate",
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        "schemas/candidate-record.schema.json",
        "schemas/event-record.schema.json",
    ):
        check(required in llms, f"llms.txt missing {required}", errors)


def main() -> int:
    errors: list[str] = []

    markdown_paths = (
        "README.md",
        "README.zh-CN.md",
        "llms.txt",
        "skills/reflection-mode/SKILL.md",
        "skills/reflection-mode/references/reflective-practice.md",
        "skills/reflection-mode/references/persistence-decision.md",
        "skills/reflection-mode/references/output-contract.md",
    )
    text_paths = markdown_paths + (
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        ".github/workflows/validate.yml",
        "schemas/candidate-record.schema.json",
        "schemas/event-record.schema.json",
        "scripts/validate_plugin.py",
        "skills/reflection-mode/agents/openai.yaml",
    )

    for path in markdown_paths:
        check_markdown_fences(path, errors)

    for path in text_paths:
        check_trailing_whitespace(path, errors)

    validate_manifests(errors)
    validate_skill(errors)
    validate_references(errors)
    validate_schemas(errors)
    validate_output_contract_examples(errors)
    validate_docs(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("plugin validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
