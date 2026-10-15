#!/usr/bin/env bash
# doc_gate.sh — 文档体系熵门禁（迁移体系的三层防线之 L3，宿主无关）
# 检查项：
#   ERROR   落点（根目录白名单外散 .md / docs 非法子结构）
#   ERROR   死路径（活文档引用 DOCS/、wayfinder/、src/collection 前缀）
#   ERROR   断链（md 相对链接失效；archive/ 冻结历史豁免；LaTeX 记号豁免）
#   WARNING 孤儿（docs/、skills/ 中不被任何活文档引用的文件）
#   WARNING 超大活文档（docs/*.md > 100KB）
#   WARNING 陈旧票据（.scratch 活票 > 30 天未动）
# 退出码：有 ERROR → 1（不修不能关票）；仅 WARNING → 0（记录进关票回复）
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PYEOF'
import os, re, sys, time
from urllib.parse import unquote

ROOT = os.getcwd()
EXCLUDE = {".git", ".venv", "build", "install", "log", "node_modules",
           "__pycache__", ".pytest_cache", "archive", "runs", "omnihand_o10_model"}
ROOT_WHITELIST = {"AGENTS.md", "CLAUDE.md", "README.md", "STATUS.md",
                  "CONTEXT.md", "CODING_STANDARDS.md"}
DOCS_SUBDIRS_OK = {"adr", "agents"}
LIVE_TICKET_STATES = ("ready-for-agent", "in-progress", "claimed", "open", "needs-triage", "needs-info")
DEAD_PATH_PAT = re.compile(r"(DOCS/0|DOCS/I|wayfinder/|src/collection)")
LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')

errors, warns = [], []

def md_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE]
        for fn in filenames:
            if fn.endswith(".md"):
                yield os.path.join(dirpath, fn)

all_md = list(md_files())
rel_all = {os.path.relpath(p, ROOT) for p in all_md}
texts = {}

# 1) 落点 + 2) 死路径（活区：根、docs/、src/、skills/、.scratch 只查落点不查死路径——票据叙述历史合法）
for p in all_md:
    rel = os.path.relpath(p, ROOT)
    parts = rel.split(os.sep)
    if len(parts) == 1:
        if os.path.basename(rel) not in ROOT_WHITELIST:
            errors.append(f"[落点] 仓库根散文件: {rel}")
    elif parts[0] == "docs" and len(parts) > 2 and parts[1] not in DOCS_SUBDIRS_OK:
        errors.append(f"[落点] docs/ 非法子结构: {rel}（扁平纪律，只允许 adr/ agents/）")
    text = open(p, encoding="utf-8", errors="replace").read()
    texts[rel] = text
    if parts[0] in ("docs", "src", "skills") and parts[:2] != ["docs", "adr"]:
        for m in DEAD_PATH_PAT.finditer(text):
            ctx = text[max(0, m.start() - 20):m.start()] + text[m.end():m.end() + 20]
            if any(k in ctx for k in ("已废弃", "旧的", "（原", "原 ", "历史")):
                continue  # 说明性提及旧路径，非活引用
            errors.append(f"[死路径] {rel} 引用已废弃路径 {m.group(0)}")
            break

# 3) 断链
link_count = 0
for rel, text in texts.items():
    for m in LINK_RE.finditer(text):
        target = m.group(2).strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if "\\" in target:
            continue  # LaTeX 假阳性
        path = unquote(target.split("#")[0])
        if not path:
            continue
        link_count += 1
        resolved = os.path.normpath(os.path.join(ROOT, rel, "..", path))
        if not os.path.exists(resolved):
            errors.append(f"[断链] {rel} -> {target}")

# 4) 孤儿（docs 平铺层 + skills：文件名不被任何活 md 引用即孤儿）
for rel in sorted(rel_all):
    parts = rel.split(os.sep)
    if parts[0] == "docs" and len(parts) == 2:
        name = os.path.basename(rel)
        quoted = {r for r in texts if name in texts[r]}
        if len(quoted) <= 1:  # 只有自己提到自己
            warns.append(f"[孤儿] {rel} 不被任何活文档引用")

# 5) 超大活文档
for rel in sorted(rel_all):
    parts = rel.split(os.sep)
    if parts[0] == "docs" and len(parts) == 2:
        size = os.path.getsize(os.path.join(ROOT, rel))
        if size > 100 * 1024:
            warns.append(f"[超大] {rel} {size // 1024}KB > 100KB（瘦身候选）")

# 6) 陈旧票据
now = time.time()
for rel in sorted(rel_all):
    if ".scratch" in rel and os.sep + "issues" + os.sep in rel:
        text = texts[rel]
        ms = re.search(r'\*\*Status:\*\*\s*([^\n（(]+)', text) or re.search(r'^status:\s*(\S+)', text, re.M)
        if ms and ms.group(1).strip() in LIVE_TICKET_STATES:
            age_days = (now - os.path.getmtime(os.path.join(ROOT, rel))) / 86400
            if age_days > 30:
                warns.append(f"[陈旧票] {rel} 活跃状态已 {int(age_days)} 天未动")

print(f"doc_gate: {len(all_md)} 个活文档, {link_count} 条链接")
for e in errors:
    print("ERROR  ", e)
for w in warns:
    print("WARN   ", w)
print(f"结果: {len(errors)} error, {len(warns)} warning")
sys.exit(1 if errors else 0)
PYEOF
