#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正文审稿候选预扫：责任口号式台词与项目装备重复。仅提供证据，不作 AI 身份/质量判定。"""
import argparse
import json
import re
import sys
from pathlib import Path
from project_config import load_project_config

QUOTE = re.compile(r'[“「『"]([^”」』"\n]{1,180})[”」』"]')
RESPONSIBILITY = re.compile(
    r'(?:我签了字|我签了名|签了字|签字|错|这事|事|这人|人|这条命|命|责任)'
    r'[^。！？\n]{0,8}?(?:我认|我扛|我担|我赔|我带|我负责)'
)


def prose_lines(raw):
    in_code = False
    for number, line in enumerate(raw.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(("~~~", chr(96) * 3)):
            in_code = not in_code
            continue
        if in_code or not stripped or re.match(r"^#{1,6}\s", stripped):
            continue
        if stripped in ("---", "***", "___"):
            continue
        yield number, line


def review_candidates(files, mode="prose", project_dir=None):
    paths = [Path(x).resolve() for x in files]
    if mode == "outline":
        return {
            "mode": "outline", "status": "SKIPPED_BY_DESIGN",
            "files": [str(p) for p in paths], "candidates": [],
            "reason": "简写/章纲只审剧情；禁止运行正文台词、句法与重复词检测",
            "quality_review_status": "NOT_EVALUATED",
            "delivery_status": "NOT_EVALUATED",
        }
    if not paths:
        raise ValueError("必须给出至少一个正文文件")
    config = load_project_config(project_dir or paths[0])
    terms = config["review"]["repeated_equipment_terms"]
    seen = {term: [] for term in terms}
    candidates, inspected = [], []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"正文文件不存在: {path}")
        lines = list(prose_lines(path.read_text(encoding="utf-8-sig")))
        inspected.append(str(path))
        for index, (line_no, line) in enumerate(lines):
            for quote in QUOTE.finditer(line):
                match = RESPONSIBILITY.search(quote.group(1))
                if match:
                    context = "\n".join(x[1].strip() for x in lines[max(0, index - 1):index + 2])
                    candidates.append({
                        "type": "SLOGAN_DIALOGUE_CANDIDATE",
                        "file": str(path), "line": line_no, "quote": quote.group(1),
                        "matched_text": match.group(0), "context": context[:500],
                        "manual_questions": [
                            "对谁说、签字或承担责任的事实是否成立",
                            "此人是否有兑现权限、说完发生了什么",
                            "是否与相邻台词及邻章同构，是否有合理保留理由"
                        ],
                    })
            for term in terms:
                for match in re.finditer(re.escape(term), line):
                    seen[term].append({
                        "file": str(path), "line": line_no, "start": match.start(),
                        "context": line.strip()[:160]
                    })
    for term, locations in seen.items():
        if len(locations) < 2:
            continue
        candidates.append({
            "type": "EQUIPMENT_REPEAT_CANDIDATE",
            "term": term, "occurrences": len(locations),
            "first_mention": locations[0], "later_mentions": locations[1:],
            "review_range": inspected,
            "caution": "仅证实重复提及；首次出现不等于首次有效交代。须审查必要参数、角色和资源连续性",
        })
    return {
        "mode": "prose", "status": "CANDIDATES_ONLY", "files": inspected,
        "candidates": candidates,
        "coverage": {
            "scanned": ["引号内的责任宣言式短句候选", "项目配置装备关键词重复提及"],
            "manual_only": [
                "六类重复的语义增量及邻章价值裁决",
                "PAM01、F01—F16、TR/TX、S01—S12、G1—G4的完整人工审稿",
                "人物知情边界、事实一致性、独立反方和改稿净收益"
            ],
        },
        "quality_review_status": "NOT_EVALUATED",
        "delivery_status": "NOT_EVALUATED",
        "disclaimer": "候选只提供真实位置，不等于缺陷/P级/AI作者概率/质量通过；同根因由主审合并",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="待检测正文或简写")
    parser.add_argument("--mode", choices=["prose", "outline"], default="prose",
                        help="简写返回SKIPPED_BY_DESIGN，不做字句检测")
    parser.add_argument("--project-dir", default=None, help="小说项目根目录")
    parser.add_argument("--json", action="store_true", help="输出JSON")
    args = parser.parse_args(argv)
    try:
        result = review_candidates(args.files, args.mode, args.project_dir)
    except (FileNotFoundError, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False) if args.json else str(exc),
              file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"模式: {result['mode']} | {result['status']}")
        for item in result["candidates"]:
            print(f"- {item['type']}: {item.get('quote', item.get('term'))} | 候选，须人工复核")
        print("结果不包含自动文学质量评分或AI作者身份结论")
    return 0


if __name__ == "__main__":
    sys.exit(main())
