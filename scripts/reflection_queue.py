#!/usr/bin/env python3
"""Manage Reflection Mode candidate inbox records."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUS_VALUES = {"pending", "confirmed", "skipped", "written", "stale_review"}
TARGET_VALUES = {"memory", "skill-reference", "project-doc", "candidate-queue", "other"}
SIGNAL_RANK = {"high": 3, "medium": 2, "low": 1}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def short_hash(text: str, size: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:size]


def default_project_id(path: Path) -> str:
    root = path.resolve()
    if root.name == ".reflection-mode":
        root = root.parent
    return f"{root.name}-{short_hash(str(root), 8)}"


def parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def resolve_queue(args: argparse.Namespace) -> Path:
    if args.queue:
        return Path(args.queue).expanduser()
    if getattr(args, "global_queue", False):
        host = getattr(args, "host", "codex")
        base = ".claude" if host == "claude" else ".codex"
        return Path.home() / base / "reflection-mode" / "pending.jsonl"
    return Path.cwd() / ".reflection-mode" / "pending.jsonl"


def events_path(queue_path: Path) -> Path:
    return queue_path.parent / "events.jsonl"


def read_records(path: Path, allow_missing: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if allow_missing:
            return []
        raise SystemExit(f"queue does not exist: {path}")

    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise SystemExit(f"{path}:{lineno}: expected JSON object")
            records.append(record)
    return records


def write_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    tmp.replace(path)


def append_event(queue_path: Path, event: dict[str, Any]) -> None:
    path = events_path(queue_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def candidate_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("project_id", "")),
        str(record.get("canonical_key", "")),
        str(record.get("lesson_hash", "")),
    )


def evidence_count_matches(record: dict[str, Any]) -> bool:
    evidence = record.get("evidence")
    if not isinstance(evidence, list):
        return False
    return record.get("evidence_count") == len(evidence)


def validate_record_shape(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = (
        "id",
        "status",
        "signal_strength",
        "evidence_count",
        "evidence",
        "scope",
        "queue_scope",
        "project_id",
        "canonical_key",
        "lesson_hash",
        "lesson",
        "next_action",
        "target",
    )
    for field in required:
        if field not in record:
            errors.append(f"{record.get('id', '<missing id>')}: missing {field}")
    if record.get("status") not in STATUS_VALUES:
        errors.append(f"{record.get('id', '<missing id>')}: invalid status")
    if record.get("target") not in TARGET_VALUES:
        errors.append(f"{record.get('id', '<missing id>')}: invalid target")
    if record.get("queue_scope") not in {"project", "global"}:
        errors.append(f"{record.get('id', '<missing id>')}: invalid queue_scope")
    if not evidence_count_matches(record):
        errors.append(f"{record.get('id', '<missing id>')}: evidence_count does not match evidence length")
    return errors


def sorted_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda item: (
            SIGNAL_RANK.get(str(item.get("signal_strength")), 0),
            parse_datetime(item.get("last_seen")),
        ),
        reverse=True,
    )


def find_record(records: list[dict[str, Any]], record_id: str) -> dict[str, Any]:
    matches = [record for record in records if record.get("id") == record_id]
    if not matches:
        raise SystemExit(f"candidate not found: {record_id}")
    if len(matches) > 1:
        raise SystemExit(f"duplicate candidate id in queue: {record_id}")
    return matches[0]


def event_base(record: dict[str, Any], event_type: str, summary: str) -> dict[str, Any]:
    created_at = utc_now()
    return {
        "schema_version": 1,
        "id": f"reflection-event-{created_at}-{short_hash(str(record.get('id', 'record')))}",
        "created_at": created_at,
        "event_type": event_type,
        "candidate_id": record.get("id"),
        "scope": record.get("scope", "unknown"),
        "queue_scope": record.get("queue_scope", "project"),
        "project_id": record.get("project_id", "unknown"),
        "summary": summary,
        "expires_after_days": 180,
    }


def cmd_list(args: argparse.Namespace) -> int:
    queue = resolve_queue(args)
    records = read_records(queue)
    if args.status:
        records = [record for record in records if record.get("status") == args.status]
    if args.project_id:
        records = [record for record in records if record.get("project_id") == args.project_id]
    records = sorted_records(records)[: args.limit]

    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"queue: {queue}")
    if not records:
        print("no records")
        return 0
    for record in records:
        marker = "!" if not evidence_count_matches(record) else " "
        print(
            f"{marker} {record.get('id')} "
            f"[{record.get('status')}/{record.get('signal_strength')}] "
            f"{record.get('project_id')} :: {record.get('canonical_key')}"
        )
        print(f"  lesson: {record.get('lesson')}")
        print(f"  next: {record.get('next_action')}")
    return 0


def update_status(args: argparse.Namespace, status: str, event_type: str, summary: str) -> int:
    queue = resolve_queue(args)
    records = read_records(queue, allow_missing=False)
    record = find_record(records, args.candidate_id)
    if args.target:
        record["target"] = args.target
    record["status"] = status
    record["last_seen"] = utc_now()
    event = event_base(record, event_type, summary)
    write_records(queue, records)
    append_event(queue, event)
    print(f"{status}: {args.candidate_id}")
    return 0


def cmd_confirm(args: argparse.Namespace) -> int:
    return update_status(args, "confirmed", "candidate_confirmed", args.reason or "Candidate confirmed.")


def cmd_skip(args: argparse.Namespace) -> int:
    return update_status(args, "skipped", "candidate_skipped", args.reason or "Candidate skipped.")


def cmd_write(args: argparse.Namespace) -> int:
    queue = resolve_queue(args)
    records = read_records(queue, allow_missing=False)
    record = find_record(records, args.candidate_id)
    record["status"] = "written"
    record["target"] = args.target
    record["last_seen"] = utc_now()
    lesson_id = args.lesson_id or f"reflection-lesson-{utc_now()}-{short_hash(record.get('lesson', 'lesson'))}"
    event = event_base(record, "lesson_written", args.reason or "Lesson written to target.")
    event.pop("candidate_id", None)
    event["lesson_id"] = lesson_id
    write_records(queue, records)
    append_event(queue, event)
    print(f"written: {args.candidate_id} -> {lesson_id}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    queue = resolve_queue(args)
    project_id = args.project_id or default_project_id(queue.parent)
    created_at = utc_now()
    event = {
        "schema_version": 1,
        "id": f"reflection-event-{created_at}-{short_hash(args.lesson_id)}",
        "created_at": created_at,
        "event_type": "lesson_applied",
        "lesson_id": args.lesson_id,
        "scope": args.scope,
        "queue_scope": args.queue_scope,
        "project_id": project_id,
        "summary": args.summary,
        "outcome_signal": args.outcome_signal,
        "result": args.result or "No additional result recorded.",
        "expires_after_days": args.expires_after_days,
    }
    append_event(queue, event)
    print(f"lesson_applied: {args.lesson_id}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    queue = resolve_queue(args)
    records = read_records(queue)
    if args.status:
        records = [record for record in records if record.get("status") == args.status]
    if args.target:
        records = [record for record in records if record.get("target") == args.target]
    records = sorted_records(records)[: args.limit]

    print(f"# Reflection Mode export\n\nqueue: {queue}\n")
    for record in records:
        print(f"## {record.get('id')}")
        print(f"- status: {record.get('status')}")
        print(f"- target: {record.get('target')}")
        print(f"- scope: {record.get('scope')}")
        print(f"- project_id: {record.get('project_id')}")
        print(f"- canonical_key: {record.get('canonical_key')}")
        print(f"- lesson_hash: {record.get('lesson_hash')}")
        print(f"- signal_strength: {record.get('signal_strength')}")
        print(f"- lesson: {record.get('lesson')}")
        print(f"- next_action: {record.get('next_action')}")
        print("")
    return 0


def cmd_dedupe(args: argparse.Namespace) -> int:
    queue = resolve_queue(args)
    records = read_records(queue, allow_missing=False)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in records:
        if args.status and record.get("status") != args.status:
            continue
        grouped.setdefault(candidate_key(record), []).append(record)

    changed = 0
    for key, group in grouped.items():
        if key == ("", "", "") or len(group) <= 1:
            continue
        keep = sorted_records(group)[0]
        for duplicate in group:
            if duplicate is keep:
                continue
            duplicate["status"] = "skipped"
            duplicate["last_seen"] = utc_now()
            append_event(queue, event_base(duplicate, "candidate_skipped", f"Duplicate of {keep.get('id')}."))
            changed += 1

    if changed:
        write_records(queue, records)
    print(f"deduped: {changed} duplicate records marked skipped")
    return 0


def cmd_gc(args: argparse.Namespace) -> int:
    queue = resolve_queue(args)
    records = read_records(queue, allow_missing=False)
    now = datetime.now(timezone.utc)
    pending = [record for record in records if record.get("status") == "pending"]
    keep = set()

    for record in sorted_records(pending)[: args.max_pending]:
        keep.add(record.get("id"))

    changed = 0
    for record in pending:
        age_days = (now - parse_datetime(record.get("last_seen"))).days
        should_skip = record.get("id") not in keep or age_days > args.keep_days
        if should_skip:
            record["status"] = "skipped"
            record["last_seen"] = utc_now()
            append_event(queue, event_base(record, "candidate_skipped", "Garbage collection skipped stale or excess pending candidate."))
            changed += 1

    if changed:
        write_records(queue, records)
    print(f"gc: {changed} pending records marked skipped")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    queue = resolve_queue(args)
    records = read_records(queue)
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str, str]] = set()
    for record in records:
        record_id = str(record.get("id", ""))
        if record_id in seen_ids:
            errors.append(f"{record_id}: duplicate id")
        seen_ids.add(record_id)
        key = candidate_key(record)
        if key != ("", "", "") and record.get("status") == "pending":
            if key in seen_keys:
                errors.append(f"{record_id}: duplicate pending canonical key")
            seen_keys.add(key)
        errors.extend(validate_record_shape(record))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"queue validation ok: {queue}")
    return 0


def add_queue_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--queue", help="Path to pending.jsonl. Defaults to .reflection-mode/pending.jsonl.")
    parser.add_argument("--global", dest="global_queue", action="store_true", help="Use the host global queue.")
    parser.add_argument("--host", choices=("codex", "claude"), default="codex", help="Global host queue to use.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List candidate inbox records.")
    add_queue_args(list_parser)
    list_parser.add_argument("--status", choices=sorted(STATUS_VALUES), default="pending")
    list_parser.add_argument("--project-id")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=cmd_list)

    confirm_parser = subparsers.add_parser("confirm", help="Mark a candidate as confirmed.")
    add_queue_args(confirm_parser)
    confirm_parser.add_argument("candidate_id")
    confirm_parser.add_argument("--target", choices=sorted(TARGET_VALUES))
    confirm_parser.add_argument("--reason")
    confirm_parser.set_defaults(func=cmd_confirm)

    skip_parser = subparsers.add_parser("skip", help="Mark a candidate as skipped.")
    add_queue_args(skip_parser)
    skip_parser.add_argument("candidate_id")
    skip_parser.add_argument("--reason")
    skip_parser.set_defaults(func=cmd_skip)

    write_parser = subparsers.add_parser("write", help="Mark a candidate as written to a target.")
    add_queue_args(write_parser)
    write_parser.add_argument("candidate_id")
    write_parser.add_argument("--target", choices=sorted(TARGET_VALUES), required=True)
    write_parser.add_argument("--lesson-id")
    write_parser.add_argument("--reason")
    write_parser.set_defaults(func=cmd_write)

    apply_parser = subparsers.add_parser("apply", help="Record that a saved lesson was applied.")
    add_queue_args(apply_parser)
    apply_parser.add_argument("lesson_id")
    apply_parser.add_argument("--scope", required=True)
    apply_parser.add_argument("--queue-scope", choices=("project", "global"), default="project")
    apply_parser.add_argument("--project-id")
    apply_parser.add_argument("--summary", required=True)
    apply_parser.add_argument("--outcome-signal", choices=("user_confirmed", "test_passed", "review_prevented", "unknown"), default="unknown")
    apply_parser.add_argument("--result")
    apply_parser.add_argument("--expires-after-days", type=int, default=180)
    apply_parser.set_defaults(func=cmd_apply)

    export_parser = subparsers.add_parser("export", help="Export candidates as Markdown.")
    add_queue_args(export_parser)
    export_parser.add_argument("--status", choices=sorted(STATUS_VALUES), default="confirmed")
    export_parser.add_argument("--target", choices=sorted(TARGET_VALUES))
    export_parser.add_argument("--limit", type=int, default=50)
    export_parser.set_defaults(func=cmd_export)

    dedupe_parser = subparsers.add_parser("dedupe", help="Mark duplicate pending records as skipped.")
    add_queue_args(dedupe_parser)
    dedupe_parser.add_argument("--status", choices=sorted(STATUS_VALUES), default="pending")
    dedupe_parser.set_defaults(func=cmd_dedupe)

    gc_parser = subparsers.add_parser("gc", help="Trim stale or excess pending records.")
    add_queue_args(gc_parser)
    gc_parser.add_argument("--max-pending", type=int, default=200)
    gc_parser.add_argument("--keep-days", type=int, default=180)
    gc_parser.set_defaults(func=cmd_gc)

    validate_parser = subparsers.add_parser("validate", help="Validate queue shape and duplicate keys.")
    add_queue_args(validate_parser)
    validate_parser.set_defaults(func=cmd_validate)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
