# Reflection Mode

`reflection-mode` 是一个面向 Codex 和 Claude Code 的本地插件，用于把任务完成后的经验、用户纠正和重复失败模式转化为可复用判断。

它的核心目标不是生成固定复盘模板，而是提供一套反思方法论：从具体证据中提炼可复用经验，判断经验应不沉淀、候选待确认，还是在达到自动写入标准且宿主允许时直接写入。

## 项目结构

```text
reflection-mode/
├── assets/
│   ├── reflection-mode-icon.png
│   └── reflection-mode-icon-small.png
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
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

## 运行时入口

- `skills/reflection-mode/SKILL.md`：触发边界、核心流程和运行规则。
- `references/reflective-practice.md`：反思方法与经验质量标准。
- `references/persistence-decision.md`：不沉淀、候选待确认、自动写入三档决策。
- `references/output-contract.md`：结构化输出和沉淀处理格式。
- `agents/openai.yaml`：Codex skill 列表展示信息。
- `assets/`：Codex 插件卡片图标，使用古典石刻沉思头像风格。

## 关键规则

- 自动触发默认只用于内部调整，不打断用户当前任务。
- 普通代码或内容 review 不触发，除非用户明确要求提炼可复用经验。
- 反思必须基于证据，不能把一次偶然事件过拟合成永久规则。
- 不因为发生了反思就自动沉淀。
- 该写入、值得自动写入且宿主允许时，就应该写入；不能写入时返回候选和原因。

## Codex 安装

当前本地安装源使用 personal marketplace：

```bash
rsync -a --delete --exclude .git \
  /Users/guobing/Desktop/my/reflection-mode/ \
  /Users/guobing/plugins/reflection-mode/

codex plugin add reflection-mode@personal
```

安装后用下面命令确认：

```bash
codex plugin list | rg "reflection-mode"
```

新安装或更新后的 skill 通常需要新开 Codex 线程才会进入上下文。

## 验证

```bash
python3 -m json.tool .codex-plugin/plugin.json
python3 -m json.tool .claude-plugin/plugin.json
ruby -e 'require "yaml"; text=File.read("skills/reflection-mode/SKILL.md"); YAML.load(text.split(/^---\s*$/,3)[1]); YAML.load_file("skills/reflection-mode/agents/openai.yaml"); puts "yaml ok"'
git diff --check
```

如果本机 Python 安装了 `PyYAML`，还可以跑 Codex 插件校验脚本：

```bash
python3 /Users/guobing/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```
