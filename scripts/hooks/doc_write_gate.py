#!/usr/bin/env python3
"""doc_write_gate — 写入门禁 hook（反熵体系 L2，ZCode / Claude Code 共用）。

stdin 收 PreToolUse 的工具调用 JSON；命中 .md 写入时：
- 无歧义违规 → stderr 给原因，exit 2（deny）
- 合法 → stdout 注入落点四问（additionalContext），exit 0
规则权威：skills/doc-writing/SKILL.md；事后兜底：scripts/doc_gate.sh。
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROOT_WHITELIST = {"AGENTS.md", "CLAUDE.md", "README.md", "STATUS.md",
                  "CONTEXT.md", "CODING_STANDARDS.md"}
DOCS_SUBDIRS_OK = {"adr", "agents"}

GIST = (
    "[doc-writing 落点四问] ① 代码/config 能 grep 到的不写（环境是事实源）；"
    "② 决策→docs/adr/，术语→CONTEXT.md，review 规则→CODING_STANDARDS.md；"
    "③ 贵再生知识（语义/坑/基线/硬件事实）→ docs/ 平铺中文文件名；"
    "④ 过程→.scratch/<feature>/ 票据，现状结论→STATUS.md，一次性叙事→不进仓库。"
    "完整规则 skills/doc-writing/SKILL.md；关票验收 scripts/doc_gate.sh 必须全绿。"
)


def deny(reason: str) -> None:
    sys.stderr.write(f"[doc_write_gate] 拒绝写入：{reason}\n")
    sys.exit(2)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 解析失败不拦截，交给事后门禁
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path or not file_path.endswith(".md"):
        sys.exit(0)
    abs_path = os.path.abspath(file_path)
    try:
        rel = os.path.relpath(abs_path, ROOT)
    except ValueError:
        sys.exit(0)
    if rel.startswith(".."):
        sys.exit(0)  # 仓库外，不管
    parts = rel.split(os.sep)

    if parts[0] == "archive":
        deny("archive/ 是冻结历史，禁止文本修改。归档请走 git mv 并在 archive/INDEX.md 登记。")
    if parts[0] == "docs" and parts[1:2] == ["agents"]:
        deny("docs/agents/ 是体系配置（tracker/triage/domain），变更需要专门票据。")
    if parts[0] == "docs" and len(parts) > 2 and parts[1] not in DOCS_SUBDIRS_OK:
        deny(f"docs/ 扁平纪律：{rel} 引入了未评审的子结构（仅允许 adr/ agents/）。新建结构先开票。")
    if len(parts) == 1 and os.path.basename(rel) not in ROOT_WHITELIST:
        deny(f"仓库根不允许新建散文件 {rel}。先读 skills/doc-writing/SKILL.md 的落点四问选对格子。")

    print(json.dumps({"additionalContext": GIST}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
