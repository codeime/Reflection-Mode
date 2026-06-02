<p align="center">
  <img src="assets/reflection-mode-icon.png" alt="Reflection Mode icon" width="160" />
</p>

# Reflection Mode

[English](README.md) | 中文

`reflection-mode` 是一个面向 Codex 和 Claude Code 的本地插件，用于把任务完成后的经验、用户纠正和重复失败模式转化为可复用判断。

它的核心目标不是生成固定复盘模板，而是提供一套反思方法论：从具体证据中提炼可复用经验，判断经验应不沉淀、候选待确认，还是在达到自动写入标准且宿主允许时直接写入。

## 由来

Reflection Mode 来自一个很朴素的想法：人会通过反思过去的经验成长；如果不反思，同样的错误就容易重复发生。AI Agent 也有类似问题。它可能完成了任务、收到用户纠正，或在熟悉的地方失败，但如果没有把这些经历转成可复用经验，下次仍然可能重新踩坑。

这个插件就是为了把这条学习链路显式化。它把已完成任务、用户纠正和重复失败当作证据，从中提炼会改变未来行为的经验；当经验足够稳定时，再判断它应该不沉淀、作为候选待确认，还是在宿主允许时自动写入。

## GitHub About

```text
反思模式：帮 Agent 从任务、纠正和重复失败中提炼经验，判断不沉淀、候选或自动写入。 Reflection Mode helps agents extract lessons and decide skip, candidate, or auto-write.
```

## 项目结构

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

## 安装

如果你希望让 AI 助手代为安装，直接把 [llms.txt](llms.txt) 的内容贴给它执行。

本仓同时支持 Codex 和 Claude Code。`llms.txt` 会引导 AI 助手 clone 本仓、同步到本地 marketplace，并完成对应 CLI 安装。

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

如果使用 Codex 的 plugin creator 工具维护该插件，可以再运行本机工具安装里的插件校验脚本。
