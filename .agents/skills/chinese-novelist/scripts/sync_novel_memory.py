#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设定与创作记忆同步与冲突校验工具
用于保证小说工程的单一可信源 (SSOT)、非权威辅助视图编译与实时状态校验。
支持三级人物分类体系（主角、配角、辅助角色+章节）的递归识别与分类索引编译。

用法:
  python sync_novel_memory.py <工程目录> [--compile-views] [--check-conflicts] [--json]

示例:
  python sync_novel_memory.py ./my-story --compile-views --check-conflicts
"""

import argparse
import io
import json
import os
import re
import sys
from pathlib import Path

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def extract_field(pattern: str, text: str) -> str:
    """提取字段内容，限定在单行范围内，避免跨行匹配"""
    m = re.search(pattern, text)
    if m:
        val = m.group(1).strip()
        if val:
            return val
    return ""


def extract_character_summary(char_file: Path, project_dir: Path) -> dict:
    """从单个独立人物主档解析提取关键信息，用于编译速查摘要"""
    with open(char_file, 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. 提取角色姓名
    raw_name = char_file.stem
    title_match = re.search(r'#\s*(?:人物档案|辅助角色档案)[：:]\s*(.+)', text)
    if title_match:
        raw_name = title_match.group(1).strip()

    # 剥离编号章或不编号插章前缀，避免将「第一卷插章005-角色甲」当作人物本名。
    name = re.sub(r'^(?:第\d+章|第?[一二三四五六七八九十百0-9]+卷(?:插章|尾声)\d+)[-_]', '', raw_name).strip()
    # 剥离人名可能包含的括号别名，例如 张三（别名） -> 张三
    pure_name = re.sub(r'[（\(].*?[）\)]', '', name).strip()
    if not pure_name:
        pure_name = name

    # 2. 判定类别 (主角 / 配角 / 辅助角色)
    # 人物目录允许在 配角/ 和 辅助角色/ 下继续增加初始阵营子目录；
    # 因此不能依赖 char_file.parent.name（这里一般是角色的初始阵营）。
    try:
        classification_parts = char_file.relative_to(project_dir / "02-人物").parts
    except ValueError:
        classification_parts = char_file.parts
    category = "配角"
    if "主角" in classification_parts:
        category = "主角"
    elif "辅助角色" in classification_parts:
        category = "辅助角色"
    elif "配角" in classification_parts:
        category = "配角"
    else:
        # 从内容或文件名判定
        if re.search(r'-\s*\*\*角色定位\*\*：\s*.*主角', text) or pure_name == "主角":
            category = "主角"
        elif re.search(r'-\s*\*\*角色定位\*\*：\s*.*辅助', text) or re.search(r'第\d+章', char_file.stem):
            category = "辅助角色"
        elif re.search(r'-\s*\*\*角色定位\*\*：\s*.*配角', text):
            category = "配角"

    # 3. 提取首次登场章节
    first_ch = extract_field(r'-\s*\*\*首次登场[章节]*\*\*：[^\S\r\n]*(.*)', text)
    if not first_ch:
        # 尝试从文件名提取如 第001章
        ch_stem_match = re.search(r'(第\d+章)', char_file.stem)
        if ch_stem_match:
            first_ch = ch_stem_match.group(1)
        elif re.search(r'^第?[一二三四五六七八九十百0-9]+卷(?:插章|尾声)\d+', char_file.stem):
            first_ch = re.search(r'^第?[一二三四五六七八九十百0-9]+卷(?:插章|尾声)\d+', char_file.stem).group(0)
        elif category == "主角":
            first_ch = "第一卷/第001章"
        else:
            first_ch = "待定"

    # 4. 提取所属阵营与身份
    identity = (
        extract_field(r'-\s*\*\*所属阵营.*?(?:身份|编制|历史编制)\*\*：[^\S\r\n]*(.*)', text) or
        extract_field(r'-\s*\*\*(?:所属阵营|阵营|身份|职业)[/\\]?(?:与|/|\\)?(?:身份|职业)?\*\*：[^\S\r\n]*(.*)', text) or
        "未定义"
    )

    # 5. 提取显性性格与行为要点
    personality = (
        extract_field(r'-\s*\*\*显性性格\*\*：[^\S\r\n]*(.*)', text) or
        extract_field(r'-\s*\*\*性格核心\*\*：[^\S\r\n]*(.*)', text) or
        extract_field(r'-\s*\*\*性格与言行特征\*\*：[^\S\r\n]*(.*)', text) or
        "未定义"
    )

    # 6. 提取能力特长或核心功能
    ability = (
        extract_field(r'-\s*\*\*能力特长\*\*：[^\S\r\n]*(.*)', text) or
        extract_field(r'-\s*\*\*评级与特长\*\*：[^\S\r\n]*(.*)', text) or
        extract_field(r'-\s*\*\*特长[/\\]技能\*\*：[^\S\r\n]*(.*)', text) or
        ""
    )

    core_function = (
        extract_field(r'-\s*\*\*本章核心作用\*\*：[^\S\r\n]*(.*)', text) or
        extract_field(r'-\s*\*\*剧情功能[与使命]*\*\*：[^\S\r\n]*(.*)', text) or
        extract_field(r'-\s*\*\*核心功能[与动机]*\*\*：[^\S\r\n]*(.*)', text) or
        ""
    )

    # 相对路径 (以 02-人物 开头)
    try:
        rel_path = char_file.relative_to(project_dir).as_posix()
    except Exception:
        rel_path = f"02-人物/{char_file.name}"

    return {
        "file": char_file.name,
        "name": name,
        "pure_name": pure_name,
        "category": category,
        "first_appearance": first_ch,
        "identity": identity,
        "personality": personality,
        "ability": ability if ability else (core_function if core_function else "未定义"),
        "core_function": core_function,
        "rel_path": rel_path
    }


def compile_views(project_dir: Path) -> dict:
    """从权威源编译生成辅助视图：03-文风基准.md, 99-章节摘要.md"""
    char_dir = project_dir / "02-人物"
    summary_list = []

    if char_dir.exists():
        # 递归扫描所有人物 Markdown 文件
        for char_file in sorted(char_dir.rglob("*.md")):
            if char_file.name in ["人物总表.md", "人物关系与冲突.md", "README.md"]:
                continue
            # 若平铺在根目录下且子目录已建立同名主档，自动跳过以兼容迁移
            if char_file.parent == char_dir:
                sub_match = any((char_dir / sub / char_file.name).exists() for sub in ["主角", "配角", "辅助角色"])
                if sub_match:
                    continue
            summary_list.append(extract_character_summary(char_file, project_dir))

    # 按主角、配角、辅助角色分类
    protagonists = [c for c in summary_list if c["category"] == "主角"]
    supporting = [c for c in summary_list if c["category"] == "配角"]
    auxiliary = [c for c in summary_list if c["category"] == "辅助角色"]
    others = [c for c in summary_list if c["category"] not in ["主角", "配角", "辅助角色"]]

    # 辅助角色按章节排序
    def sort_key_aux(item):
        match = re.search(r'(\d+)', item.get("first_appearance", ""))
        return int(match.group(1)) if match else 999999
    auxiliary.sort(key=sort_key_aux)

    # 人物不再生成根目录重复快照；直接维护 02-人物/ 独立档案与人物总表。

    # 同步 07-创作记忆/章节摘要.md 到 99-章节摘要.md
    mem_summary_path = project_dir / "07-创作记忆" / "章节摘要.md"
    legacy_summary_path = project_dir / "99-章节摘要.md"
    if mem_summary_path.exists():
        with open(mem_summary_path, 'r', encoding='utf-8') as f:
            sum_text = f.read()
        with open(legacy_summary_path, 'w', encoding='utf-8') as f:
            f.write("# 章节摘要（只读镜像视图）\n\n> 权威源位于 `07-创作记忆/章节摘要.md`。\n\n" + sum_text)

    # 编译 03-文风基准.md（双源动态加权文风演进视图）
    style_res = compile_style_view(project_dir)

    return {
        "status": "success",
        "compiled_characters": len(summary_list),
        "protagonists": len(protagonists),
        "supporting": len(supporting),
        "auxiliary": len(auxiliary),
        "style_evolution": style_res
    }


def compile_style_view(project_dir: Path) -> dict:
    """从 04-文风/ 权威源与已写正文编译生成 03-文风基准.md (双源动态加权文风演进视图)"""
    style_dir = project_dir / "04-文风"
    body_dir = project_dir / "06-正文"
    legacy_style_file = project_dir / "03-文风基准.md"

    # 1. 扫描正文统计篇幅
    chapter_files = []
    if body_dir.exists():
        for f in body_dir.rglob("*.md"):
            if re.search(r'第\s*\d+\s*章', f.name):
                chapter_files.append(f)
    else:
        for f in project_dir.glob("*.md"):
            if re.search(r'第\s*\d+\s*章', f.name) and not any(k in f.name for k in ["审稿", "任务卡", "质检", "大纲", "人物"]):
                chapter_files.append(f)

    def sort_ch(p: Path):
        m = re.search(r'第\s*(\d+)\s*章', p.name)
        return int(m.group(1)) if m else 999999

    unique_files = {f.name: f for f in chapter_files}
    sorted_files = sorted(unique_files.values(), key=sort_ch)

    completed_chapters = len(sorted_files)
    total_chars = 0
    recent_snippets = []

    for cf in sorted_files:
        try:
            with open(cf, 'r', encoding='utf-8', errors='replace') as fp:
                t = fp.read()
                lines = [l for l in t.split('\n') if not l.startswith('#')]
                body_t = '\n'.join(lines)
                total_chars += len(re.findall(r'[\u4e00-\u9fff]', body_t))
        except Exception:
            pass

    # 提取最近/高光段落 (从后往前找 2-3 个生动段落)
    for cf in reversed(sorted_files):
        if len(recent_snippets) >= 3:
            break
        try:
            with open(cf, 'r', encoding='utf-8', errors='replace') as fp:
                t = fp.read()
            paras = [p.strip() for p in t.split('\n') if len(p.strip()) >= 80]
            for p in paras:
                c_count = len(re.findall(r'[\u4e00-\u9fff]', p))
                if 100 <= c_count <= 500:
                    if len(re.findall(r'[“「]', p)) >= 1 or len(re.findall(r'(?:斩|拔|刺|踏|冲|跃|握|抓|推|撞)', p)) >= 2:
                        recent_snippets.append((cf.stem, p))
                        break
        except Exception:
            pass

    # 2. 计算动态权重 (正文越多，参考自身的权重越重)
    if completed_chapters <= 0 or total_chars < 1500:
        ext_w, int_w = 1.00, 0.00
        phase = "阶段零·起手播种期 (外部参考 100% : 本书正文 0%)"
        desc = "正文尚未动笔或仅有引子，完全依靠外部文风参考与 Nuwa 蒸馏指纹建立起步调性。"
    elif completed_chapters == 1:
        ext_w, int_w = 0.85, 0.15
        phase = "阶段一·起步破土期 (外部参考 85% : 本书正文 15%)"
        desc = "第 1 章已定稿，开始提取黄金校准段落，外部参考仍居绝对主导。"
    elif completed_chapters == 2:
        ext_w, int_w = 0.75, 0.25
        phase = "阶段一·起步破土期 (外部参考 75% : 本书正文 25%)"
        desc = "正文语态萌芽，逐步增加对前 2 章实际节奏的参照。"
    elif completed_chapters == 3:
        ext_w, int_w = 0.65, 0.35
        phase = "阶段二·爬坡磨合期 (外部参考 65% : 本书正文 35%)"
        desc = "角色对话特色与叙事节奏初显，自身正文权重显著提升。"
    elif completed_chapters == 4:
        ext_w, int_w = 0.55, 0.45
        phase = "阶段二·爬坡磨合期 (外部参考 55% : 本书正文 45%)"
        desc = "外部参考与本书自生语感趋于平衡对撞。"
    elif completed_chapters == 5:
        ext_w, int_w = 0.45, 0.55
        phase = "阶段二·磨合定型期 (外部参考 45% : 本书正文 55%)"
        desc = "拐点出现！本书正文权重首次超越外部参考，以内生语感为主导。"
    elif 6 <= completed_chapters <= 9:
        ext_w = round(max(0.20, 0.45 - (completed_chapters - 5) * 0.05), 2)
        int_w = round(1.0 - ext_w, 2)
        phase = f"阶段三·风格定型期 (外部参考 {int(ext_w*100)}% : 本书正文 {int(int_w*100)}%)"
        desc = "本书独有行文节奏与人物语言指纹已成型，创作主要对齐自身高水准段落。"
    elif 10 <= completed_chapters <= 19:
        ext_w = round(max(0.12, 0.22 - (completed_chapters - 10) * 0.012), 2)
        int_w = round(1.0 - ext_w, 2)
        phase = f"阶段四·深度内化期 (外部参考 {int(ext_w*100)}% : 本书正文 {int(int_w*100)}%)"
        desc = "中长篇深度内化，本书正文占据绝对主导地位，外部参考退居为反模式红线规约。"
    else:
        ext_w, int_w = 0.10, 0.90
        phase = "阶段五·自成一体成熟期 (外部参考 10% : 本书正文 90%)"
        desc = "全书内生文风已臻成熟浑然一体！本书定稿正文为最高准绳，外部参考仅做底线防漂移兜底。"

    # 3. 读取权威文风源
    spec_text = ""
    if style_dir.exists():
        for sp in sorted(style_dir.glob("*.md")):
            if "规范" in sp.name or "总纲" in sp.name:
                try:
                    spec_text = sp.read_text(encoding='utf-8', errors='replace')
                    break
                except Exception:
                    pass

    # 若未找到独立规范，尝试读取现有 03-文风基准.md 的核心内容
    if not spec_text and legacy_style_file.exists():
        try:
            old_c = legacy_style_file.read_text(encoding='utf-8', errors='replace')
            # 提取二、三大文学标杆支柱 等内容
            m = re.search(r'(##\s+[一二三].*)', old_c, re.DOTALL)
            if m:
                spec_text = m.group(1)
        except Exception:
            pass

    # 4. 组装 03-文风基准.md 内容
    lines = [
        f"# 文风与叙事基准（只读编译视图）\n",
        f"> ⚠️ **重要规则**：本文件由 `sync_novel_memory.py` 自动编译更新，**严禁手动在此处修改**！",
        f"> 权威源位于 `04-文风/` 独立档案与 `06-正文/` 已定稿章节。",
        f"> **双源动态加权演进法则**：**文风不仅参考提供的外部文本，更深度参考小说已生成的正文部分；小说正文越多，参考自身的权重越重！**\n",
        f"---",
        f"",
        f"## 🧭 双源文风动态权重指示牌（Dynamic Weighting Dashboard）\n",
        f"| 指标项 | 当前数值 / 状态 | 说明与演进法则 |",
        f"| :--- | :--- | :--- |",
        f"| **已定稿章节数** | **第 {completed_chapters} 章** | 当前正文篇幅累积进度 |",
        f"| **已累积正文字数** | **{total_chars} 纯汉字** | 全书已写正文体量 |",
        f"| **当前演进阶段** | **{phase}** | {desc} |",
        f"| **外部参考文本权重** | **{int(ext_w*100)}%** | 外部语料/名家风格样章影响力（随篇幅增加平滑递减） |",
        f"| **本书自身正文权重** | **{int(int_w*100)}%** | 本书自生语调/已定型人物台词与动作白描（**正文越多权重越重**） |\n",
        f"> 💡 **写前注意力锚定指令**：在撰写下一章时，大模型必须按上述 **外部 {int(ext_w*100)}% : 自身 {int(int_w*100)}%** 的权重加载语态。正文越多，越要以本书已有高水准章节为第一模仿准绳！\n",
        f"---",
        f""
    ]

    if spec_text:
        clean_spec = re.sub(r'^#\s+.*?\n', '', spec_text)
        # 清除已有的权重指示牌与自生沉淀库避免重复
        clean_spec = re.sub(r'##\s+🧭.*?---\n*', '', clean_spec, flags=re.DOTALL)
        clean_spec = re.sub(r'##\s+.*?(?:黄金沉淀库|自生正文|校准段落).*?(?:---\n*|$)', '', clean_spec, flags=re.DOTALL)
        clean_spec = re.sub(r'---\s*\n*---', '---', clean_spec)
        clean_spec = clean_spec.strip()
        if clean_spec and clean_spec != "---":
            if not clean_spec.startswith("## 一、"):
                lines.append("## 一、全书文风总规范与文学标杆基准\n")
            lines.append(clean_spec + "\n")
            lines.append("---\n")

    lines.append(f"## 二、本书自生正文黄金沉淀库（权重: {int(int_w*100)}%，随章节累积持续演进）\n")
    if recent_snippets:
        for ch_name, snip in recent_snippets:
            lines.append(f"### 来自【{ch_name}】的语态与对话切片：")
            lines.append(f"```markdown\n{snip}\n```\n")
    else:
        lines.append("*（第 1 章尚未定稿，暂未提取本书自生黄金段落）*\n")
    lines.append("---\n")

    try:
        with open(legacy_style_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    except Exception as e:
        print(f"⚠️ 写入 03-文风基准.md 失败: {e}", file=sys.stderr)

    return {
        "status": "success",
        "completed_chapters": completed_chapters,
        "total_chars": total_chars,
        "external_weight": ext_w,
        "internal_weight": int_w,
        "phase": phase
    }


def check_conflicts(project_dir: Path) -> dict:
    """检查设定与事实状态冲突"""
    issues = []
    warnings = []

    state_file = project_dir / "07-创作记忆" / "人物实时状态.md"
    char_dir = project_dir / "02-人物"

    if state_file.exists():
        with open(state_file, 'r', encoding='utf-8') as f:
            state_text = f.read()

        # 检查实时状态表中记录的人物是否都有对应独立档案（递归匹配）
        rows = [line.strip() for line in state_text.split('\n') if line.strip().startswith('|') and not line.startswith('| :---')]
        for row in rows[1:]:  # 跳过表头
            cols = [c.strip() for c in row.split('|')[1:-1]]
            if cols:
                name = cols[0].replace('*', '').strip()
                pure_name = re.sub(r'[（\(].*?[）\)]', '', name).strip()
                if pure_name and not any(char_dir.rglob(f"*{pure_name}*.md")):
                    warnings.append(f"实时状态表中存在角色 [{name}]，但在 02-人物/ 下未找到独立档案")

    # 检查时间轴总账 (Timeline Ledger)
    timeline_file = project_dir / "07-创作记忆" / "时间轴总账.json"
    if timeline_file.exists():
        try:
            with open(timeline_file, 'r', encoding='utf-8') as f:
                tdata = json.load(f)
            chars_timeline = tdata.get("charactersTimeline", {})
            for cname, cinfo in chars_timeline.items():
                pure_cname = re.sub(r'[（\(].*?[）\)]', '', cname).strip()
                if not any(char_dir.rglob(f"*{pure_cname}*.md")) and pure_cname != "主角":
                    warnings.append(f"时间轴总账中登记了角色 [{cname}]，但 02-人物/ 下未找到独立档案")
                age = cinfo.get("currentAge")
                birth = cinfo.get("birthYear")
                world_year = tdata.get("worldBaseline", {}).get("currentYear")
                if age is not None and birth is not None and world_year is not None:
                    expected_age = world_year - birth
                    if abs(int(age) - int(expected_age)) > 1:
                        issues.append(f"时间轴基准等式冲突: [{cname}] 登记年龄 {age} 与 (世界年 {world_year} - 出生年 {birth} = {expected_age}) 矛盾")
        except Exception as e:
            issues.append(f"解析 时间轴总账.json 失败: {str(e)}")

    # 检查写作计划与正文文件匹配
    plan_file = project_dir / "02-写作计划.json"
    if plan_file.exists():
        try:
            with open(plan_file, 'r', encoding='utf-8') as f:
                plan_data = json.load(f)
            chapters = plan_data.get("chapters", [])
            for ch in chapters:
                fpath = project_dir / ch.get("filePath", "")
                if ch.get("status") == "completed" and not fpath.exists():
                    issues.append(f"第 {ch.get('chapterNumber')} 章标记为 completed，但文件不存在: {ch.get('filePath')}")
        except Exception as e:
            issues.append(f"解析 02-写作计划.json 失败: {str(e)}")

    return {
        "status": "error" if issues else ("warning" if warnings else "pass"),
        "issues": issues,
        "warnings": warnings
    }


def main():
    parser = argparse.ArgumentParser(description="中文小说工程记忆同步与冲突校验工具")
    parser.add_argument("project_dir", type=str, help="工程根目录")
    parser.add_argument("--compile-views", action="store_true", help="从权威源编译文风与章节摘要辅助视图")
    parser.add_argument("--check-conflicts", action="store_true", help="校验动态状态与设定冲突")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")

    args = parser.parse_args()
    project_path = Path(args.project_dir).resolve()

    if not project_path.exists():
        print(f"❌ 目录不存在: {project_path}", file=sys.stderr)
        sys.exit(2)

    result = {}
    if args.compile_views or (not args.compile_views and not args.check_conflicts):
        res = compile_views(project_path)
        result["compile"] = res

    if args.check_conflicts or (not args.compile_views and not args.check_conflicts):
        conflicts = check_conflicts(project_path)
        result["conflicts"] = conflicts

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "compile" in result:
            comp = result['compile']
            print(f"✅ 兼容视图编译完成，处理人物主档: {comp['compiled_characters']} 个 (主角: {comp.get('protagonists', 0)}, 配角: {comp.get('supporting', 0)}, 辅助角色: {comp.get('auxiliary', 0)})")
        if "conflicts" in result:
            conf = result["conflicts"]
            if conf["status"] == "pass":
                print("✅ 状态冲突检查通过，未发现冲突")
            else:
                for w in conf["warnings"]:
                    print(f"⚠️  警告: {w}")
                for i in conf["issues"]:
                    print(f"❌ 错误: {i}")

    sys.exit(1 if result.get("conflicts", {}).get("issues") else 0)


if __name__ == "__main__":
    main()
