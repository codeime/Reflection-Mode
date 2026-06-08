# Output Contract

反思输出应该简洁、基于证据、可复用。除非用户明确要求长篇叙事，否则不要写成流水账。只有用户要求结构化反思、任务高风险、问题重复出现，或正在判断是否写入时，才使用完整格式。候选队列只是 inbox，不是长期记忆；pending 记录只有被确认并写入真实加载面后，才会影响后续会话。

所有结构化输出都必须包含 `signal_strength`，并说明它来自哪些结构化证据。`signal_strength` 的取值只能是 `high`、`medium` 或 `low`。

## 默认结构

需要结构化反思时，使用这个形状：

```text
事实:
- 发生了什么:
- 用户纠正或失败信号:
- 证据不足之处:

经验:
- 可复用判断:
- 适用边界:
- 下次动作:
- experience_type: preference | repo-contract | process | review-rule | code-pattern | other

沉淀:
- 建议: 无需保存 | 候选 inbox 待确认 | 宿主授权写入
- signal_strength: high | medium | low
- evidence_count:
- correction_count:
- 理由:
- 验证信号:
- 目标位置:
- queue_scope: project | global
- project_id:
- canonical_key:
- lesson_hash:
```

## 紧凑结构

用户只要快速反思时，使用这个形状：

```text
经验: ...
下次: ...
沉淀建议: 无需保存 | 候选 inbox 待确认 | 宿主授权写入
signal_strength: high | medium | low
```

## 沉淀处理

用户要求保存、把反思转成产物，或判断出值得宿主授权写入时，使用这个形状：

```text
处理方式: 无需保存 | 候选 inbox 待确认 | 宿主授权写入
目标位置: 长期记忆 | skill reference | 其他明确产物
signal_strength: high | medium | low
metadata:
  created_at:
  last_seen:
  evidence_count:
  correction_count:
  experience_type:
  scope:
  queue_scope:
  project_id:
  canonical_key:
  lesson_hash:
  stale_after_days:
  applies_to:
文本:
...
理由:
...
风险:
...
```

如果处理方式是宿主授权写入，且当前宿主支持对应写入机制并且用户/策略允许，就执行写入并说明结果。不能写入时，退回候选 inbox 待确认，并说明缺少的证据、目标位置或权限。

## 候选队列记录

当宿主允许写入候选队列时，使用 JSONL，每行一个 `candidate_record`。正式字段以 `skills/reflection-mode/schemas/candidate-record.schema.json` 为准。项目经验默认写入 `{project_root}/.reflection-mode/pending.jsonl`；只有稳定用户偏好、跨项目流程规则或用户明确要求全局记录时，才写入用户级目录。

```json
{
  "schema_version": 1,
  "id": "reflection-candidate-2026-06-03T06:00:00Z-a1b2c3",
  "created_at": "2026-06-03T06:00:00Z",
  "last_seen": "2026-06-03T06:00:00Z",
  "decision": "candidate",
  "signal_strength": "medium",
  "evidence_count": 2,
  "correction_count": 1,
  "experience_type": "repo-contract",
  "scope": "repo-or-global-scope",
  "queue_scope": "project",
  "project_id": "repo-reflection-mode",
  "canonical_key": "repo-reflection-mode:repo-contract:validate-before-write",
  "lesson_hash": "sha256:8a4f2c9d1e3b",
  "stale_after_days": 90,
  "applies_to": ["future trigger or task class"],
  "lesson": "Reusable lesson text.",
  "next_action": "How the agent should behave differently.",
  "target": "skill-reference",
  "evidence": [
    {
      "source_type": "user_correction",
      "source_ref": "current conversation",
      "summary": "User corrected the agent's workflow."
    },
    {
      "source_type": "command_output",
      "source_ref": "python3 scripts/validate_plugin.py",
      "summary": "Validation exposed the same contract gap."
    }
  ],
  "provisional": false,
  "status": "pending"
}
```

如果证据还不足但值得保留，标记为 `provisional: true` 并保持 `status: pending`，等后续证据确认后再升级为稳定经验。`evidence_count` 必须等于 `evidence` 数组长度；写入前应按 `project_id`、`canonical_key` 和 `lesson_hash` 检查重复。

对于代码型经验（`experience_type: code-pattern`），必须额外携带 `code_pattern`：

```json
{
  "experience_type": "code-pattern",
  "code_pattern": {
    "language": "typescript",
    "pattern": "return withRetry(() => client.request(input));",
    "applies_when": "The same retryable request pattern appears.",
    "does_not_apply_when": "The endpoint is non-idempotent."
  }
}
```

不要把完整对话、私密片段或一次性叙事写入候选队列；只写可复用经验和必要证据摘要。结构化证据的 `source_type` 应尽量使用 `user_correction`、`test_failure`、`command_output`、`review_finding`、`prior_candidate`、`manual_request`、`agent_observation` 或 `other`。

候选确认、跳过、写入、复用或老化复查事件写入 `events.jsonl` 时，字段以 `skills/reflection-mode/schemas/event-record.schema.json` 为准。长期保留时可滚动归档到 `events.archive.jsonl`。事件只能记录真实发生的动作；不要为了证明有效而编造 `lesson_applied`。

`event_record` 建议默认保留策略：

- 候选相关事件（例如 `candidate_created`、`candidate_confirmed`、`candidate_skipped`、`stale_review`）默认 `expires_after_days: 180`
- 依赖快速变化上下文的短期事件可用 `expires_after_days: 30`

事件示例（候选创建）：

```json
{
  "schema_version": 1,
  "id": "reflection-event-2026-06-03T06:00:00Z-created",
  "created_at": "2026-06-03T06:00:00Z",
  "event_type": "candidate_created",
  "candidate_id": "reflection-candidate-2026-06-03T06:00:00Z-a1b2c3",
  "scope": "repo-or-global-scope",
  "queue_scope": "project",
  "project_id": "repo-reflection-mode",
  "summary": "Candidate created and queued for confirmation.",
  "expires_after_days": 180
}
```

事件示例（经验写入）：

```json
{
  "schema_version": 1,
  "id": "reflection-event-2026-06-03T06:00:00Z-written",
  "created_at": "2026-06-03T06:00:00Z",
  "event_type": "lesson_written",
  "lesson_id": "reflection-lesson-2026-06-03T06:00:00Z-x1y2z3",
  "scope": "repo-or-global-scope",
  "queue_scope": "project",
  "project_id": "repo-reflection-mode",
  "summary": "Reusable lesson written to skill reference.",
  "expires_after_days": 180
}
```

事件示例（经验被使用）：

```json
{
  "schema_version": 1,
  "id": "reflection-event-2026-06-03T06:00:00Z-applied",
  "created_at": "2026-06-03T06:00:00Z",
  "event_type": "lesson_applied",
  "lesson_id": "reflection-lesson-2026-06-03T06:00:00Z-x1y2z3",
  "scope": "repo-or-global-scope",
  "queue_scope": "project",
  "project_id": "repo-reflection-mode",
  "summary": "Lesson was applied during a matching review task.",
  "outcome_signal": "unknown",
  "result": "The user did not provide an external success signal.",
  "expires_after_days": 180
}
```

## 代码型经验

当经验必须包含代码片段才能准确复用时，使用 `experience_type: code-pattern`，并给出语言、适用条件和边界。代码片段应该短小，只保留模式本身。

````text
experience_type: code-pattern
language: typescript
pattern:
```typescript
// minimal reusable pattern only
```
applies_when:
does_not_apply_when:
next_action:
````

如果代码片段来自项目文件，优先引用文件和行号；如果只是示意代码，明确标记为示意，避免误当成项目事实。

## 状态与列表请求

如果用户要求 `$reflection-list`、`/reflect status`、列出候选或查看反思历史：

- 先检查宿主是否有候选队列、事件日志或 memory 列表能力。
- 可读取时，按当前项目、`signal_strength`、`last_seen` 和 `stale_after_days` 排序展示，默认只展示少量相关记录。
- 优先使用真实脚本管理队列：
  - `python3 scripts/reflection_queue.py list --status pending --limit <n>`
  - `python3 scripts/reflection_queue.py confirm <candidate_id> --target memory|skill-reference|project-doc|other`
  - `python3 scripts/reflection_queue.py skip <candidate_id>`
  - `python3 scripts/reflection_queue.py dedupe`
  - `python3 scripts/reflection_queue.py gc`
- 文本触发可以作为自然语言入口，但不要把它们描述成宿主内置命令，除非宿主确实提供了命令系统。示例：
  - `$reflection-list --status pending|confirmed|skipped|written|stale_review --limit <n>`
  - `$reflection-list delete <candidate_id>`
  - `$reflection-list export`
  - `/reflect status`
- 不可读取或日志不存在时，明确说明没有可访问的持久记录，不要编造历史。

## 质量门槛

最终输出前检查：

- 是否指出了具体行为改变？
- 是否基于证据而不是情绪或猜测？
- 是否避免了模糊建议？
- 是否避免把单次事件过拟合成规则？
- 沉淀建议是否有理由？
- 是否给出 `signal_strength`、证据次数和目标位置？
- 宿主授权写入是否满足量化标准和宿主权限？
- 候选是否能进入队列或明确返回给用户，避免静默丢失？
- 经验是否带有老化或复查信号？
- 下次是否能识别并复用这条经验？
