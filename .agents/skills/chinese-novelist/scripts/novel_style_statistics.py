#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小说正文的可复核文风统计与可选朱雀检测。仅提供审稿线索，不鉴定作者身份。

用法（只针对正式正文，简写/卷纲禁止使用）：
python novel_style_statistics.py 06-正文/第一卷/第001章.md --json
python novel_style_statistics.py 正文.md --baseline 已定稿1.md --baseline 已定稿2.md --baseline 已定稿3.md --report report.md
# 只有显式启用 --zhuque 才会上传正文，需要环境变量 MAKERS_MODELS_KEY。
python novel_style_statistics.py 正文.md --zhuque --report report.md
"""
import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
from urllib import request, error

ZHUQUE_ENDPOINT = "https://ai-gateway.edgeone.link/v1/providers/zhuque-text/classify"
MODIFIERS = ("猛地", "迅速", "死死", "狠狠", "骤然", "瞬间", "顿时", "立刻", "无比", "彻底", "冰冷", "狂暴", "突然", "缓缓")
PATTERNS = {
    "空洞升华": re.compile(r"这(?:不仅|不只)是.{2,24}(?:更是|而是)|这一刻.{0,16}(?:终于明白|懂得了)|命运的齿轮|标志着"),
    "套式责任台词": re.compile(r"(?:我签了字[，,]我认|错我担|命我赔|事情我扛|人我救)"),
    "罐头反应": re.compile(r"(?:沉默了?(?:片刻|半晌|几秒)|愣了一下|怔了一下|攥紧了拳头)"),
    "公文抽象表达": re.compile(r"(?:进行(?:了)?(?:检查|分析|处理|部署|讨论)|赋能|底层逻辑|形成闭环)"),
}
SENTENCE_RE = re.compile(r"[^。！？!?]+[。！？!?]?")
HAN_RE = re.compile(r"[\u3400-\u9fff]")
HEAD_RE = re.compile(r"^\s*(?:#{1,6}\s|第[零一二三四五六七八九十百\d]{1,5}章\s*$)")
CODE_RE = re.compile(r"^\s*[\x60]{3}")


def paragraphs(path):
    raw = Path(path).read_text(encoding="utf-8-sig")
    result = []
    in_code = False
    for line_no, line in enumerate(raw.splitlines(), 1):
        if CODE_RE.match(line):
            in_code = not in_code
            continue
        if in_code or HEAD_RE.match(line) or line.strip() in ("---", "***"):
            continue
        line = re.sub(r"^\s*[　 ]*", "", line).strip()
        if not line or line.startswith((">", "|", "<!--")):
            continue
        result.append({"line": line_no, "text": line})
    return result


def han_count(text):
    return len(HAN_RE.findall(text))


def safe_cv(values):
    mean = statistics.mean(values) if values else 0
    return round(statistics.pstdev(values) / mean, 3) if mean else None


def metrics(parts):
    prose = "\n".join(p["text"] for p in parts)
    hans = "".join(HAN_RE.findall(prose))
    sentence_lengths = [han_count(m.group()) for m in SENTENCE_RE.finditer(prose)
                        if han_count(m.group()) >= 2]
    n = max(len(hans), 1)
    modifiers = Counter({w: prose.count(w) for w in MODIFIERS if prose.count(w)})
    return {
        "han_chars": len(hans), "paragraph_count": len(parts),
        "sentence_count": len(sentence_lengths),
        "sentence_length_mean": round(statistics.mean(sentence_lengths), 2) if sentence_lengths else None,
        "sentence_length_cv": safe_cv(sentence_lengths),
        "paragraph_length_cv": safe_cv([han_count(p["text"]) for p in parts]),
        "unique_bigrams_ratio": round(len(set(hans[i:i+2] for i in range(max(0, len(hans)-1)))) / max(len(hans)-1, 1), 4),
        "modifier_per_1000": round(sum(modifiers.values()) / n * 1000, 2),
        "modifier_counts": dict(modifiers),
    }


def scan(parts):
    """只标候选，找得到行号和具体片段。相同短语跨段重复需达到8个汉字。"""
    issues = []
    seen = defaultdict(set)
    for p in parts:
        text = p["text"]
        compact = "".join(HAN_RE.findall(text))
        for name, pat in PATTERNS.items():
            for hit in pat.finditer(text):
                issues.append({"line": p["line"], "type": name, "evidence": text[max(0, hit.start()-12):hit.end()+16][:90],
                               "reason": "仅为候选，核对人物声音、场景和叙事必要性"})
        for w in MODIFIERS:
            if text.count(w) >= 3 and han_count(text) <= 160:
                issues.append({"line": p["line"], "type": "局部修饰词聚集", "evidence": text[:90],
                               "reason": f"{w}同段出现{text.count(w)}次；不自动判错"})
        # 8字片段的复现用于提示，排除纯数字、在同一段内重复与常见过短专业术语。
        chunks = {compact[i:i+8] for i in range(max(0, len(compact)-7))}
        repeated = sorted(((s, seen[s]) for s in chunks if seen[s] and p["line"] not in seen[s]),
                          key=lambda t: (min(t[1]), t[0]))
        if repeated:
            s, origins = repeated[0]
            issues.append({"line": p["line"], "type": "跨段连续表达复现",
                           "evidence": s, "reason": f"与第{min(origins)}行至少8个汉字连续相同；检查是否必要复沓"})
        for s in chunks:
            seen[s].add(p["line"])
    # 整章的重复不会被无限报满：同一类最多8条，报告标记截断数量。
    grouped = defaultdict(list)
    for i in issues:
        grouped[i["type"]].append(i)
    selected = [v for k in sorted(grouped) for v in grouped[k][:8]]
    return sorted(selected, key=lambda v: (v["line"], v["type"])), {
        k: {"total": len(v), "shown": min(len(v), 8)} for k, v in grouped.items()
    }


def baseline_compare(target, paths):
    samples = []
    for f in paths:
        p = Path(f)
        if not p.exists():
            raise FileNotFoundError(f"基线文件不存在: {p}")
        sampled = metrics(paragraphs(p))
        if sampled["han_chars"] >= 100:
            samples.append(sampled)
    if len(samples) < 3:
        return {"status": "INSUFFICIENT", "used": len(samples),
                "message": "至少需要3份每份100汉字以上的已定稿同类正文；不作异常判定"}
    fields = ("sentence_length_mean", "sentence_length_cv",
              "paragraph_length_cv", "unique_bigrams_ratio", "modifier_per_1000")
    observations = {}
    for name in fields:
        values = [s[name] for s in samples if s[name] is not None]
        if not values or target[name] is None:
            continue
        midpoint = statistics.median(values)
        # 小基线只作差异记录，不给'显著'统计结论。
        observations[name] = {"current": target[name], "baseline_median": round(midpoint, 4),
                               "difference": round(target[name] - midpoint, 4)}
    return {"status": "REFERENCE_ONLY", "used": len(samples), "differences": observations,
            "message": "基线仅帮助识别场景/视角变化，未经标注样本校准不得据此扣分"}


def zhuque_check(parts, timeout=30):
    key = os.getenv("MAKERS_MODELS_KEY", "").strip()
    if not key:
        return {"status": "SKIPPED", "reason": "未设置 MAKERS_MODELS_KEY；没有上传正文"}
    text = "\n".join(p["text"] for p in parts)
    req = request.Request(
        ZHUQUE_ENDPOINT,
        data=json.dumps({"text": text, "is_merge": False}, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read(2 * 1024 * 1024).decode("utf-8"))
        if data.get("status") != "success":
            return {"status": "ERROR", "reason": "官方模型返回非success", "message": str(data.get("msg", ""))[:180]}
        labels = {"0": "人工", "1": "AI", "2": "疑似AI"}
        return {"status": "SUCCESS", "provider": "Tencent EdgeOne Makers Zhuque",
                "labels_ratio": {labels.get(str(k), str(k)): v for k, v in data.get("labels_ratio", {}).items()},
                "ratio_confidence": data.get("ratio_confidence"),
                "softmax_confidence": data.get("softmax_confidence"),
                "usage": data.get("makers_models_usage", data.get("usage")),
                "segments": [{"label": labels.get(str(s.get("label")), "未知"),
                              "confidence": s.get("conf"), "position": s.get("position"),
                              "order": s.get("order")} for s in data.get("segment_labels", [])][:120],
                "note": "分类及置信度是官方服务输出，不是创作来源证明，也不直接进入小说质量评分"}
    except (OSError, ValueError, error.URLError) as exc:
        # 不回显请求/Authorization，不因网络失败阻断本地检测。
        return {"status": "ERROR", "reason": type(exc).__name__,
                "message": "服务请求失败，未获得有效检测结果；本地分析仍有效"}


def md_report(result):
    m = result["metrics"]
    out = ["# 小说正文文风统计与分段候选报告", "",
           f"- 文件：\x60{Path(result['file']).name}\x60",
           f"- 模式：正式正文（prose）；汉字 {m['han_chars']}，段落 {m['paragraph_count']}",
           "- 判定：**仅供审稿参考，不是AI生成概率；不会触发BLOCKED**", "",
           "## 统计特征", "",
           "| 指标 | 数值 |", "|---|---:|"]
    for k in ("sentence_length_mean", "sentence_length_cv", "paragraph_length_cv",
              "unique_bigrams_ratio", "modifier_per_1000"):
        out.append(f"| {k} | {m[k] if m[k] is not None else '样本不足'} |")
    b = result["baseline"]
    out.extend(["", "## 已定稿文风基线", "",
                f"- 状态：{b['status']}；有效样本 {b['used']}；{b['message']}"])
    if b.get("differences"):
        for k, v in b["differences"].items():
            out.append(f"- {k}：本章 {v['current']} / 基线中位数 {v['baseline_median']} / 差值 {v['difference']}")
    out.extend(["", "## 可复核候选（每类最多8条）", "",
                "| 行号 | 类型 | 原文证据 | 人工待查 |",
                "|---:|---|---|---|"])
    for i in result["candidates"]:
        clean = lambda s: str(s).replace("|", "／").replace("\n", " ")
        out.append(f"| {i['line']} | {clean(i['type'])} | {clean(i['evidence'])} | {clean(i['reason'])} |")
    if not result["candidates"]:
        out.append("| — | 未检出统计候选 | — | 仍须人工审稿 |")
    z = result["zhuque"]
    out.extend(["", "## 朱雀（仅显式开启时调用）", "",
                f"- 状态：{z['status']}"])
    if z["status"] == "SUCCESS":
        out.append(f"- 官方分类占比（非质量分）：{json.dumps(z['labels_ratio'], ensure_ascii=False)}")
        out.append(f"- 官方整体置信度：{z['softmax_confidence']}；风险占比参考：{z['ratio_confidence']}")
    elif z.get("reason"):
        out.append(f"- 说明：{z['reason']}")
    out.extend(["", "## 复核与改稿规则", "",
                "1. 按行号核对上下文、人物声口、战术复诵和必要文学复沓；提出反证与保留理由。",
                "2. 每个修改须比较收益与损害；不因统计数字或朱雀分类自动改稿。",
                "3. 此报告不替代 G1—G4、独立反方、七维评分、时空与设定核对。",
                "4. 简写/章纲/卷纲不使用本语言检测器，只使用剧情设计审查。"])
    return "\n".join(out) + "\n"


def main(argv=None):
    pa = argparse.ArgumentParser(description=__doc__)
    pa.add_argument("file", type=Path)
    pa.add_argument("--baseline", action="append", default=[], metavar="已定稿正文")
    pa.add_argument("--mode", choices=["prose", "outline"], default="prose")
    pa.add_argument("--zhuque", action="store_true", help="显式同意上传正文到腾讯云朱雀；默认绝不联网")
    pa.add_argument("--report", type=Path)
    pa.add_argument("--json", action="store_true")
    a = pa.parse_args(argv)
    if a.mode == "outline":
        pa.error("简写/大纲仅运行剧情审查；禁止正文语言统计及朱雀调用")
    try:
        parts = paragraphs(a.file)
        if not parts:
            pa.error("未读取到正文段落")
        m = metrics(parts)
        candidates, counts = scan(parts)
        b = baseline_compare(m, a.baseline) if a.baseline else {
            "status": "NOT_REQUESTED", "used": 0, "message": "未指定同类已定稿基线"}
        result = {"file": str(a.file), "mode": a.mode, "metrics": m, "candidates": candidates,
                  "candidate_counts": counts, "baseline": b,
                  "zhuque": zhuque_check(parts) if a.zhuque else {"status": "NOT_REQUESTED"},
                  "quality_gate": "REFERENCE_ONLY"}
        if a.report:
            a.report.parent.mkdir(parents=True, exist_ok=True)
            a.report.write_text(md_report(result), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else md_report(result))
        return 0
    except (OSError, UnicodeError) as exc:
        print(f"读取失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
