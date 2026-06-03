#!/usr/bin/env python3
"""Validate Reflection Mode plugin packaging and runtime contracts."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft7Validator
except ModuleNotFoundError:
    jsonschema = None
    Draft7Validator = None


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SCHEMA_PATH = "skills/reflection-mode/schemas/candidate-record.schema.json"
EVENT_SCHEMA_PATH = "skills/reflection-mode/schemas/event-record.schema.json"


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
        "读取候选上下文",
        "status: pending",
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
        "events.archive.jsonl",
        "expires_after_days",
        "stale_after_days",
        "stale_review",
        "provisional: true",
        "无法写入候选队列，请手动保存",
    ):
        check(required in persistence, f"persistence-decision.md missing {required}", errors)

    output = read_text("skills/reflection-mode/references/output-contract.md")
    for required in (
        "`signal_strength`",
        "candidate_record",
        CANDIDATE_SCHEMA_PATH,
        EVENT_SCHEMA_PATH,
        "experience_type",
        "code-pattern",
        "$reflection-list",
        "--status pending|confirmed|skipped|written|stale_review",
        "--limit <n>",
        "$reflection-list delete <candidate_id>",
        "$reflection-list export",
        "events.archive.jsonl",
        "expires_after_days",
        "candidate_id",
        "lesson_id",
        "code_pattern",
        "/reflect status",
    ):
        check(required in output, f"output-contract.md missing {required}", errors)

    reflective = read_text("skills/reflection-mode/references/reflective-practice.md")
    for required in ("reflection_depth_score", "总分上限封顶为 10", "条件只部分满足", "## 效果追踪", "跨会话重复模式"):
        check(required in reflective, f"reflective-practice.md missing {required}", errors)


def validate_schemas(errors: list[str]) -> None:
    candidate = load_json(CANDIDATE_SCHEMA_PATH)
    event = load_json(EVENT_SCHEMA_PATH)

    for schema_name, schema in (
        ("candidate-record.schema.json", candidate),
        ("event-record.schema.json", event),
    ):
        check(schema.get("$schema") == "http://json-schema.org/draft-07/schema#", f"{schema_name}: wrong draft", errors)
        check(schema.get("type") == "object", f"{schema_name}: root type must be object", errors)
        check(schema.get("additionalProperties") is False, f"{schema_name}: additionalProperties must be false", errors)
        check(isinstance(schema.get("required"), list) and schema["required"], f"{schema_name}: required fields missing", errors)
        check(isinstance(schema.get("properties"), dict) and schema["properties"], f"{schema_name}: properties missing", errors)
        if Draft7Validator is not None:
            try:
                Draft7Validator.check_schema(schema)
            except jsonschema.SchemaError as exc:
                errors.append(f"{schema_name}: invalid Draft-07 schema: {exc.message}")

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
        "provisional",
        "status",
    ):
        check(required in candidate_required, f"candidate schema missing required field {required}", errors)

    candidate_properties = candidate.get("properties", {})
    check("code_pattern" in candidate_properties, "candidate schema missing code_pattern property", errors)
    check("allOf" in candidate, "candidate schema missing conditional code_pattern rules", errors)
    check(
        "code_pattern" in json.dumps(candidate.get("allOf", []), ensure_ascii=False),
        "candidate schema conditional rules must mention code_pattern",
        errors,
    )

    for required in ("schema_version", "id", "created_at", "event_type", "scope", "summary", "expires_after_days"):
        check(required in event_required, f"event schema missing required field {required}", errors)

    event_rules = json.dumps(event.get("allOf", []), ensure_ascii=False)
    check("allOf" in event, "event schema missing conditional id rules", errors)
    check("candidate_id" in event_rules, "event schema conditional rules must mention candidate_id", errors)
    check("lesson_id" in event_rules, "event schema conditional rules must mention lesson_id", errors)
    check("stale_review" in event_rules, "event schema conditional rules must mention stale_review", errors)
    event_properties = event.get("properties", {})
    check(
        "pattern" in event_properties.get("candidate_id", {}),
        "event schema candidate_id must enforce an id pattern",
        errors,
    )
    check(
        "minLength" in event_properties.get("lesson_id", {}),
        "event schema lesson_id must be non-empty",
        errors,
    )


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
    if "allOf" in schema:
        for index, item_schema in enumerate(schema["allOf"]):
            if isinstance(item_schema, dict):
                validate_instance(instance, item_schema, f"{name}.allOf[{index}]", errors)

    if "anyOf" in schema:
        any_valid = False
        for item_schema in schema["anyOf"]:
            if not isinstance(item_schema, dict):
                continue
            branch_errors: list[str] = []
            validate_instance(instance, item_schema, name, branch_errors)
            if not branch_errors:
                any_valid = True
                break
        check(any_valid, f"{name}: value does not match anyOf", errors)

    if "if" in schema and isinstance(schema["if"], dict):
        condition_errors: list[str] = []
        validate_instance(instance, schema["if"], name, condition_errors)
        if not condition_errors and isinstance(schema.get("then"), dict):
            validate_instance(instance, schema["then"], f"{name}.then", errors)

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


def instance_errors(instance: object, schema: dict, name: str) -> list[str]:
    errors: list[str] = []
    if Draft7Validator is not None:
        validator = Draft7Validator(schema, format_checker=jsonschema.FormatChecker())
        for error in sorted(validator.iter_errors(instance), key=lambda item: item.path):
            path = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{name}.{path}: {error.message}")
    else:
        validate_instance(instance, schema, name, errors)
    return errors


def check_schema_case(instance: object, schema: dict, name: str, should_pass: bool, errors: list[str]) -> None:
    case_errors = instance_errors(instance, schema, name)
    if should_pass:
        errors.extend(case_errors)
    else:
        check(bool(case_errors), f"{name}: invalid fixture unexpectedly passed schema validation", errors)


def validate_schema_fixtures(errors: list[str]) -> None:
    candidate_schema = load_json(CANDIDATE_SCHEMA_PATH)
    event_schema = load_json(EVENT_SCHEMA_PATH)

    base_candidate = {
        "schema_version": 1,
        "id": "reflection-candidate-2026-06-03T06:00:00Z-test",
        "created_at": "2026-06-03T06:00:00Z",
        "last_seen": "2026-06-03T06:00:00Z",
        "decision": "candidate",
        "signal_strength": "medium",
        "evidence_count": 1,
        "correction_count": 1,
        "experience_type": "repo-contract",
        "scope": "repo-or-global-scope",
        "stale_after_days": 90,
        "applies_to": ["future trigger"],
        "lesson": "Reusable lesson text.",
        "next_action": "Apply the reusable lesson.",
        "target": "skill-reference",
        "evidence": ["Short evidence summary."],
        "provisional": False,
        "status": "pending",
    }
    code_candidate = {
        **base_candidate,
        "id": "reflection-candidate-2026-06-03T06:00:00Z-code",
        "experience_type": "code-pattern",
        "code_pattern": {
            "language": "typescript",
            "pattern": "return withRetry(() => client.request(input));",
            "applies_when": "The same retryable request pattern appears.",
            "does_not_apply_when": "The endpoint is non-idempotent.",
        },
    }
    code_candidate_missing_pattern = {key: value for key, value in code_candidate.items() if key != "code_pattern"}
    non_code_candidate_with_pattern = {**code_candidate, "experience_type": "repo-contract"}

    check_schema_case(base_candidate, candidate_schema, "candidate fixture plain", True, errors)
    check_schema_case(code_candidate, candidate_schema, "candidate fixture code-pattern", True, errors)
    check_schema_case(code_candidate_missing_pattern, candidate_schema, "candidate fixture missing code_pattern", False, errors)
    check_schema_case(non_code_candidate_with_pattern, candidate_schema, "candidate fixture unexpected code_pattern", False, errors)

    base_event = {
        "schema_version": 1,
        "id": "reflection-event-2026-06-03T06:00:00Z-test",
        "created_at": "2026-06-03T06:00:00Z",
        "event_type": "candidate_confirmed",
        "candidate_id": "reflection-candidate-2026-06-03T06:00:00Z-test",
        "scope": "repo-or-global-scope",
        "summary": "Candidate confirmed.",
        "expires_after_days": 180,
    }
    candidate_created_event = {
        **base_event,
        "id": "reflection-event-2026-06-03T06:00:00Z-created",
        "event_type": "candidate_created",
        "summary": "Candidate created.",
    }
    candidate_skipped_event = {
        **base_event,
        "id": "reflection-event-2026-06-03T06:00:00Z-skipped",
        "event_type": "candidate_skipped",
        "summary": "Candidate skipped.",
    }
    candidate_event_missing_id = {key: value for key, value in base_event.items() if key != "candidate_id"}
    candidate_event_empty_id = {**base_event, "candidate_id": ""}
    lesson_event = {
        **base_event,
        "id": "reflection-event-2026-06-03T06:00:00Z-lesson",
        "event_type": "lesson_applied",
        "lesson_id": "reflection-lesson-2026-06-03T06:00:00Z-test",
        "summary": "Lesson applied.",
    }
    lesson_event.pop("candidate_id")
    lesson_written_event = {
        **lesson_event,
        "id": "reflection-event-2026-06-03T06:00:00Z-written",
        "event_type": "lesson_written",
        "summary": "Lesson written.",
    }
    lesson_event_missing_id = {key: value for key, value in lesson_event.items() if key != "lesson_id"}
    lesson_event_empty_id = {**lesson_event, "lesson_id": ""}
    stale_event = {
        **base_event,
        "id": "reflection-event-2026-06-03T06:00:00Z-stale",
        "event_type": "stale_review",
        "summary": "Candidate needs stale review.",
    }
    stale_event_missing_id = {key: value for key, value in stale_event.items() if key != "candidate_id"}
    stale_lesson_event = {
        **lesson_event,
        "id": "reflection-event-2026-06-03T06:00:00Z-stale-lesson",
        "event_type": "stale_review",
        "summary": "Lesson needs stale review.",
    }

    check_schema_case(base_event, event_schema, "event fixture candidate", True, errors)
    check_schema_case(candidate_created_event, event_schema, "event fixture candidate_created", True, errors)
    check_schema_case(candidate_skipped_event, event_schema, "event fixture candidate_skipped", True, errors)
    check_schema_case(candidate_event_missing_id, event_schema, "event fixture missing candidate_id", False, errors)
    check_schema_case(candidate_event_empty_id, event_schema, "event fixture empty candidate_id", False, errors)
    check_schema_case(lesson_event, event_schema, "event fixture lesson", True, errors)
    check_schema_case(lesson_written_event, event_schema, "event fixture lesson_written", True, errors)
    check_schema_case(lesson_event_missing_id, event_schema, "event fixture missing lesson_id", False, errors)
    check_schema_case(lesson_event_empty_id, event_schema, "event fixture empty lesson_id", False, errors)
    check_schema_case(stale_event, event_schema, "event fixture stale_review", True, errors)
    check_schema_case(stale_lesson_event, event_schema, "event fixture stale_review lesson_id", True, errors)
    check_schema_case(stale_event_missing_id, event_schema, "event fixture stale_review missing id", False, errors)


def looks_like_candidate_record(example: object) -> bool:
    if not isinstance(example, dict):
        return False
    if str(example.get("id", "")).startswith("reflection-candidate-"):
        return True
    if example.get("decision") == "candidate":
        return True
    if "event_type" in example:
        return False

    candidate_fields = {
        "schema_version",
        "created_at",
        "last_seen",
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
        "provisional",
        "status",
    }
    return len(candidate_fields.intersection(example.keys())) >= 8


def looks_like_event_record(example: object) -> bool:
    return isinstance(example, dict) and (
        str(example.get("id", "")).startswith("reflection-event-") or "event_type" in example
    )


def validate_example_against_schema(example: object, schema: dict, name: str, errors: list[str]) -> None:
    if Draft7Validator is not None:
        validator = Draft7Validator(schema, format_checker=jsonschema.FormatChecker())
        for error in sorted(validator.iter_errors(example), key=lambda item: item.path):
            path = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{name}.{path}: {error.message}")
    else:
        validate_instance(example, schema, name, errors)


def validate_output_contract_examples(errors: list[str]) -> None:
    blocks = json_blocks("skills/reflection-mode/references/output-contract.md")
    candidate_schema = load_json(CANDIDATE_SCHEMA_PATH)
    event_schema = load_json(EVENT_SCHEMA_PATH)
    candidate_examples = 0
    event_examples = 0

    for line, text in blocks:
        try:
            example = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"output-contract.md:{line}: invalid JSON example: {exc}")
            continue

        if looks_like_candidate_record(example):
            candidate_examples += 1
            validate_example_against_schema(example, candidate_schema, f"output-contract.md:{line}", errors)
            if isinstance(example, dict):
                check(
                    example.get("experience_type") != "code-pattern" or "code_pattern" in example,
                    f"output-contract.md:{line}: code-pattern candidates must include code_pattern",
                    errors,
                )
                check(
                    "code_pattern" not in example or example.get("experience_type") == "code-pattern",
                    f"output-contract.md:{line}: code_pattern is only valid for experience_type code-pattern",
                    errors,
                )
            continue

        if looks_like_event_record(example):
            event_examples += 1
            validate_example_against_schema(example, event_schema, f"output-contract.md:{line}", errors)

    check(candidate_examples >= 1, "output-contract.md must contain at least one candidate_record JSON example", errors)
    check(event_examples >= 1, "output-contract.md must contain at least one event_record JSON example", errors)


def validate_docs(errors: list[str]) -> None:
    readme = read_text("README.md")
    readme_zh = read_text("README.zh-CN.md")
    for required in ("## What It Does", "## Project Structure", "skills/reflection-mode/schemas/", "## Installation", "## Validation"):
        check(required in readme, f"README.md missing {required}", errors)
    for required in ("## 项目结构", "skills/reflection-mode/schemas/", "## 关键规则", "## 安装", "## 验证"):
        check(required in readme_zh, f"README.zh-CN.md missing {required}", errors)

    check("GitHub About" not in readme, "README.md must not include GitHub About text", errors)
    check("GitHub About" not in readme_zh, "README.zh-CN.md must not include GitHub About text", errors)

    llms = read_text("llms.txt")
    for required in (
        "pending.jsonl",
        "validate",
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        CANDIDATE_SCHEMA_PATH,
        EVENT_SCHEMA_PATH,
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
        CANDIDATE_SCHEMA_PATH,
        EVENT_SCHEMA_PATH,
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
    validate_schema_fixtures(errors)
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
