#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线生成 v8 风格的十段写作材料包；不修改小说权威文件。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from project_config import load_project_config, project_file


def checksum(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run():
    parser = argparse.ArgumentParser(description="生成本仓 webnovel-writer v8 适配备料包")
    parser.add_argument("--project-dir", default=".")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--chapter", type=int)
    choice.add_argument("--interlude-task")
    parser.add_argument("--volume", required=True)
    parser.add_argument("--source", action="append", default=[], help="补充人物小传或专题源，可多次传入")
    parser.add_argument("--previous", help="上一正式章相对路径")
    parser.add_argument("--output", help="仓内临时输出目录")
    args = parser.parse_args()
    root = Path(args.project_dir).resolve()
    if not (root / "AGENTS.md").is_file():
        parser.error("找不到 AGENTS.md；须指定本书仓库根目录")

    def secure(rel):
        p = (root / rel).resolve()
        if not p.is_relative_to(root):
            raise ValueError("禁止读取或写入仓库外路径: " + rel)
        return p

    if args.chapter is not None:
        if args.chapter < 1:
            parser.error("章号必须为正整数")
        slug = f"第{args.chapter:03d}章"
        tasks = list((root / "05-写作计划/章节任务卡").glob(slug + "-任务卡.md"))
        if len(tasks) != 1:
            parser.error("不存在唯一任务卡: " + slug)
        task = tasks[0].relative_to(root).as_posix()
    else:
        task = args.interlude_task
        slug = Path(task).stem.removesuffix("-任务卡")
        if "插章" not in slug or not task.startswith("05-写作计划/插章任务卡/"):
            parser.error("插章任务卡必须位于 05-写作计划/插章任务卡/")

    if not secure(task).is_file():
        parser.error("任务卡不存在: " + task)
    original_task = secure(task).read_text(encoding="utf-8-sig")
    approved_text_signal = bool(re.search(r"(?:简写|审核状态|作者审核).{0,30}(?:已通过|已批准|通过审核)", original_task))
    names = ["本章任务与确认细纲", "硬约束与禁区", "当前事实与连续性",
             "人物关系组织与规则", "时空及知情边界", "线索与承诺",
             "近期正文衔接", "文风与表达", "暂定事项及风险", "来源版本清单"]
    data = [[] for _ in names]
    files = []
    missing = []

    def add(section, rel, tail=None):
        file = secure(rel)
        if not file.is_file():
            missing.append(rel)
            data[section - 1].append("【缺失】" + rel)
            return
        full = file.read_text(encoding="utf-8-sig")
        selected = full[-tail:] if tail is not None else full
        selected_range = f"末尾{tail}字符" if tail is not None else "全文"
        record = {"path": rel, "sha256": checksum(full), "range": selected_range,
                  "total_characters": len(full), "selected_characters": len(selected)}
        files.append(record)
        data[section - 1].append(
            f"【来源：{rel}；范围：{selected_range}；原文SHA256：{record['sha256']}】\n{selected}"
        )

    add(1, task)
    add(2, "AGENTS.md")
    rules_path = project_file(root, "story_rules")
    if rules_path:
        add(2, rules_path.relative_to(root).as_posix())
    if (root / "novel.project.json").is_file():
        add(2, "novel.project.json")
    add(2, "04-文风/禁用表达与常见问题.md")
    for name in ["当前写作进度", "人物实时状态", "队伍编组状态总账"]:
        add(3, f"07-创作记忆/{name}.md")
    add(4, "02-人物/人物关系与冲突.md")
    for rel in args.source:
        add(4, rel)
    add(5, "07-创作记忆/事件时间线.md")
    add(5, "07-创作记忆/时间轴总账.json")
    add(6, "07-创作记忆/伏笔兑现记录.md")
    previous = args.previous
    if not previous and args.chapter and args.chapter > 1:
        matches = list((root / "06-正文").glob(f"*/第{args.chapter-1:03d}章.md"))
        if len(matches) == 1:
            previous = matches[0].relative_to(root).as_posix()
    if previous:
        add(7, previous, tail=1200)
    else:
        data[6].append("【未定位上一实写章节；主控须按时序核对，不得猜测】")
    add(7, "99-章节摘要.md", tail=5000)
    add(8, "04-文风/文风总规范.md")
    add(8, "04-文风/原创文风样例.md", tail=6000)
    brief_size = load_project_config(root)["writing"]["brief_target_han"]
    data[8].append(
        f"【人工必查】作者是否明确批准本章概要和约{brief_size}字简写；人物是否建档；"
        "重要物资伤势与知情范围是否连续；需不需要战斗协同专项。\n"
        f"【任务卡审批文字信号】{'检出，但仍须人工核对' if approved_text_signal else '未检出；不能据此进入详写'}"
    )
    if missing:
        data[8].append("【缺失来源】" + "、".join(missing))
    data[9].extend(f"- {item['path']} / {item['range']} / sha256={item['sha256']}" for item in files)
    content = (f"# {slug}·v8 流程适配备料包\n\n"
               f"所属卷：{args.volume}\n\n"
               "此包不是 DSH 原生输出，不证明作者批准或质检通过。\n")
    for i, name in enumerate(names):
        content += f"\n## {i+1:02d} {name}\n\n" + "\n\n".join(data[i] or ["【未提供】"]) + "\n"
    output = secure(args.output or f".novel-work/{slug}")
    if output == root or output.is_file():
        parser.error("输出目录不合法")
    output.mkdir(parents=True, exist_ok=True)
    material = output / "材料包.md"
    manifest = output / "来源清单.json"
    facts = {"schemaVersion": 1, "chapter": slug, "volume": args.volume,
             "task": task, "sources": files, "missing": missing,
             "task_approval_keyword_only": approved_text_signal,
             "author_approval_verified": False, "ready_for_drafting": False,
             "material_sha256": checksum(content)}
    material.write_text(content, encoding="utf-8")
    manifest.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"material": str(material), "manifest": str(manifest),
                      "sources": len(files), "missing": missing,
                      "approval_verified": False, "sha256": checksum(content)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        run()
    except (OSError, ValueError, UnicodeError) as e:
        print("生成材料包失败：" + str(e), file=sys.stderr)
        sys.exit(2)
