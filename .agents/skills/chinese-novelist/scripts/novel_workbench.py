#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用小说轻量工作台：只读查询、体检、面板与审核式学习。无第三方依赖。"""
import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from project_config import load_project_config

SOURCES = {
    "人物": "02-人物", "世界观": "01-世界观", "剧情": "03-剧情",
    "计划": "05-写作计划", "正文": "06-正文", "记忆": "07-创作记忆",
    "审稿": "08-审稿"
}
REQUIRED = ["AGENTS.md", "02-写作计划.json", "06-正文", "07-创作记忆"]
EXCLUDE = {".git", ".novel-work", "__pycache__", ".venv", "node_modules"}

def files_under(root, name, suffixes=(".md", ".json")):
    d = root / name
    if not d.is_dir():
        return []
    return sorted(x for x in d.rglob("*") if x.is_file() and x.suffix.lower() in suffixes and not any(p in EXCLUDE for p in x.relative_to(d).parts))

def read(path):
    return path.read_text(encoding="utf-8-sig")

def short(s, limit=180):
    return re.sub(r"\\s+", " ", s).strip()[:limit]

def lines_matching(root, kind, term, limit):
    paths = files_under(root, SOURCES[kind])
    found = []
    for p in paths:
        try:
            for n, line in enumerate(read(p).splitlines(), 1):
                if term.casefold() in line.casefold():
                    found.append({"path": str(p.relative_to(root)), "line": n, "excerpt": short(line)})
                    if len(found) >= limit:
                        return found
        except (OSError, UnicodeError):
            continue
    return found

def query(root, kind, term, limit):
    kinds = list(SOURCES) if kind == "全部" else [kind]
    results = [r for k in kinds for r in lines_matching(root, k, term, limit)]
    return {"term": term, "scope": kind, "count": len(results[:limit]), "matches": results[:limit],
            "caution": "检索命中不等于已证实事实；请按正文、人物主档和时序账本核验。"}

def doctor(root):
    findings = []
    try:
        load_project_config(root)
    except ValueError as exc:
        findings.append({"severity": "ERROR", "path": "novel.project.json", "message": str(exc)})
    for name in REQUIRED:
        if not (root / name).exists():
            findings.append({"severity": "ERROR", "path": name, "message": "必要文件或目录缺失"})
    for d in ("01-世界观", "02-人物", "03-剧情", "04-文风", "05-写作计划", "08-审稿"):
        if not (root / d).is_dir():
            findings.append({"severity": "WARN", "path": d, "message": "约定目录不存在"})
    for p in [root / "02-写作计划.json", *files_under(root, "07-创作记忆", (".json",))]:
        if p.is_file():
            try:
                json.loads(read(p))
            except (OSError, ValueError) as e:
                findings.append({"severity": "ERROR", "path": str(p.relative_to(root)), "message": "JSON 无法解析: " + str(e)})
    chapters = files_under(root, "06-正文", (".md",))
    for p in chapters:
        relative = p.relative_to(root / "06-正文")
        txt = root / "06-正文-TXT" / relative.with_suffix(".txt")
        txt_dir = root / "06-正文-TXT" / relative.parent
        found = txt.is_file() or (txt_dir.is_dir() and any(txt_dir.glob(f"{p.stem}*.txt")))
        if not found:
            findings.append({"severity": "WARN", "path": str(txt.relative_to(root)), "message": "正文 TXT 副本缺失"})
    # 本工具不声称扫描了依赖、RAG 或原生 Dashboard 服务。
    return {"status": "BLOCKED" if any(f["severity"] == "ERROR" for f in findings) else ("WARN" if findings else "PASS"),
            "chapters": len(chapters), "findings": findings,
            "not_checked": ["原版 Scriptor/novel_* 服务", "RAG 索引", "外部依赖", "章节语义一致性", "MD/TXT 内容逐字一致性"],
            "next": "TXT 一致性请另运行 export_reading_txt.py --all --check；人工核验人物与时间线。"}

def dashboard(root, out):
    chapters = files_under(root, "06-正文", (".md",))
    characters = files_under(root, "02-人物", (".md",))
    memory = files_under(root, "07-创作记忆")
    reviews = files_under(root, "08-审稿", (".md",))
    groups = {}
    for p in chapters:
        groups[p.parent.name] = groups.get(p.parent.name, 0) + 1
    def entries(paths):
        return "".join("<li>" + html.escape(str(p.relative_to(root))) + "</li>" for p in paths[:1000])
    nav = "".join('<a href="#' + key + '">' + label + '</a>' for key,label in
                  (("volumes","卷进度"),("characters","人物档案"),("memory","动态记忆"),("reviews","审稿"),("chapters","正文")))
    rows = "".join("<tr><td>" + html.escape(k) + "</td><td>" + str(v) + "</td></tr>" for k,v in sorted(groups.items()))
    page = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>小说项目只读面板</title><style>
body{margin:0;color:#202938;background:#f6f7f9;font:15px/1.65 system-ui,sans-serif}nav{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:12px;z-index:10}nav a{margin-right:18px;color:#175c83}main{max-width:1000px;margin:auto;padding:20px}section{background:#fff;border:1px solid #e4e8ed;border-radius:7px;padding:18px;margin:18px 0}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;text-align:left;padding:7px}ul{overflow-wrap:anywhere}small{color:#5d6470}</style></head><body>
<nav>小说工程 · 只读视图　""" + nav + """</nav><main><h1>项目概览</h1><p>本页面由本地文件生成，不读取网络、不修改正文。列表为文件索引，不推断人物关系或追读评分。</p>
<section id="volumes"><h2>卷进度</h2><table><tr><th>卷</th><th>正文文件数</th></tr>""" + rows + """</table></section>
<section id="characters"><h2>人物档案</h2><ul>""" + entries(characters) + """</ul></section>
<section id="memory"><h2>动态记忆 / 伏笔 / 时间线</h2><ul>""" + entries(memory) + """</ul></section>
<section id="reviews"><h2>审稿记录</h2><ul>""" + entries(reviews) + """</ul></section>
<section id="chapters"><h2>正文章节</h2><ul>""" + entries(chapters) + """</ul></section>
<small>数据源：本地 MD/JSON；不包含原版数据库、RAG、追读力统计和可交互实体图谱。</small></main></body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return {"output": str(out), "chapters": len(chapters), "characters": len(characters)}

def learn(root, source, excerpt, finding, usage):
    src = (root / source).resolve()
    if not src.is_relative_to(root.resolve()) or not src.is_file():
        raise ValueError("source 必须是项目内已存在的文件")
    content = read(src)
    if not excerpt or excerpt not in content:
        raise ValueError("excerpt 必须是 source 中真实存在的原文（不可编造例句）")
    record = {
        "state": "CANDIDATE_REQUIRES_AUTHOR_APPROVAL",
        "source": str(src.relative_to(root)), "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "excerpt": excerpt, "learning": finding, "applicability": usage,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "warning": "候选经验未获作者确认；严禁自动改变正式文风规则。"
    }
    outdir = root / "07-创作记忆" / "学习候选"
    outdir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
    out = outdir / ("候选-" + key + ".json")
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output": str(out.relative_to(root)), "state": record["state"]}

def main():
    p = argparse.ArgumentParser(description="小说工程查询/体检/学习候选/静态面板")
    p.add_argument("--project-dir", default=".")
    sub = p.add_subparsers(dest="action", required=True)
    q = sub.add_parser("query")
    q.add_argument("term"); q.add_argument("--scope", choices=["全部", *SOURCES], default="全部")
    q.add_argument("--limit", type=int, default=30)
    sub.add_parser("doctor")
    d = sub.add_parser("dashboard")
    d.add_argument("--output", default=".novel-work/dashboard/index.html")
    l = sub.add_parser("learn")
    l.add_argument("--source", required=True); l.add_argument("--excerpt", required=True)
    l.add_argument("--finding", required=True); l.add_argument("--usage", required=True)
    a = p.parse_args()
    root = Path(a.project_dir).resolve()
    if not root.is_dir():
        p.error("project-dir 不存在")
    try:
        if a.action == "query":
            result = query(root, a.scope, a.term, max(1, min(200, a.limit)))
        elif a.action == "doctor":
            result = doctor(root)
        elif a.action == "dashboard":
            output = (root / a.output).resolve()
            if not output.is_relative_to(root) or not str(output.relative_to(root)).startswith(".novel-work/"):
                raise ValueError("面板必须输出到项目内 .novel-work/，避免覆盖正式文件")
            result = dashboard(root, output)
        else:
            result = learn(root, a.source, a.excerpt, a.finding, a.usage)
    except (OSError, UnicodeError, ValueError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if a.action == "doctor" and result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    sys.exit(main())
