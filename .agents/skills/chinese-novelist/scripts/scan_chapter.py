#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单章机械性预扫描工具（合并自 novel-quality-review）
功能：
1. 精确统计正文汉字数（is_han 算法，严格过滤标题、代码围栏、Markdown 标记、空行、场景分隔符）
2. 统计非空白字符数（含正文标点）
3. 扫描 5 类典型候选文本套式（全知模板句、总结式顿悟、假对比/升华、机械断章、高频修饰词）
4. 输出候选证据列表与行号上下文，供质检核查

用法:
  python scan_chapter.py <章节路径> [<章节路径2> ...] [--min-words 配置覆盖] [--max-words 配置覆盖] [--json]
"""

import argparse
import io
import json
import os
import re
import sys
from pathlib import Path
from project_config import chapter_limits, load_project_config

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PATTERNS = {
    "全知模板句": r"他不知道的是|她不知道的是|殊不知|命运的齿轮",
    "总结式顿悟": r"这一刻.{0,9}(终于|才)?明白|终于懂得了|这一刻.{0,9}意识到",
    "假对比/升华": r"不仅是.{0,24}更是|不只是.{0,24}更是|看似.{0,24}实则",
    "机械断章": r"危险正在悄然逼近|然而.{0,20}意想不到|一场更大的风暴",
    "高频修饰词": r"瞬间|冰冷|死死|狂暴|狠狠",
}


def is_han(ch: str) -> bool:
    """判定单个字符是否为汉字（统一中日韩象形字符及扩展区）"""
    cp = ord(ch)
    return (
        0x3400 <= cp <= 0x9FFF or
        0xF900 <= cp <= 0xFAFF or
        0x20000 <= cp <= 0x3134F
    )


def prose_lines(text: str):
    """
    遍历并提取纯正文行，保留原始行号。
    跳过 Markdown 标题、代码围栏、场景分割线以及转储注释。
    """
    inside_fence = False
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(">>>"):  # 某些文稿插入的转储标记
            continue
        if stripped.startswith("~~~") or stripped.startswith("```"):
            inside_fence = not inside_fence
            continue
        if inside_fence or not stripped or re.match(r"^#{1,6}\s", stripped):
            continue
        # Markdown 场景分隔符不算正文
        if stripped in ("---", "***", "___"):
            continue
        yield line_no, line


def scan_file(path: Path, min_words: int = None, max_words: int = None):
    """扫描单章文件，返回汉字字数与潜在套式命中"""
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    min_words, max_words = chapter_limits(path, min_words=min_words, max_words=max_words)
    raw_text = path.read_text(encoding="utf-8-sig")
    lines = list(prose_lines(raw_text))
    prose = "".join(line for _, line in lines)

    hits = []
    for label, pattern in PATTERNS.items():
        for line_no, line in lines:
            for match in re.finditer(pattern, line):
                left = max(0, match.start() - 24)
                right = min(len(line), match.end() + 24)
                hits.append({
                    "type": label,
                    "line": line_no,
                    "match": match.group(),
                    "context": line[left:right].strip()
                })

    # 项目关注的装备名词只生成候选：重复本身并非质量问题。
    equipment_terms = load_project_config(path)["review"]["repeated_equipment_terms"]
    for term in equipment_terms:
        occurrences = []
        for line_no, line in lines:
            for match in re.finditer(re.escape(term), line):
                occurrences.append((line_no, line.strip()))
        if len(occurrences) > 1:
            for line_no, context in occurrences[1:]:
                hits.append({"type": "项目装备重复候选", "line": line_no,
                             "match": term, "context": context[:100]})
    hits.sort(key=lambda x: (x["line"], x["type"]))
    han_count = sum(is_han(ch) for ch in prose)
    visible_count = sum(not ch.isspace() for ch in prose)

    # 判断字数红线
    is_blocked_by_length = False
    length_issues = []
    if han_count < min_words:
        is_blocked_by_length = True
        length_issues.append(f"汉字字数不足: 当前 {han_count} 字，最低红线 {min_words} 字（缺口 {min_words - han_count} 字）")
    elif max_words and han_count > max_words:
        length_issues.append(f"汉字字数超标: 当前 {han_count} 字，建议上限 {max_words} 字（超出 {han_count - max_words} 字）")

    return {
        "file": str(path.resolve()),
        "han_characters": han_count,
        "non_whitespace_characters": visible_count,
        "min_words_required": min_words,
        "max_words_suggested": max_words,
        "length_status": "BLOCKED" if is_blocked_by_length else "PASS",
        "length_issues": length_issues,
        "potential_patterns": hits,
        "patterns_count": len(hits),
        "disclaimer": "候选文本模式只供上下文复核，不是AI作者鉴定或质量一票否决依据",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+", help="章节 Markdown 文件路径")
    parser.add_argument("--min-words", type=int, default=None, help="覆盖小说项目的最低字数")
    parser.add_argument("--max-words", type=int, default=None, help="覆盖小说项目的建议上限")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    args = parser.parse_args()
    results = [scan_file(p, *chapter_limits(p, min_words=args.min_words, max_words=args.max_words)) for p in args.files]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print("=" * 60)
            print(f"📄 文件: {item['file']}")
            print(f"📊 正文汉字: {item['han_characters']} | 非空白字符: {item['non_whitespace_characters']} | 篇幅判定: {item['length_status']}")
            if item["length_issues"]:
                for iss in item["length_issues"]:
                    print(f"  ❌ {iss}")
            print(f"🔍 模式命中: {item['patterns_count']} 处候选套式表达")
            for hit in item["potential_patterns"][:20]:
                print(f"  L{hit['line']} [{hit['type']}] {hit['context']}")
            if len(item["potential_patterns"]) > 20:
                print(f"  ... 另有 {len(item['potential_patterns']) - 20} 处命中，请使用 --json 查看全部")
        print("=" * 60)


if __name__ == "__main__":
    main()
