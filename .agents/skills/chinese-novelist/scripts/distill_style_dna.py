#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
女娲 (Nuwa) 双源动态加权文风与表达DNA认知蒸馏工具
基于 alchaincyf/nuwa-skill 核心理念升级：
支持双源动态加权文风演进机制 (Dual-Source Dynamic Style Weighting):
1. 外部参考文本 (Provided Reference / External DNA): 建立起步风格基准与反模式红线
2. 小说自身正文 (Accumulated Novel Body / Internal DNA): 随着小说章节与字数累积，自身文风权重递增
3. 动态权重演化 (Dynamic Weight Shift):
   - 起步期 (1-2章): 外部 85%~100% : 自身 0%~15%
   - 磨合期 (3-5章): 外部 60%~45% : 自身 40%~55%
   - 定型期 (6-10章): 外部 30%~20% : 自身 70%~80%
   - 成熟期 (11章+ / 宏篇): 外部 10%~15% : 自身 85%~90% (小说正文越多，参考自身的权重越重)

用法:
  python distill_style_dna.py [<参考文本路径>] [--project-dir <工程目录>] [--author <作家/风格名>] [--output <输出文件>] [--json]
"""

import argparse
import io
import json
import math
import os
import re
import sys
from pathlib import Path

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def analyze_text_dna(text: str) -> dict:
    """对文本进行多维度量化语言指纹提取"""
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    total_chars = len(chinese_chars)
    if total_chars == 0:
        return {"error": "未检测到有效中文字符", "total_chinese_chars": 0}

    # 1. 句子长度与律动分析（按句号、感叹号、问号、分号、换行分割）
    sentences = [s.strip() for s in re.split(r'[。！？；\n]', text) if len(s.strip()) > 1]
    sentence_lengths = [len(re.findall(r'[\u4e00-\u9fff]', s)) for s in sentences if len(re.findall(r'[\u4e00-\u9fff]', s)) > 0]

    avg_sentence_len = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0
    short_sentences = sum(1 for l in sentence_lengths if l <= 10)
    medium_sentences = sum(1 for l in sentence_lengths if 11 <= l <= 25)
    long_sentences = sum(1 for l in sentence_lengths if l > 25)

    short_ratio = round(short_sentences / len(sentence_lengths) * 100, 1) if sentence_lengths else 0
    long_ratio = round(long_sentences / len(sentence_lengths) * 100, 1) if sentence_lengths else 0

    # 2. 对话占比分析
    dialogues = re.findall(r'[“「](.*?)[”」]', text)
    dialogue_chars = sum(len(re.findall(r'[\u4e00-\u9fff]', d)) for d in dialogues)
    dialogue_ratio = round((dialogue_chars / total_chars) * 100, 1) if total_chars else 0

    # 3. 标点符号指纹
    commas = len(re.findall(r'[，,]', text))
    periods = len(re.findall(r'[。.]', text))
    dashes = text.count("——")
    ellipses = text.count("……")
    exclamations = len(re.findall(r'[！!]', text))
    questions = len(re.findall(r'[？?]', text))

    comma_to_period = round(commas / periods, 2) if periods > 0 else 0

    # 4. 感官通道词汇检测
    visual_words = len(re.findall(r'(?:看|见|望|瞧|注视|扫|瞥|黑|白|红|光|影|暗|明|青|灰|耀|色)', text))
    auditory_words = len(re.findall(r'(?:听|闻|声|音|响|吼|鸣|碎|颤|呼啸|嘶|寂|静|噪)', text))
    tactile_words = len(re.findall(r'(?:冷|热|冰|凉|痛|麻|硬|软|粗|滑|紧|触|摸|贴|沉|重)', text))

    # 5. 动词与动作白描密度
    action_words = len(re.findall(r'(?:斩|拔|刺|踏|跨|闪|劈|跃|握|抓|推|撞|扣|扯|按|甩|掷|翻|滚|掠|砸)', text))
    action_density = round((action_words / total_chars) * 100, 2) if total_chars else 0

    # 6. 四字结构密度
    idiom_matches = re.findall(r'[\u4e00-\u9fff]{4}', text)
    idiom_density = round((len(idiom_matches) * 4 / total_chars) * 100, 1) if total_chars else 0

    return {
        "total_chinese_chars": total_chars,
        "sample_sentences_count": len(sentence_lengths),
        "rhythm": {
            "avg_sentence_length": round(avg_sentence_len, 1),
            "short_sentence_ratio_pct": short_ratio,
            "long_sentence_ratio_pct": long_ratio,
            "comma_to_period_ratio": comma_to_period,
            "rhythm_tag": "凌厉紧凑型（短句为主）" if short_ratio >= 45 else ("盘旋繁复型（长复句为主）" if long_ratio >= 35 else "均衡叙事型")
        },
        "structure": {
            "dialogue_ratio_pct": dialogue_ratio,
            "action_density_pct": action_density,
            "idiom_density_pct": idiom_density
        },
        "punctuation_fingerprint": {
            "dashes_per_1000_chars": round((dashes / max(1, total_chars)) * 1000, 2),
            "ellipses_per_1000_chars": round((ellipses / max(1, total_chars)) * 1000, 2),
            "exclamation_ratio": round((exclamations / max(1, periods)) * 100, 1)
        },
        "sensory_channels": {
            "visual_weight": visual_words,
            "auditory_weight": auditory_words,
            "tactile_weight": tactile_words,
            "dominant_sense": "视觉主导" if visual_words >= auditory_words and visual_words >= tactile_words else ("听觉氛围主导" if auditory_words >= tactile_words else "体感触觉主导")
        }
    }


def calculate_dynamic_weights(completed_chapters: int, total_chars: int) -> dict:
    """根据已写章节数与正文字数，计算外部参考与小说自身正文的动态权重配比。
    法则：小说正文越多，参考自身的权重越重。"""
    if completed_chapters <= 0 or total_chars < 1500:
        ext_w = 1.00
        phase = "阶段零·起手播种期 (外部参考绝对主导)"
        desc = "正文尚未起步或极少，以外部提供的文风参考与 Nuwa 蒸馏指纹为 100% 语态锚点。"
    elif completed_chapters == 1:
        ext_w = 0.85
        phase = "阶段一·起步破土期 (外部参考 85% : 本书正文 15%)"
        desc = "已有第 1 章奠定基础，开始提取首批校准段落，仍以外部参考文本为主导。"
    elif completed_chapters == 2:
        ext_w = 0.75
        phase = "阶段一·起步破土期 (外部参考 75% : 本书正文 25%)"
        desc = "正文语态开始萌芽，逐步增加对第 1-2 章高光行文的吸收。"
    elif completed_chapters == 3:
        ext_w = 0.65
        phase = "阶段二·爬坡磨合期 (外部参考 65% : 本书正文 35%)"
        desc = "角色对话特色与叙事节奏初显，自身正文权重显著提升。"
    elif completed_chapters == 4:
        ext_w = 0.55
        phase = "阶段二·爬坡磨合期 (外部参考 55% : 本书正文 45%)"
        desc = "外部参考与本书自生语感趋于平衡对撞。"
    elif completed_chapters == 5:
        ext_w = 0.45
        phase = "阶段二·磨合定型期 (外部参考 45% : 本书正文 55%)"
        desc = "转折点！本书自身正文权重首次超越外部参考，开始以内生语调为主导。"
    elif 6 <= completed_chapters <= 9:
        ext_w = round(max(0.20, 0.45 - (completed_chapters - 5) * 0.05), 2)
        phase = f"阶段三·风格定型期 (外部参考 {int(ext_w*100)}% : 本书正文 {int((1-ext_w)*100)}%)"
        desc = "本书独有行文节奏与人物语言指纹已成型，创作主要对齐自身高水准段落。"
    elif 10 <= completed_chapters <= 19:
        ext_w = round(max(0.12, 0.22 - (completed_chapters - 10) * 0.012), 2)
        phase = f"阶段四·深度内化期 (外部参考 {int(ext_w*100)}% : 本书正文 {int((1-ext_w)*100)}%)"
        desc = "中长篇深度内化，本书正文占据绝对主导地位，外部参考退居为反模式红线规约。"
    else:  # >= 20 章节或字数超过 60,000
        ext_w = 0.10
        phase = "阶段五·自成一体成熟期 (外部参考 10% : 本书正文 90%)"
        desc = "全书内生文风已臻成熟浑然一体！本书定稿正文为最高准绳，外部参考仅做底线防漂移兜底。"

    int_w = round(1.0 - ext_w, 2)
    return {
        "external_weight": ext_w,
        "internal_weight": int_w,
        "external_pct": int(ext_w * 100),
        "internal_pct": int(int_w * 100),
        "phase_name": phase,
        "description": desc,
        "completed_chapters": completed_chapters,
        "total_chars": total_chars
    }


def blend_dna_metrics(ext_dna: dict, int_dna: dict, ext_w: float, int_w: float) -> dict:
    """根据权重融合外部参考与自身正文的量化指标"""
    if not ext_dna or "error" in ext_dna:
        return int_dna
    if not int_dna or "error" in int_dna:
        return ext_dna

    def blend_val(k1, k2, default=0.0):
        v1 = ext_dna.get(k1, {}).get(k2, default)
        v2 = int_dna.get(k1, {}).get(k2, default)
        return round(v1 * ext_w + v2 * int_w, 2)

    avg_len = blend_val("rhythm", "avg_sentence_length", 15.0)
    short_ratio = blend_val("rhythm", "short_sentence_ratio_pct", 30.0)
    long_ratio = blend_val("rhythm", "long_sentence_ratio_pct", 20.0)
    comma_to_period = blend_val("rhythm", "comma_to_period_ratio", 1.5)

    dialogue_ratio = blend_val("structure", "dialogue_ratio_pct", 30.0)
    action_density = blend_val("structure", "action_density_pct", 2.5)
    idiom_density = blend_val("structure", "idiom_density_pct", 5.0)

    dashes = blend_val("punctuation_fingerprint", "dashes_per_1000_chars", 1.0)
    ellipses = blend_val("punctuation_fingerprint", "ellipses_per_1000_chars", 1.0)

    # 判定主导风格律动
    rhythm_tag = "凌厉紧凑型（短句为主）" if short_ratio >= 45 else ("盘旋繁复型（长复句为主）" if long_ratio >= 35 else "均衡叙事型")

    # 感官通道混合
    v_w = ext_dna.get("sensory_channels", {}).get("visual_weight", 0) * ext_w + int_dna.get("sensory_channels", {}).get("visual_weight", 0) * int_w
    a_w = ext_dna.get("sensory_channels", {}).get("auditory_weight", 0) * ext_w + int_dna.get("sensory_channels", {}).get("auditory_weight", 0) * int_w
    t_w = ext_dna.get("sensory_channels", {}).get("tactile_weight", 0) * ext_w + int_dna.get("sensory_channels", {}).get("tactile_weight", 0) * int_w

    dominant_sense = "视觉主导" if v_w >= a_w and v_w >= t_w else ("听觉氛围主导" if a_w >= t_w else "体感触觉主导")

    return {
        "total_chinese_chars": ext_dna.get("total_chinese_chars", 0) + int_dna.get("total_chinese_chars", 0),
        "rhythm": {
            "avg_sentence_length": avg_len,
            "short_sentence_ratio_pct": short_ratio,
            "long_sentence_ratio_pct": long_ratio,
            "comma_to_period_ratio": comma_to_period,
            "rhythm_tag": rhythm_tag
        },
        "structure": {
            "dialogue_ratio_pct": dialogue_ratio,
            "action_density_pct": action_density,
            "idiom_density_pct": idiom_density
        },
        "punctuation_fingerprint": {
            "dashes_per_1000_chars": dashes,
            "ellipses_per_1000_chars": ellipses
        },
        "sensory_channels": {
            "visual_weight": round(v_w, 1),
            "auditory_weight": round(a_w, 1),
            "tactile_weight": round(t_w, 1),
            "dominant_sense": dominant_sense
        }
    }


def extract_golden_snippets_from_text(text: str, max_snippets: int = 3) -> list:
    """从正文中自动挖掘优质候选黄金段落（高张力动作段、鲜活对话段、意境沉浸段）"""
    paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) >= 80]
    scored = []

    for i, p in enumerate(paragraphs):
        chars = len(re.findall(r'[\u4e00-\u9fff]', p))
        if chars < 80 or chars > 600:
            continue
        # 评分机制：动词密度 + 对话比率 + 长短句交错
        actions = len(re.findall(r'(?:斩|拔|刺|踏|跨|闪|劈|跃|握|抓|推|撞|扣|扯|按|甩|掷|翻|滚|掠|砸)', p))
        dialogues = len(re.findall(r'[“「](.*?)[”」]', p))
        short_sentences = len([s for s in re.split(r'[。！？；]', p) if 2 <= len(re.findall(r'[\u4e00-\u9fff]', s)) <= 12])

        score = (actions * 3.0) + (dialogues * 2.5) + (short_sentences * 1.5)
        # 惩罚项：包含假对比或AI味
        if re.search(r'不仅.*?更|看似.*?实则|表面上|这一刻|无法言喻', p):
            score -= 10.0

        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:max_snippets]]


def scan_project_novel_body(project_dir: Path) -> tuple:
    """扫描工程正文目录，提取所有已完成章节文本与统计数据"""
    body_dir = project_dir / "06-正文"
    chapter_files = []

    if body_dir.exists():
        for f in body_dir.rglob("*.md"):
            if re.search(r'第\s*\d+\s*章', f.name):
                chapter_files.append(f)
    else:
        for f in project_dir.glob("*.md"):
            if re.search(r'第\s*\d+\s*章', f.name) and not any(k in f.name for k in ["审稿", "任务卡", "质检", "大纲", "人物"]):
                chapter_files.append(f)

    # 去重并排序
    def sort_ch(p: Path):
        m = re.search(r'第\s*(\d+)\s*章', p.name)
        return int(m.group(1)) if m else 999999

    unique_files = {}
    for f in chapter_files:
        unique_files[f.name] = f
    sorted_files = sorted(unique_files.values(), key=sort_ch)

    full_text = []
    chapter_count = len(sorted_files)
    total_chars = 0

    for cf in sorted_files:
        try:
            with open(cf, 'r', encoding='utf-8', errors='replace') as fp:
                t = fp.read()
                # 剔除 markdown 标题
                lines = [l for l in t.split('\n') if not l.startswith('#')]
                body_t = '\n'.join(lines)
                full_text.append(body_t)
                total_chars += len(re.findall(r'[\u4e00-\u9fff]', body_t))
        except Exception as e:
            print(f"⚠️ 读取章节失败 {cf}: {e}", file=sys.stderr)

    combined_text = '\n\n'.join(full_text)
    return sorted_files, chapter_count, total_chars, combined_text

    combined_text = '\n\n'.join(full_text)
    return sorted_files, chapter_count, total_chars, combined_text


def generate_nuwa_dual_dna_markdown(blended_dna: dict, ext_dna: dict, int_dna: dict, weights: dict, author: str, ext_sample: str, int_samples: list) -> str:
    """生成带有双源动态加权演进指示盘的女娲文风蒸馏档案"""
    rhythm = blended_dna.get("rhythm", {})
    structure = blended_dna.get("structure", {})
    sensory = blended_dna.get("sensory_channels", {})
    punct = blended_dna.get("punctuation_fingerprint", {})

    ext_r = ext_dna.get("rhythm", {}) if ext_dna else {}
    int_r = int_dna.get("rhythm", {}) if int_dna else {}

    ext_snippet = ext_sample.strip()[:600] if ext_sample else "（暂无外部参考文本）"
    if ext_sample and len(ext_sample) > 600:
        ext_snippet += "\n……（以下略）"

    int_snippets_md = ""
    if int_samples:
        for idx, snip in enumerate(int_samples, 1):
            int_snippets_md += f"#### 【本书正文高光段落 {idx}】\n```markdown\n{snip}\n```\n\n"
    else:
        int_snippets_md = "*（暂无已定稿章节黄金段落，待第 1 章创作后自动提取入库）*\n"

    md = f"""# 《{author}》双源动态加权文风认知蒸馏档案（Nuwa Dynamic Expression DNA）

> **蒸馏基准**：基于 `alchaincyf/nuwa-skill` 认知蒸馏框架与**双源动态加权文风演进机制**生成。
> **核心铁律**：**文风不仅参考提供的外部文本，更深度参考小说已生成的正文部分；小说正文越多，参考自身正文的权重越重！**

---

## 🧭 当前双源文风动态权重指示盘（Dynamic Weighting Dashboard）

| 指标维度 | 当前状态 / 数值 | 说明与演进法则 |
| :--- | :--- | :--- |
| **已定稿章节数** | **第 {weights['completed_chapters']} 章** | 当前正文篇幅积累状态 |
| **已累积正文字数** | **{weights['total_chars']} 纯汉字** | 真实正文规模 |
| **当前所处演进阶段** | **{weights['phase_name']}** | {weights['description']} |
| **外部参考文本权重** | **{weights['external_pct']}%** | 外部语料/名家风格样章影响力（随着正文增多逐步递减） |
| **本书自身正文权重** | **{weights['internal_pct']}%** | 本书自生语感/已确立的人物语言与节奏影响力（**篇幅越多权重越重！**） |

> 💡 **写前注意**：动笔撰写下一章时，大模型必须按上述 **外部 {weights['external_pct']}% : 自身 {weights['internal_pct']}%** 的权重将语态注入注意力头部。正文越多，越以本书定稿章节的腔调为最高准绳！

---

## 一、双源心智模型与决策启发式（Mental Models & Decision Heuristics）

1. **叙事视角与审视距离（外部底线 + 本书内生继承）**：
   - 视角贴合：贴近角色感知与肉体极限，拒绝上帝视角的道德说教。
   - 人性切角：关注“极端环境下的真实生存博弈”，每个人行动都有独立代价。
2. **决策启发式（叙事直觉）**：
   - **留白启发式**：遇重大转折不急于说透，通过角色下意识动作与环境异样展现。
   - **高潮爆发节奏**：动作前蓄力压抑，爆发时简洁致命；交火后必须有真实生理反馈（粗喘、创口脱力、耗材见底）。
   - **对话推进法则**：严格区分出场人物台词风格，说话带毛边与市井粗粝感，大道理烂在肚里，绝不全员哲学家。

---

## 二、融合表达 DNA（Blended Expression DNA —— 当前综合语言指纹）

### 1. 量化语言指纹（双源动态加权实测值）
- **综合句式律动**：**{rhythm.get('rhythm_tag', '标准型')}**
  - 平均句长：**{rhythm.get('avg_sentence_length', 15)}** 字（外部参考: {ext_r.get('avg_sentence_length', '-')} 字 / 本书正文: {int_r.get('avg_sentence_length', '-')} 字）
  - 短句（≤10字）占比：**{rhythm.get('short_sentence_ratio_pct', 0)}%**
  - 长句（>25字）占比：**{rhythm.get('long_sentence_ratio_pct', 0)}%**
  - 逗号/句号比：**{rhythm.get('comma_to_period_ratio', 1.5)}**
- **结构与动作质感**：
  - 对话字符占比：**{structure.get('dialogue_ratio_pct', 30)}%**
  - 动作动词密度：**{structure.get('action_density_pct', 2.5)}%**（以具象动词白描为主）
  - 成语密度：**{structure.get('idiom_density_pct', 5)}%**（严禁成语堆叠）
- **主导感官通道**：**{sensory.get('dominant_sense', '视觉主导')}**（视觉权重: {sensory.get('visual_weight', 0)}，听觉: {sensory.get('auditory_weight', 0)}，体感触觉: {sensory.get('tactile_weight', 0)}）

---

## 三、反模式清单（Anti-patterns —— 全书坚决拦截的雷区）

1. ❌ **严禁假对比与虚浮升华**：绝不出现“不仅是……更是……”、“看似……实则……”、“这不仅是一场战斗，更是一次对命运的拷问”。
2. ❌ **严禁机械网文陈词**：严禁“嘴角勾起一抹邪魅弧度”、“倒吸一口凉气”、“宛如天神降世”。
3. ❌ **严禁播音腔式全知心理说明**：绝不代替读者做道德总结（如“他心中涌起一股无法言喻的悲凉”）。
4. ❌ **严禁全员哲学家与长篇说教**：严禁角色突然发表长篇哲学演讲，多说人话，多写具体动作。
5. ❌ **严禁无代价光环**：战斗必有装备磨损、体能消耗与伤残代价。

---

## 四、双源黄金锚点段落库（动笔前强制诵读与注意力对齐）

### 1. 外部基准样章（权重占比: {weights['external_pct']}%）
> 用于奠定冷峻克制、物理感官与反套式基本底色。

```markdown
{ext_snippet}
```

### 2. 本书自生正文黄金段落库（权重占比: {weights['internal_pct']}%，**随正文增多权重持续增大**）
> 萃取自本书最新定稿的优秀章节，代表本书人物的实际声线、战斗白描手感与生活烟火气。

{int_snippets_md}

---

> ⚠️ **执行约束**：创作每一章前，根据当前正文规模（第 {weights['completed_chapters']} 章），严格按照 **外部 {weights['external_pct']}% : 自身 {weights['internal_pct']}%** 的权重比例锚定语态。正文越多，越要以本书自身已定型的高光段落与上一章切片为首要模仿基准！
"""
    return md


def main():
    parser = argparse.ArgumentParser(description="女娲 (Nuwa) 双源动态加权文风与表达DNA认知蒸馏工具")
    parser.add_argument("reference_file", nargs="?", default=None, help="外部参考文本文件路径")
    parser.add_argument("--project-dir", type=str, default=None, help="小说工程目录（用于扫描自身正文与自动加权）")
    parser.add_argument("--author", type=str, default="作品文风", help="作家姓名或文风名称")
    parser.add_argument("--output", type=str, default=None, help="蒸馏档案输出路径（Markdown 格式）")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出量化指标与权重")
    parser.add_argument("--update-self-style", action="store_true", help="自动从工程正文目录提取自身文风并更新工程文风档案")

    args = parser.parse_args()

    project_path = Path(args.project_dir).resolve() if args.project_dir else None
    ref_path = Path(args.reference_file).resolve() if args.reference_file else None

    # 如果没有指定参考文件但指定了工程目录，尝试在 04-文风/ 中查找已有参考
    raw_ext_text = ""
    if ref_path and ref_path.exists():
        with open(ref_path, 'r', encoding='utf-8', errors='replace') as f:
            raw_ext_text = f.read()
    elif project_path:
        possible_refs = [
            project_path / "04-文风" / "原创文风样例.md",
            project_path / "04-文风" / "文风总规范.md",
            project_path / "03-文风基准.md"
        ]
        for pr in possible_refs:
            if pr.exists():
                with open(pr, 'r', encoding='utf-8', errors='replace') as f:
                    raw_ext_text = f.read()
                break

    # 扫描工程正文
    chapter_count = 0
    total_chars = 0
    novel_body_text = ""
    int_samples = []

    if project_path and project_path.exists():
        ch_files, chapter_count, total_chars, novel_body_text = scan_project_novel_body(project_path)
        if novel_body_text:
            int_samples = extract_golden_snippets_from_text(novel_body_text, max_snippets=3)

    # 计算动态权重
    weights = calculate_dynamic_weights(chapter_count, total_chars)

    # 分析外部 DNA
    ext_dna = analyze_text_dna(raw_ext_text) if raw_ext_text else {}
    # 分析自身正文 DNA
    int_dna = analyze_text_dna(novel_body_text) if novel_body_text else {}

    # 混合指标
    blended_dna = blend_dna_metrics(ext_dna, int_dna, weights["external_weight"], weights["internal_weight"])

    # 生成 Markdown
    author_name = args.author if args.author != "作品文风" else (project_path.name if project_path else "全书文风")
    md_content = generate_nuwa_dual_dna_markdown(blended_dna, ext_dna, int_dna, weights, author_name, raw_ext_text, int_samples)

    # 确定输出路径
    out_path = Path(args.output).resolve() if args.output else None
    if not out_path and args.update_self_style and project_path:
        out_path = project_path / "04-文风" / "文风DNA蒸馏档案.md"

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"✅ 双源动态加权文风蒸馏档案已生成: {out_path}")
        print(f"   当前阶段: {weights['phase_name']}")
        print(f"   正文篇幅: {chapter_count} 章 ({total_chars} 字) | 权重配比: 外部 {weights['external_pct']}% : 自身 {weights['internal_pct']}%")

    if args.json:
        result = {
            "author": author_name,
            "weights": weights,
            "blended_metrics": blended_dna,
            "external_metrics": ext_dna,
            "internal_metrics": int_dna,
            "golden_snippets_count": len(int_samples)
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not out_path:
        print(md_content)

    sys.exit(0)


if __name__ == "__main__":
    main()
