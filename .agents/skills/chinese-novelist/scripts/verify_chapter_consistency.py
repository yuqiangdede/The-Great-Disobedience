#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单章多维一致性与合规性核查工具（Consistency & Quality Review Engine）
集成:
1. 时间轴与多主角年龄/主线事件合规性核验（Timeline & Chronology Gate）
2. 情节因果与生理/伤病状态继承核验（Plot & Physical Continuity）
3. 主角人设契合度、负面禁令与小传完备性核验（Persona, Constraints & Bios）
4. 正文精确汉字数统计与篇幅红线核验（Word Count & Mechanics via is_han）
5. AI式痕迹与候选套式模式扫描（Humanizer-zh & novel-quality-review）
6. 自动生成七维量化审稿报告（符合固定审稿报告模板）

用法:
  python verify_chapter_consistency.py <章节文件路径> [--project-dir <工程根目录>] [--min-words <最小字数>] [--max-words <建议上限>] [--json] [--report <报告输出路径>] [--auto-report]

退出码:
  0 = 全部通过 (PASS)
  1 = 存在阻断性问题 (BLOCKED)
  2 = 参数或文件错误 (ERROR)
"""

import argparse
import datetime
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

# 中文数字解析映射
CHINESE_NUM_MAP = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '百': 100, '千': 1000
}

# 典型候选文本套式模式 (来自 novel-quality-review)
REVIEW_PATTERNS = {
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


def parse_chinese_number(cn_str: str) -> int:
    """解析简单的中文字符串为整数（如：十六 -> 16, 二十四 -> 24）"""
    if cn_str.isdigit():
        return int(cn_str)
    val = 0
    temp = 0
    for char in cn_str:
        num = CHINESE_NUM_MAP.get(char, None)
        if num is None:
            continue
        if num == 10:
            if temp == 0:
                temp = 1
            val += temp * 10
            temp = 0
        elif num == 100:
            val += temp * 100
            temp = 0
        else:
            temp = num
    val += temp
    return val


def prose_lines(text: str):
    """提取纯正文行，保留原始行号，过滤标题与代码块等标记"""
    inside_fence = False
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(">>>"):
            continue
        if stripped.startswith("~~~") or stripped.startswith("```"):
            inside_fence = not inside_fence
            continue
        if inside_fence or not stripped or re.match(r"^#{1,6}\s", stripped):
            continue
        if stripped in ("---", "***", "___"):
            continue
        yield line_no, line


def locate_project_dir(chapter_path: Path, explicit_project_dir: str = None) -> Path:
    """推断或定位工程根目录"""
    if explicit_project_dir:
        return Path(explicit_project_dir).resolve()

    current = chapter_path.resolve().parent
    for _ in range(5):
        if (
            (current / "02-写作计划.json").exists() or
            (current / "07-创作记忆").exists() or
            (current / "01-大纲.md").exists() or
            (current / "AGENTS.md").exists()
        ):
            return current
        if current.parent == current:
            break
        current = current.parent
    return chapter_path.resolve().parent


def extract_chapter_content(chapter_path: Path) -> dict:
    """解析章节正文及各组成部分"""
    with open(chapter_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    lines_with_no = list(prose_lines(raw_text))
    pure_prose = "".join(line for _, line in lines_with_no)

    title = chapter_path.stem
    for line in raw_text.split('\n'):
        if line.startswith('#') and '章' in line:
            title = line.strip('#').strip()
            break

    # 提取对话内容
    dialogues = re.findall(r'[“「](.*?)[”」]', raw_text)

    # 汉字字数与可见非空白字符统计
    han_words = sum(is_han(ch) for ch in pure_prose)
    non_space_chars = sum(not ch.isspace() for ch in pure_prose)

    # 章节号提取
    chapter_num = 0
    ch_num_match = re.search(r'第(\d+)章', chapter_path.name) or re.search(r'第(\d+)章', title)
    if ch_num_match:
        chapter_num = int(ch_num_match.group(1))

    return {
        "title": title,
        "chapter_number": chapter_num,
        "raw_text": raw_text,
        "pure_prose": pure_prose,
        "lines_with_no": lines_with_no,
        "dialogues": dialogues,
        "han_words": han_words,
        "non_space_chars": non_space_chars
    }


def check_word_count(content: dict, min_words: int, max_words: int) -> dict:
    """字数与篇幅红线核验"""
    wc = content["han_words"]
    issues = []
    warnings = []

    if wc < min_words:
        issues.append(f"正文汉字数不足: 当前 {wc} 字，最低红线要求 {min_words} 字（缺口 {min_words - wc} 字）")
    elif max_words and wc > max_words:
        warnings.append(f"单章正文字数偏长（当前 {wc} 字，建议上限 {max_words} 字），注意控制叙事节奏与分章")

    return {
        "status": "fail" if issues else ("warn" if warnings else "pass"),
        "han_words": wc,
        "non_space_chars": content["non_space_chars"],
        "min_words": min_words,
        "max_words": max_words,
        "issues": issues,
        "warnings": warnings
    }


def find_chapter_task_card(project_dir: Path, chapter_num: int) -> tuple:
    """寻找对应章节的任务卡文件并读取内容"""
    cards_dir = project_dir / "05-写作计划" / "章节任务卡"
    if not cards_dir.exists():
        return None, ""

    candidate_cards = (
        list(cards_dir.glob(f"*{chapter_num:03d}*.md")) or
        list(cards_dir.glob(f"*{chapter_num:02d}*.md")) or
        list(cards_dir.glob(f"*{chapter_num}*.md"))
    )
    if candidate_cards:
        card_file = candidate_cards[0]
        try:
            with open(card_file, 'r', encoding='utf-8') as f:
                return card_file, f.read()
        except Exception:
            return card_file, ""
    return None, ""


def check_timeline_and_world_events(content: dict, project_dir: Path, chapter_path: Path) -> dict:
    """
    时间轴与多主角年龄/世界主线事件合规性深度核验（核心增强）
    核验维度:
    1. 章节世界基线时间锚定（当前世界年份、月份、天候节令）
    2. 多主角实时理论年龄计算与正文表述严格校验
    3. 主角生命周期与阶段合法性（未出生/已阵亡/提前登场/超阶段能力拦截）
    4. 世界主线事件时刻表与因果顺逆校验（未来事件提前成为既成事实拦截）
    5. 环境与气候节令矛盾核查（如严冬出现蝉鸣酷暑）
    6. 地理位移耗时与交通矩阵核查
    """
    raw_text = content["raw_text"]
    chapter_num = content["chapter_number"]
    issues = []
    warnings = []
    info = []

    # 1. 读取时间轴总账 JSON
    timeline_json_path = project_dir / "07-创作记忆" / "时间轴总账.json"
    timeline_data = {}
    if timeline_json_path.exists():
        try:
            with open(timeline_json_path, 'r', encoding='utf-8') as f:
                timeline_data = json.load(f)
        except Exception as e:
            warnings.append(f"读取时间轴总账.json失败: {e}")

    # 读取任务卡文本
    card_file, card_text = find_chapter_task_card(project_dir, chapter_num)

    # 提取世界基线时间信息
    world_baseline = timeline_data.get("worldBaseline", {})
    baseline_year = world_baseline.get("currentYear")
    baseline_year = baseline_year if type(baseline_year) is int else None
    baseline_season = world_baseline.get("season") or ""
    baseline_weather = world_baseline.get("weather") or ""
    if baseline_year is None:
        warnings.append("缺少可信世界时间基线；仅检查正文和任务卡能确认的时间，不推断角色年龄或未来事件")

    # 2. 章节世界时间提取与对齐（优先以任务卡与正文时间为准，无则沿用基准）
    chapter_world_year = baseline_year
    year_match = re.search(r'(?:公元)?(\d{4})年', card_text) or re.search(r'(?:公元)?(\d{4})年', raw_text[:1000])
    if year_match:
        chapter_world_year = int(year_match.group(1))

    info.append(f"当前章节锚定世界年份: {chapter_world_year if chapter_world_year is not None else '待确认'} | 基线季节: {baseline_season or '待确认'}")

    # 3. 提取正文中所有显式的年龄数字
    age_patterns = [
        r'(?:年方|年仅|已满|年岁|虚岁|周岁|年纪|时年|年已)?\s*([0-9零一二两三四五六七八九十百]+)\s*岁',
        r'([0-9零一二两三四五六七八九十百]+)\s*余岁'
    ]
    detected_ages = []
    for pat in age_patterns:
        for m in re.finditer(pat, raw_text):
            age_str = m.group(1)
            parsed_age = parse_chinese_number(age_str)
            if 3 <= parsed_age <= 120:
                snippet = raw_text[max(0, m.start() - 25):min(len(raw_text), m.end() + 25)].replace('\n', ' ')
                detected_ages.append({"age": parsed_age, "raw": m.group(0), "snippet": snippet, "pos": m.start()})

    # 4. 多主角时间生命线、阶段与出场合法性校验
    chars_timeline = timeline_data.get("charactersTimeline", {})
    for char_name, cinfo in chars_timeline.items():
        pure_cname = re.sub(r'[（\(].*?[）\)]', '', char_name).strip()
        birth_year = cinfo.get("birthYear")
        death_year = cinfo.get("deathYear")
        first_chapter = cinfo.get("firstAppearanceChapter", 1)
        allowed_volume = cinfo.get("allowedStartVolume", 1)

        # 检查是否登场或在正文中被深度描写
        is_in_text = (pure_cname in raw_text) or (char_name in raw_text)

        # 4.1 理论实岁核验
        expected_age = None
        if birth_year is not None and chapter_world_year is not None:
            expected_age = chapter_world_year - int(birth_year)

        if is_in_text and expected_age is not None:
            # 校验正文中是否出现关于该角色的错误年龄描写
            for da in detected_ages:
                if pure_cname in da["snippet"] or (char_name in da["snippet"]):
                    diff = abs(da["age"] - expected_age)
                    if diff >= 1:
                        issues.append(
                            f"时间轴年龄严重冲突 (P0): 角色 [{pure_cname}] 在当前世界年份 {chapter_world_year} 年理论实岁为 {expected_age} 岁"
                            f"（出生年 {birth_year}），但在正文「{da['snippet']}」中被描述为「{da['raw']}」（误差 {diff} 岁）！"
                        )
                    else:
                        info.append(f"角色 [{pure_cname}] 年龄表述准确 ({da['raw']})，与理论实岁 {expected_age} 岁完全吻合。")

        # 4.2 生命周期边界核验 (未出生 / 已阵亡)
        if is_in_text and birth_year is not None and chapter_world_year is not None and chapter_world_year < int(birth_year):
            issues.append(
                f"角色时空悖论 (P0): 角色 [{pure_cname}] 设定出生于 {birth_year} 年，而当前世界年份为 {chapter_world_year} 年，"
                f"该角色尚未出生，严禁作为实体角色登场！"
            )

        if is_in_text and death_year is not None and chapter_world_year is not None and chapter_world_year > int(death_year):
            # 检查是否仅仅作为回忆
            memory_keywords = ["回忆", "当年", "曾经", "音容", "旧部", "牺牲", "墓碑", "抚恤", "遗物"]
            is_just_memory = any(k in raw_text[max(0, raw_text.find(pure_cname)-30):raw_text.find(pure_cname)+30] for k in memory_keywords)
            if not is_just_memory:
                issues.append(
                    f"生死因果冲突 (P0): 角色 [{pure_cname}] 设定已于 {death_year} 年阵亡，当前章节时间已过该节点，"
                    f"正文却出现其现场活动，严禁无故复活！"
                )

        # 4.3 登场时机拦截 (第一卷严禁出现后续分卷登场角色的现场互动)
        if is_in_text and first_chapter and chapter_num > 0 and chapter_num < int(first_chapter):
            # 后续登场的角色，不得提前出现在当前章的现场活动中
            mention_in_card = card_file and (pure_cname in card_text)
            # 排除单纯的旁人提起或背景提及，捕捉实体动作或对话
            action_match = re.search(rf'{pure_cname}[^，。！？\n]{{0,15}}[说道问喊听走跑笑怒跳看叹呼冲跃]', raw_text)
            if mention_in_card or action_match:
                issues.append(
                    f"角色登场时序越界 (P0): 角色 [{pure_cname}] 规划于第 {first_chapter} 章（第 {allowed_volume} 卷）正式入场，"
                    f"当前仅为第 {chapter_num} 章，正文却出现其实体对话或现场动作，属于早产登场严重违规！"
                )

        # 4.4 人生阶段与禁令约束
        life_stages = cinfo.get("lifeStages", [])
        if is_in_text and life_stages and expected_age is not None:
            for stage in life_stages:
                s_start = stage.get("startYear", 0)
                s_end = stage.get("endYear", 9999)
                if s_start <= chapter_world_year <= s_end:
                    stage_role = stage.get("role", "")
                    for forbidden_action in stage.get("forbidden", []):
                        if forbidden_action in raw_text:
                            issues.append(
                                f"角色生命阶段冲突 (P1): 角色 [{pure_cname}] 在 {chapter_world_year} 年处于 [{stage_role}] 阶段，"
                                f"明确禁止 [{forbidden_action}]，但正文触发了该违禁行为！"
                            )

    # 5. 世界主线事件时刻表合规性校验
    world_events = timeline_data.get("worldEventsTimeline", [])
    for ev in world_events:
        ev_year = ev.get("year", 0)
        ev_month = ev.get("month", 0)
        ev_desc = ev.get("event", "")
        ev_status = ev.get("status", "")
        keywords = ev.get("keywords", [ev_desc[:10]])

        # 检查未来事件是否被提前当做既成事实剧透
        if chapter_world_year is not None and (ev_status in ("future_forbidden_early_reveal", "future") or (type(ev_year) is int and ev_year > chapter_world_year)):
            for kw in keywords:
                if len(kw) >= 3 and kw in raw_text:
                    # 检查是否写成了已成事实 (如 "已经覆灭", "早已陷落", "爆发多年")
                    context_pat = rf'{re.escape(kw)}[^\n。！？]{{0,15}}(?:早已|已经|悉数|完全|彻底|覆灭|陷落|阵亡|爆发)'
                    if re.search(context_pat, raw_text):
                        issues.append(
                            f"世界主线因果颠倒/严重早产剧透 (P0): 主线大事件 [{ev_desc}] 设定发生在 {ev_year} 年，"
                            f"当前时间为 {chapter_world_year} 年，但正文中已将其表述为既成事实！"
                        )

    # 6. 环境气候与反季节描写核查
    cold_seasons = ["冬", "寒冬", "晚冬", "深冬", "初冬", "严寒"]
    is_cold_baseline = any(s in baseline_season for s in cold_seasons) or (baseline_weather and "雪" in baseline_weather)
    if is_cold_baseline:
        anti_winter_patterns = [
            (r'蝉鸣|蛙声|蛙鸣', "盛夏鸣虫"),
            (r'烈日炎炎|骄阳似火|酷暑难耐|酷热', "盛夏酷热"),
            (r'绿树成荫|春花烂漫|满山翠绿', "春夏季繁茂植被"),
        ]
        for pat, desc in anti_winter_patterns:
            m = re.search(pat, raw_text)
            if m:
                # 排除显式的回忆与梦境比喻
                snippet = raw_text[max(0, m.start()-15):min(len(raw_text), m.end()+15)]
                if not any(k in snippet for k in ["宛如", "犹如", "仿佛", "恍若", "梦见", "做梦", "回忆起", "忆及当年"]):
                    issues.append(
                        f"自然天候时空矛盾 (P1): 世界基线当前为 [{baseline_season}·{baseline_weather}]，"
                        f"但正文「{snippet}」出现反季节描写 [{m.group(0)}]（属于{desc}），破坏世界观可信度！"
                    )

    # 7. 长距离地理位移耗时核验
    travel_matrix = timeline_data.get("travelConstraintMatrix", {})
    travel_config = load_project_config(project_dir)["review"]
    location_terms = travel_config["travel_location_terms"]
    instant_terms = travel_config["instant_travel_terms"]
    fast_travel_pairs = [
        ("(?:" + "|".join(map(re.escape, location_terms)) + ")",
         "(?:" + "|".join(map(re.escape, instant_terms)) + ")")
    ] if location_terms and instant_terms else []
    for loc_pat, speed_pat in fast_travel_pairs:
        if re.search(loc_pat, raw_text) and re.search(speed_pat, raw_text):
            warnings.append("检测到大尺度地理词与瞬时位移词同现，请核实位移耗时是否符合世界观物理/交通规则")
            break

    status = "BLOCKED" if issues else ("WARNING" if warnings else "PASS")
    return {
        "status": status,
        "chapter_world_year": chapter_world_year,
        "baseline_season": baseline_season,
        "detected_ages": detected_ages,
        "issues": issues,
        "warnings": warnings,
        "info": info
    }


def check_plot_and_status_continuity(content: dict, project_dir: Path) -> dict:
    """情节因果合理性与生理/伤病状态继承核验"""
    raw_text = content["raw_text"]
    issues = []
    warnings = []
    info = []

    state_file = project_dir / "07-创作记忆" / "人物实时状态.md"
    if not state_file.exists():
        return {"status": "pass", "issues": [], "warnings": ["未找到 人物实时状态.md，跳过状态继承比对"]}

    with open(state_file, 'r', encoding='utf-8') as f:
        state_text = f.read()

    rows = [line.strip() for line in state_text.split('\n') if line.strip().startswith('|') and not line.startswith('| :---')]
    char_states = {}
    if len(rows) > 1:
        for row in rows[1:]:
            cols = [c.strip() for c in row.split('|')[1:-1]]
            if cols:
                name = cols[0].replace('*', '').strip()
                pure_name = re.sub(r'[（\(].*?[）\)]', '', name).strip()
                char_states[pure_name] = {
                    "raw_row": row,
                    "condition": cols[2] if len(cols) > 2 else "",
                    "equipment": cols[3] if len(cols) > 3 else "",
                    "known_info": cols[4] if len(cols) > 4 else "",
                    "forbidden_info": cols[5] if len(cols) > 5 else ""
                }

    severe_injury_keywords = ["骨折", "骨裂", "重伤", "断臂", "断腿", "失血", "中毒", "虚弱", "昏迷", "濒死", "失明", "肋骨挫伤"]
    miracle_actions = ["健步如飞", "飞身跃起", "全速狂奔", "双手横推", "力拔千钧", "毫发无损", "挥洒自如", "毫无痛感"]

    for char_name, s in char_states.items():
        if char_name in raw_text:
            cond = s["condition"]
            has_injury = any(k in cond for k in severe_injury_keywords)
            if has_injury:
                for action in miracle_actions:
                    if action in raw_text:
                        issues.append(
                            f"生理伤病因果矛盾 (P1): 角色 [{char_name}] 实时状态记录为 [{cond}]，"
                            f"但在本章出现了超常动作描写 [{action}]，未体现伤势阻碍或合理治愈过程！"
                        )
                info.append(f"角色 [{char_name}] 当前处于生理伤病/负重状态: {cond}")

    return {
        "status": "fail" if issues else ("warn" if warnings else "pass"),
        "issues": issues,
        "warnings": warnings,
        "info": info
    }


def check_persona_and_constraints(content: dict, project_dir: Path, chapter_path: Path = None) -> dict:
    """主角及登场角色人设契合度、负面禁令清单、情报边界与写前小传完备性核验"""
    raw_text = content["raw_text"]
    issues = []
    warnings = []
    info = []

    char_dir = project_dir / "02-人物"
    chars_to_check = []
    if char_dir.exists():
        for f in char_dir.rglob("*.md"):
            if f.name not in ["人物总表.md", "人物关系与冲突.md", "README.md"]:
                if f.parent == char_dir:
                    sub_match = any((char_dir / sub / f.name).exists() for sub in ["主角", "配角", "辅助角色"])
                    if sub_match:
                        continue
                chars_to_check.append(f)

    for cfile in chars_to_check:
        with open(cfile, 'r', encoding='utf-8') as f:
            ctext = f.read()

        cname = cfile.stem
        cname = re.sub(r'^第\d+章[-_]', '', cname).strip()
        title_m = re.search(r'#\s*(?:人物档案|辅助角色档案)[：:]\s*(.+)', ctext)
        if title_m:
            cname = title_m.group(1).strip()
        pure_cname = re.sub(r'[（\(].*?[）\)]', '', cname).strip()
        if not pure_cname:
            pure_cname = cname

        if pure_cname not in raw_text and cname not in raw_text:
            continue

        # 1. 提取【禁止偏离清单】
        prohibited_section = re.search(r'###?\s*(?:10[、\.]\s*)?禁止偏离清单[^\n]*\n(.*?)(?=\n##|\Z)', ctext, re.DOTALL)
        if prohibited_section:
            prohibited_text = prohibited_section.group(1)
            prohibited_items = [
                line.strip().lstrip('-* 0123456789.、')
                for line in prohibited_text.split('\n')
                if line.strip() and not line.strip().startswith('#')
            ]
            for item in prohibited_items:
                if len(item) < 4:
                    continue
                key_match = re.search(r'(?:严禁|绝不|不得|不可|禁止)(.*?)(?:[，。；\n]|$)', item)
                if key_match:
                    rule_target = key_match.group(1).strip()
                    if rule_target and len(rule_target) >= 2 and rule_target in raw_text:
                        warnings.append(
                            f"角色 [{pure_cname}] 疑似触碰禁止偏离项: 正文出现关键词 [{rule_target}]（对应禁令: {item}），请复核人设合理性"
                        )

        # 2. 提取【未知警戒线】核验（严防全知剧透）
        unknown_section = re.search(r'-\s*\*\*未知警戒线[^\*]*\*\*：\s*(.*?)(?=\n-|\Z)', ctext)
        if unknown_section:
            unknown_text = unknown_section.group(1).strip()
            unknown_clues = [c.strip() for c in re.split(r'[,，;；、]', unknown_text) if len(c.strip()) >= 3]
            for clue in unknown_clues:
                for d in content["dialogues"]:
                    if clue in d:
                        issues.append(
                            f"情报边界泄露 (全知剧透 P1): 角色 [{pure_cname}] 在台词中直接说出未知警戒线机密 [{clue}]（台词: “{d}”）！"
                        )

    # 3. 检查任务卡中的出场人物是否均有小传主档
    if chapter_path and char_dir.exists():
        ch_num = content["chapter_number"]
        card_file, card_text = find_chapter_task_card(project_dir, ch_num)
        if card_text:
            char_section = re.search(r'-\s*\*\*出场人物[^\*]*\*\*[^\n]*\n(.*?)(?=\n-\s*\*\*|\n##|\Z)', card_text, re.DOTALL)
            if char_section:
                for line in char_section.group(1).split('\n'):
                    line = line.strip().lstrip('-* 0123456789.、')
                    if not line or "暂未登场" in line or "（一次性）" in line or "(一次性)" in line:
                        continue
                    bold_m = re.search(r'\*\*([^\*]+)\*\*', line)
                    cand_name = bold_m.group(1).strip() if bold_m else line.split('：')[0].split(':')[0].strip()
                    cand_pure = re.sub(r'[（\(].*?[）\)]', '', cand_name).strip()
                    if cand_pure in ["主角", "配角", "辅助角色", "出场人物", "待定", "无"] or len(cand_pure) < 2:
                        continue
                    has_profile = any(cand_pure in profile.name for profile in char_dir.rglob("*.md"))
                    if not has_profile and (cand_pure in raw_text or cand_name in raw_text):
                        warnings.append(
                            f"写前小传核验提示: 本章出场角色 [{cand_pure}] 在 02-人物/ 下未找到独立档案。"
                            f"理论上只要多次出现的人物都要设立小传（作为性格基石与合规质检输入），除纯一次性龙套外请补齐！"
                        )

    return {
        "status": "fail" if issues else ("warn" if warnings else "pass"),
        "issues": issues,
        "warnings": warnings,
        "info": info
    }


def check_language_and_ai_patterns(content: dict) -> dict:
    """语言自然度与 AI 式模式扫描（合并自 scan_chapter 与 Humanizer-zh）"""
    lines_with_no = content["lines_with_no"]
    raw_text = content["raw_text"]
    hits = []
    warnings = []

    # 1. 扫描 5 类典型候选模式
    for label, pattern in REVIEW_PATTERNS.items():
        for line_no, line in lines_with_no:
            for match in re.finditer(pattern, line):
                left = max(0, match.start() - 24)
                right = min(len(line), match.end() + 24)
                hits.append({
                    "type": label,
                    "line": line_no,
                    "match": match.group(),
                    "context": line[left:right].strip()
                })

    # 2. 公文式动词扫描 (说人话)
    official_verbs = [
        (r'(?:进行|予以|给予)了?(?:一轮|一番|致命|沉重|持续|全面)?[^，。\n]{0,6}(?:打击|反击|追击|搜寻|观察|救治|试探|攻击|惩戒)', "公文式翻译腔动词 (进行/予以+动词)"),
        (r'作为一(?:个|名)[^，。\n]{2,10}，他', "公文式前缀 (作为……，他……)")
    ]
    for pat, desc in official_verbs:
        for m in re.finditer(pat, raw_text):
            warnings.append(f"检测到 {desc}: '{m.group(0)}'，请按'说人话'法则改写为具象动作白描")
            break

    # 3. 破折号过多
    dash_count = raw_text.count("——")
    if dash_count >= 12:
        warnings.append(f"全章出现 {dash_count} 处破折号(——)，建议适度精简，避免过密排比打断阅读节奏")

    return {
        "status": "warn" if warnings or hits else "pass",
        "patterns_hits": hits,
        "patterns_count": len(hits),
        "warnings": warnings
    }


def compute_seven_dimensions(wc_res, time_res, plot_res, persona_res, lang_res) -> dict:
    """计算七维评分与总分（满分 100 分）"""
    scores = {}

    # 1. 剧情因果与信息证据链 (权重 20)
    score_plot = 10
    if plot_res["issues"]:
        score_plot -= len(plot_res["issues"]) * 3
    if plot_res["warnings"]:
        score_plot -= len(plot_res["warnings"]) * 1
    scores["plot_causality"] = max(2, min(10, score_plot))

    # 2. 时空、物理与战术合理性 (权重 15)
    score_time = 10
    if time_res["issues"]:
        score_time -= len(time_res["issues"]) * 4
    if time_res["warnings"]:
        score_time -= len(time_res["warnings"]) * 1
    scores["spacetime_tactics"] = max(1, min(10, score_time))

    # 3. 设定/装备与跨章连续性 (权重 15)
    score_setting = 9
    if plot_res["issues"]:
        score_setting -= 2
    scores["continuity_setting"] = max(3, min(10, score_setting))

    # 4. 人物动机与群像真实度 (权重 15)
    score_persona = 10
    if persona_res["issues"]:
        score_persona -= len(persona_res["issues"]) * 3
    if persona_res["warnings"]:
        score_persona -= len(persona_res["warnings"]) * 1
    scores["character_depth"] = max(2, min(10, score_persona))

    # 5. 节奏、可读性与追更欲 (权重 15)
    score_rhythm = 9
    # 字数是工程交付条件，不得直接扣减「节奏与可读性」文学质量分。
    # 以下分数仅为历史兼容的机械参考，不能冒充完整语义审稿。
    scores["pacing_readability"] = max(3, min(10, score_rhythm))

    # 6. 语言自然度与AI式模式控制 (权重 15)
    score_lang = 10  # 机械参考，不按候选数计算 AI 味分数
    if lang_res["warnings"]:
        score_lang -= 1
    scores["language_naturalness"] = max(2, min(10, score_lang))

    # 7. 悬念、伏笔与信息释放 (权重 5)
    score_suspense = 9
    scores["suspense_foreshadow"] = max(4, min(10, score_suspense))

    weights = {
        "plot_causality": 20,
        "spacetime_tactics": 15,
        "continuity_setting": 15,
        "character_depth": 15,
        "pacing_readability": 15,
        "language_naturalness": 15,
        "suspense_foreshadow": 5
    }

    total_score = sum(scores[k] * weights[k] / 10 for k in weights)
    return {
        "dimension_scores": scores,
        "total_score": round(total_score, 1),
        "scoring_kind": "MECHANICAL_REFERENCE_ONLY",
        "quality_review_status": "NOT_EVALUATED"
    }


def generate_review_report_markdown(result: dict, project_dir: Path) -> str:
    """生成符合固定审稿报告模板 Markdown"""
    ch_title = result["chapter_title"]
    ch_num = result["chapter_number"]
    total_score = result["scoring"]["total_score"]
    dim_scores = result["scoring"]["dimension_scores"]
    overall_status = result["overall_status"]
    han_count = result["han_words"]
    min_words = result["min_words_required"]
    max_words = result["max_words_suggested"]
    time_info = result["dimensions"]["timeline_check"]

    today_str = datetime.date.today().isoformat()
    project_name = project_dir.name

    report = []
    report.append(f"# 《{project_name}》章节机械质检参考报告｜第{ch_num:03d}章\n")
    report.append("## 0. 审查元信息\n")
    report.append(f"- **章节标题**：{ch_title}")
    report.append(f"- **审查日期**：{today_str}")
    report.append(f"- **正文计数**：正文汉字数 **{han_count}** 字（达标线：{min_words}-{max_words} 字）｜非空白字符数 {result['non_space_chars']} 字")
    report.append(f"- **工程交付门禁（机械）**：**{overall_status}**")
    report.append("- **完整小说质量审稿判定**：**未执行／待全文及设定人工核验**（字数不属于质量P级）")
    report.append(f"- **阻断原因**：{'无' if not result['issues'] else '存在 ' + str(len(result['issues'])) + ' 项阻断性问题（必须修改）'}\n")

    report.append("## 1. 核心维度量化评价\n")
    report.append(f"- **机器指标参考（非完整质量总分）**：**{total_score}/100**；须以0—10节人工审查报告为正式质量评分")
    report.append(f"- **时空、物理与战术合理性**：{dim_scores['spacetime_tactics']}/10（世界主线时间、主角理论年龄、天候位移吻合）")
    report.append(f"- **剧情因果与信息证据链**：{dim_scores['plot_causality']}/10（任务决策闭环、战术摩擦、无机械降神）")
    report.append(f"- **人物动机与小传合规性**：{dim_scores['character_depth']}/10（符合小传性格底色、未触犯禁止偏离清单）")
    report.append(f"- **设定/装备与跨章连续性**：{dim_scores['continuity_setting']}/10（装备与伤病继承合规）")
    report.append(f"- **节奏、可读性与追更欲**：{dim_scores['pacing_readability']}/10（张弛有度、推进明确）")
    report.append(f"- **语言自然度与AI式模式控制**：{dim_scores['language_naturalness']}/10（动作具象、说人话）")
    report.append("- **AI味专项**：未审查，须按统一协议逐项人工裁决。\n")

    report.append("## 2. 逐项核验细节对账\n")
    report.append("### 1. 时间轴与多主角年龄/主线事件合规性核验")
    report.append(f"- **世界年份锚定**：{str(time_info['chapter_world_year']) + ' 年' if time_info['chapter_world_year'] is not None else '待确认'} | 基线季节：{time_info['baseline_season'] or '待确认'}")
    for inf in time_info["info"]:
        report.append(f"  - [x] {inf}")
    report.append("")

    report.append("### 2. 生理伤病与因果连续性")
    for inf in result["dimensions"]["plot_check"]["info"]:
        report.append(f"  - [x] {inf}")
    report.append("  - [ ] 弹药消耗与装备状态：**待审稿人核对动态账本**。\n")

    report.append("### 3. 人物小传合规性与负面禁令")
    report.append("  - [ ] 人物行为与小传禁止偏离清单：**待真实语义核验**。")
    report.append("  - [ ] 情报边界与人物实际所知：**待真实语义核验**。\n")

    report.append("### 4. 语言打磨与套式控制")
    report.append(f"  - 扫描到候选模式命中：{result['dimensions']['language_check']['patterns_count']} 处（未经全文语义审稿）")
    report.append("  - AI味专项：未审查，候选不能自动裁决。\n")

    if result["issues"]:
        report.append("## 3. 阻断性问题清单与可执行最小修改建议\n")
        report.append("| ID | 级别 | 类别 | 冲突说明 | 最小修改建议 |")
        report.append("|---|---|---|---|---|")
        for idx, iss in enumerate(result["issues"], 1):
            report.append(f"| L-{idx:03d} | P0/P1 | 一致性 | {iss} | 根据时间轴总账与主线设定调整时间/年龄/行为描写 |")
        report.append("")

    if result["warnings"]:
        report.append("## 4. 警示与关注项 (Suggestions)\n")
        for idx, warn in enumerate(result["warnings"], 1):
            report.append(f"- **W-{idx:03d}**：{warn}")
        report.append("")

    report.append("## 5. 结论与下一步处置\n")
    if overall_status == "PASS":
        report.append("- [x] **【工程机械 PASS】本次已运行的机械规则无阻断；仍需独立完成完整语义质量审稿和工程其他门禁。**")
    elif overall_status == "WARNING":
        report.append("- [ ] **【工程机械 WARNING】存在候选警示，需人工裁决；不得宣称文学质量已通过。**")
    else:
        report.append("- [ ] **【工程机械 BLOCKED】存在工程阻断（可能包含篇幅）；未修正前不得交付。不可推断为文学质量P1。**")

    return '\n'.join(report)


def verify_chapter(
    chapter_path: Path,
    project_dir: Path,
    min_words: int = None,
    max_words: int = None
) -> dict:
    """机械一致性与交付候选质检；不自动完成全文文学质量审稿。"""
    min_words, max_words = chapter_limits(chapter_path, project_dir, min_words, max_words)
    content = extract_chapter_content(chapter_path)

    wc_result = check_word_count(content, min_words, max_words)
    timeline_result = check_timeline_and_world_events(content, project_dir, chapter_path)
    plot_result = check_plot_and_status_continuity(content, project_dir)
    persona_result = check_persona_and_constraints(content, project_dir, chapter_path)
    lang_result = check_language_and_ai_patterns(content)

    all_issues = wc_result["issues"] + timeline_result["issues"] + plot_result["issues"] + persona_result["issues"]
    all_warnings = wc_result["warnings"] + timeline_result["warnings"] + plot_result["warnings"] + persona_result["warnings"] + lang_result["warnings"]

    overall_status = "BLOCKED" if all_issues else ("WARNING" if all_warnings else "PASS")

    scoring = compute_seven_dimensions(wc_result, timeline_result, plot_result, persona_result, lang_result)

    return {
        "chapter_file": str(chapter_path),
        "chapter_title": content["title"],
        "chapter_number": content["chapter_number"],
        "han_words": content["han_words"],
        "non_space_chars": content["non_space_chars"],
        "min_words_required": min_words,
        "max_words_suggested": max_words,
        "overall_status": overall_status,
        "delivery_gate_status": overall_status,
        "quality_review_status": "NOT_EVALUATED",
        "issues_count": len(all_issues),
        "warnings_count": len(all_warnings),
        "issues": all_issues,
        "warnings": all_warnings,
        "scoring": scoring,
        "dimensions": {
            "word_count_check": wc_result,
            "timeline_check": timeline_result,
            "plot_check": plot_result,
            "persona_check": persona_result,
            "language_check": lang_result
        }
    }


def main():
    parser = argparse.ArgumentParser(description="单章多维一致性与合规性核查工具")
    parser.add_argument("chapter_file", type=str, help="待检测的章节文件路径")
    parser.add_argument("--project-dir", type=str, default=None, help="小说工程根目录")
    parser.add_argument("--min-words", type=int, default=None, help="覆盖小说项目最低字数")
    parser.add_argument("--max-words", type=int, default=None, help="覆盖小说项目建议上限")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")
    parser.add_argument("--report", type=str, default=None, help="输出固定模板 Markdown 审稿报告文件路径")
    parser.add_argument("--auto-report", action="store_true", help="自动沉淀报告至 08-审稿/第{XX}章-质检报告.md")

    args = parser.parse_args()
    chapter_path = Path(args.chapter_file).resolve()

    if not chapter_path.exists():
        print(f"❌ 章节文件不存在: {chapter_path}", file=sys.stderr)
        sys.exit(2)

    project_dir = locate_project_dir(chapter_path, args.project_dir)
    min_words, max_words = chapter_limits(chapter_path, project_dir, args.min_words, args.max_words)
    result = verify_chapter(chapter_path, project_dir, min_words, max_words)

    # 报告自动生成处理
    report_md = None
    if args.report or args.auto_report:
        report_md = generate_review_report_markdown(result, project_dir)
        target_path = None
        if args.report:
            target_path = Path(args.report).resolve()
        elif args.auto_report:
            review_dir = project_dir / "08-审稿"
            review_dir.mkdir(parents=True, exist_ok=True)
            ch_num = result["chapter_number"]
            target_path = review_dir / f"第{ch_num:03d}章-质检报告.md"

        if target_path:
            with open(target_path, 'w', encoding='utf-8') as rf:
                rf.write(report_md)
            result["report_path"] = str(target_path)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=" * 65)
        print(f"📋 章节质检报告: {result['chapter_title']} (第{result['chapter_number']:03d}章)")
        print(f"📊 正文汉字: {result['han_words']} 字 (红线: {result['min_words_required']}-{result['max_words_suggested']} 字) | 非空白: {result['non_space_chars']}")
        print(f"🎯 机械参考指标（非正式文学质量分）: {result['scoring']['total_score']}/100 | 模式候选: {result['dimensions']['language_check']['patterns_count']} 处（AI味未审查）")
        print(f"🚦 工程机械门禁: {result['overall_status']}；完整质量审稿: 未执行（需人工阅读及设定对账）")
        print("=" * 65)

        if result.get("report_path"):
            print(f"📝 质检报告已写入: {result['report_path']}")

        if result["issues"]:
            print("\n❌ 阻断性问题 (必须修正才能归档/OK):")
            for i, issue in enumerate(result["issues"], 1):
                print(f"  {i}. {issue}")

        if result["warnings"]:
            print("\n⚠️ 警示与优化项 (建议关注):")
            for i, warn in enumerate(result["warnings"], 1):
                print(f"  {i}. {warn}")

        if not result["issues"] and not result["warnings"]:
            print("\n✨ 完美！四维核验与时间轴主线校验全部通过，准予进入下一阶段。")

    sys.exit(1 if result["overall_status"] == "BLOCKED" else 0)


if __name__ == "__main__":
    main()
