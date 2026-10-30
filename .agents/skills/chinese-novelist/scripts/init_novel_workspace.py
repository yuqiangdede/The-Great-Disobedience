#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小说工程工作区初始化脚本
支持标准模式 (standard) 与 深度史诗模式 (deep) 的目录与模板脚手架生成。

用法:
  python init_novel_workspace.py <目标目录> --title <小说名称> [--mode deep|standard] [--genre <题材>]

示例:
  python init_novel_workspace.py ./my-story --title 我的小说 --mode deep --genre 奇幻
"""

import argparse
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from project_config import DEFAULT_WRITING, DEFAULT_REVIEW

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def write_file_if_not_exists(path: Path, content: str):
    """安全写入文件，若已存在则不覆盖"""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content.strip() + '\n')


def write_project_config(target_dir: Path, title: str):
    """为新项目生成独立配置，不覆盖已有小说的作者设定。"""
    config = {"schema_version": 1, "title": title, "writing": dict(DEFAULT_WRITING),
              "review": dict(DEFAULT_REVIEW),
              "paths": {"story_rules": "04-文风/项目专属写作规则.md"}}
    write_file_if_not_exists(target_dir / "novel.project.json",
                             json.dumps(config, ensure_ascii=False, indent=2))
    write_file_if_not_exists(target_dir / "04-文风/项目专属写作规则.md",
                             "# 项目专属写作规则\n\n将具体角色、地名、既定剧情、题材风格写在这里；通用 Skill 不写死。")


def init_deep_workspace(target_dir: Path, title: str, genre: str = "通用"):
    """初始化深度模块化工程体系 (Deep / Epic Mode)"""
    target_dir.mkdir(parents=True, exist_ok=True)
    write_project_config(target_dir, title)

    # 1. 创建标准目录（含人物三级子目录与多媒体资源目录）
    dirs = [
        "01-世界观",
        "02-人物",
        "02-人物/主角",
        "02-人物/配角",
        "02-人物/辅助角色",
        "03-剧情",
        "04-文风",
        "05-写作计划/章节任务卡",
        "05-写作计划/插章任务卡",
        "06-正文/第一卷",
        "07-创作记忆",
        "08-审稿",
        "09-归档",
        "10-人物插画",
        "11-剧情音频",
    ]
    for d in dirs:
        (target_dir / d).mkdir(parents=True, exist_ok=True)

    # 2. 生成 AGENTS.md (全局中枢与创作约束)
    agents_md = f"""# 《{title}》全局创作约束与 Agent 协作指南

## 一、唯一权威设定源原则（SSOT）
1. **世界规则**：唯一权威源为 `01-世界观/` 下各专题文档。其他文档不得建立冲突规则。
2. **人物基准与三级小传体系**：唯一权威源为 `02-人物/` 独立档案体系。
   - 主角：`02-人物/主角/[角色名].md`
   - 配角：`02-人物/配角/{{初始所属势力}}/[角色名].md`
   - 辅助角色：`02-人物/辅助角色/{{初始所属势力}}/第{{XXX}}章-[角色名].md` 或 `第一卷插章NNN-[角色名].md`（初始所属势力以首次正式出场为准，未知归初始阵营未确认；插章人物也须建小传）
   - **核心铁律**：**主角和配角都要有人物小传，理论上只要多次出现的人物都要设立独立小传！**
   - **小传定位（冰山原则与合规基准）**：小传没必要所有的情节都在正文中提及，只是为性格和人物建立一个基础而已，后续合规性教研质检时当做基准输入。
   - `00-人物档案.md` 仅为只读编译快照，严禁手动双向改动。
3. **剧情因果**：唯一权威源为 `03-剧情/` 下的分卷因果大纲。
4. **文风基准**：唯一权威源为 `04-文风/`。
5. **动态状态**：唯一权威源为 `07-创作记忆/人物实时状态.md`。

## 二、渐进式读取协议（JIT Context）与写前小传核验
在开始撰写第 N 章时，为避免上下文溢出与设定漂移，AI/Agent **严禁通读全工程所有文档**。
必须按以下顺序渐进加载与核查：
1. 【必读·中枢】读取本文件（`AGENTS.md`）与 `07-创作记忆/当前写作进度.md`
2. 【必读·状态】读取 `07-创作记忆/人物实时状态.md`（掌握登场人物当前伤情、所在位置与装备）
3. 【必读·任务】读取 `05-写作计划/章节任务卡/第{title}章-任务卡.md`（或当前分卷规划中对应小节）
4. 【必检·小传完备性拦截】（硬性前置）：核查本章出场参与人员。主角和配角都要有人物小传，理论上只要多次出现的人物都要设立小传。除纯一次性龙套外，所有角色必须先行在 `02-人物/` 对应分类下创建小传（小传旨在奠定性格基石，正文无需全盘复述生平），登记入总表与实时状态，方可动笔！
5. 【按需·人物】根据任务卡登场名单，仅读取对应角色的主档（重点关注行为逻辑与禁止偏离项）
6. 【按需·设定】若本章涉及特定科技/地理/阵营，仅精准读取对应 `01-世界观/` 单个专题文档
7. 【语态·锚点】读取上一章末尾 500-800 字与 `04-文风/原创文风样例.md`

## 三、写前与写中硬性约束
- **时间轴与生理年龄约束**：角色实际年龄必须与世界主线年份严格对齐（世界年 - 出生年），跨地域位移需符合物理耗时，严禁无铺垫瞬移。
- **行为逻辑约束**：人物不得违背人物主档中的「行为逻辑」与「禁止偏离清单」。
- **知识边界约束**：人物只知道他在当前时间节点理应知道的事。严禁使用全知视角让角色剧透未揭示伏笔。
- **状态继承约束**：角色行动受限于 `人物实时状态.md` 中的负伤与体力状态，严禁无铺垫暴走或机械降神。

## 四、写后事实回写与审稿协议
1. 每章初稿完成后，必须执行四维多维一致性核验（以人物小传为核心输入，运行 `verify_chapter_consistency.py` 严格核验人设行为逻辑合规性、负面禁令、时间轴年龄、情节合理性与字数）。若判定为 BLOCKED 严禁归档回写，必须定向修复直至 PASS。在 `08-审稿/` 输出单章质检报告。
2. 审稿确认后，正文归入 `06-正文/`。
3. 必须及时回写事实到 `07-创作记忆/`：
   - 身体变化、位置移动、获得/损毁装备、最新关系变化回写至 `人物实时状态.md`
   - 新发生的大事回写至 `事件时间线.md`
   - 本章兑现或埋下的线索回写至 `伏笔兑现记录.md`
4. 运行 `sync_novel_memory.py` 刷新 `00-人物档案.md` 与 `99-章节摘要.md` 兼容索引。
"""
    write_file_if_not_exists(target_dir / "AGENTS.md", agents_md)

    # 3. 生成 README.md
    readme_md = f"""# 《{title}》小说工程

- **题材**：{genre}
- **架构模式**：深度模块化架构（Deep Mode）
- **初始化时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 目录索引与导航

- [AGENTS.md](AGENTS.md) — 全局创作约束与 JIT 加载指南（**所有 Agent 必读**）
- [01-世界观/](01-世界观/) — 世界规则唯一权威源（总纲、历史、地理、阵营、战力、装备、社会、异常）
- [02-人物/](02-人物/) — 人物静态主档唯一权威源（分级管理：主角/、配角/、辅助角色/，非一次性角色必建小传）
- [03-剧情/](03-剧情/) — 全书主线、分卷因果大纲、伏笔与命运终局
- [04-文风/](04-文风/) — 文风指纹、文学参考、原创范例与去AI味负面清单
- [05-写作计划/](05-写作计划/) — 章节规划总表、分卷细目与单章任务卡
- [06-正文/](06-正文/) — 正式章节输出库
- [07-创作记忆/](07-创作记忆/) — 动态事实账本（人物实时状态、时间线、伏笔兑现）
- [08-审稿/](08-审稿/) — 单章审稿报告与设定冲突稽核
- [09-归档/](09-归档/) — 历史草稿与过期设定归档
- [10-人物插画/](10-人物插画/) — 角色视觉立绘、肖像与高光情节插画库（用户自由扩充）
- [11-剧情音频/](11-剧情音频/) — 章节配音朗读、广播剧片段与剧情氛围配乐库（用户自由扩充）

## 兼容视图
- `00-人物档案.md` — 从 `02-人物/` 自动提取生成的只读速查表（按主角/配角/辅助角色+章节自动分类）
- `01-大纲.md` — 汇集全书与分卷剧情的总索引
- `02-写作计划.json` — 机器可读调度状态核心
- `03-文风基准.md` — 从 `04-文风/` 提取的上下文锚点
- `99-章节摘要.md` — 逐章连贯性追踪摘要
"""
    write_file_if_not_exists(target_dir / "README.md", readme_md)

    # 4. 生成 01-世界观 模板文件
    world_files = {
        "世界观总纲.md": f"# 《{title}》世界观总纲\n\n## 1. 世界底层核心机制\n\n## 2. 时代背景与生存矛盾\n\n## 3. 核心阵营冲突根源\n",
        "历史与时间线.md": f"# 《{title}》纪年史与历史大事件\n\n| 纪年/时间节点 | 历史事件 | 对当前世界格局的影响 |\n| :--- | :--- | :--- |\n| 早期 | | |\n",
        "地理与地图.md": f"# 《{title}》全球地理与边境疆界\n\n## 1. 核心战略区域\n\n## 2. 缓冲带与荒野地带\n\n## 3. 交通线与资源咽喉\n",
        "阵营与组织.md": f"# 《{title}》主要阵营与势力档案\n\n## 1. 主要阵营列表与利益诉求\n\n## 2. 阵营间的战略博弈关系\n",
        "战力与规则.md": f"# 《{title}》战力阶层与能力运转规则\n\n## 1. 体系分级标准\n\n## 2. 能力觉醒/习得代价\n\n## 3. 绝对法则与无法突破的铁律\n",
        "武器装备与技术.md": f"# 《{title}》军事装备与科技体系\n\n## 1. 单兵标准配置与维保要求\n\n## 2. 重型/战略技术\n",
        "经济社会与平民生活.md": f"# 《{title}》经济循环与底层平民生活\n\n## 1. 资源货币与配给机制\n\n## 2. 平民流亡与生存组织形态\n",
        "异常现象与特殊法则.md": f"# 《{title}》异常现象与环境威胁\n\n## 1. 异常触发机制\n\n## 2. 危害分级与应对预案\n"
    }
    for fname, content in world_files.items():
        write_file_if_not_exists(target_dir / "01-世界观" / fname, content)

    # 5. 生成 02-人物 初始文件（三级分类体系）
    write_file_if_not_exists(target_dir / "02-人物" / "人物总表.md", f"""# 《{title}》人物总表与出场矩阵

## 一、主角列表
| 姓名/代号 | 生理年龄 | 身份/阵营 | 核心能力/特长 | 首次登场分卷/章节 | 终局预设 | 独立主档链接 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 主角 | | | | 第一卷/第001章 | | [主角主档](主角/主角.md) |

## 二、核心配角列表
| 姓名/代号 | 身份/阵营 | 核心能力/特长 | 与主角关系定位 | 首次登场 | 终局预设 | 独立主档链接 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |

## 三、辅助角色列表（按首次登场章节组织）
> ⚠️ **小传铁律**：主角和配角都要有人物小传，理论上只要多次出现的人物都要设立小传！小传没必要所有的情节都在正文中提及，只是为性格和人物建立基础，后续合规性教研质检时当做基准输入。命名格式：`第{{XX}}章-[角色名].md`。

| 首次登场章节 | 姓名/代号 | 所属阵营/身份 | 核心剧情功能 | 是否一次性 | 独立主档链接 |
| :--- | :--- | :--- | :--- | :--- | :--- |
""")

    # 主角独立主档放在 主角/ 目录下
    write_file_if_not_exists(target_dir / "02-人物" / "主角" / "主角.md", f"""# 人物档案：主角

## 1. 基础信息
- **姓名/曾用名**：主角
- **首次登场**：第一卷/第001章
- **角色定位**：主角
- **生理年龄/外观年龄**：
- **所属阵营/身份**：
- **外貌特征与标志性细节**：

## 2. 人生经历与关键转折
- **童年与早期塑造**：
- **重大创伤事件**：
- **加入当前势力的因果**：

## 3. 战斗能力与特长
- **能力特长**：
- **战术习惯**：
- **生理弱点与战斗短板**：

## 4. 特异禀赋（如有）
- **禀赋表现与效果**：
- **触发条件与代价**：
- **失效与克制机制**：

## 5. 人格与行为底层逻辑
- **显性性格**：
- **核心行为逻辑**：
  - *何时愿意牺牲个人利益*：
  - *何时会坚决违抗命令*：
  - *什么极端情境会使其失去冷静*：
  - *始终无法割舍的旧观念/执念*：
- **致命心理缺陷与最大恐惧**：

## 6. 核心信念与动机
- **他究竟相信什么？**：
- **在残酷世界中依然坚持行动的根本动力**：

## 7. 阵营与人际网络
- **与核心队友关系**：
- **与对立阵营关系**：

## 8. 分卷人物弧线
- **第一卷**：
- **第二卷**：

## 9. 终局命运与边界
- **预设宿命**：
- **不可突破的道德底线**：

## 10. 禁止偏离清单（Negative Constraints）
- ❌ 绝对禁止：未经历铺垫突然战力暴涨或获得超纲技能。
- ❌ 绝对禁止：做出违背其行为逻辑的无脑妥协或降智冲动。
""")

    # 新项目也采用两级身份归档，实际阵营子目录由新角色建档时按需创建。
    write_file_if_not_exists(target_dir / "02-人物" / "README.md", """# 人物小传的层级与初始势力

- 主角：`主角/角色名.md`
- 配角：`配角/初始所属势力/角色名.md`
- 辅助角色：`辅助角色/初始所属势力/第XXX章-角色名.md` 或 `第一卷插章NNN-角色名.md`
- 初始势力指首次正式登场时的归属，非出生地／历史服役／未来转投；未知归 `初始阵营未确认/`。
- 编号章与第三方视角插章都需要人物小传：关键人物和多场景角色先建档再详写。
""")

    # 辅助角色目录说明
    write_file_if_not_exists(target_dir / "02-人物" / "辅助角色" / "README.md", """# 辅助角色小传归档说明

- **目录规范**：`辅助角色/{初始所属势力}/第XXX章-角色名.md` 或 `辅助角色/{初始所属势力}/第一卷插章NNN-角色名.md`。未知势力放 `初始阵营未确认/`。
- **建档原则**：编号正文及外部势力插章适用同一门禁。主视角、关键选择执行者、可辨认且多场景复现的人物均需独立小传；允许纯一次性无身份群众豁免。后续转投不变更按首次正式登场势力归档的位置。
- **模板参考**：采用 deep-character-template.md 中的辅助角色精悍小传模板。
""")

    write_file_if_not_exists(target_dir / "02-人物" / "人物关系与冲突.md", f"# 《{title}》核心人物关系与冲突矩阵\n\n## 1. 核心团队内部关系\n\n## 2. 外部利益冲突\n")

    # 6. 生成 03-剧情 模板文件
    write_file_if_not_exists(target_dir / "03-剧情" / "全书主线.md", f"""# 《{title}》全书总纲与核心主线

## 核心前提与终极命题
- **终极冲突**：
- **主题内核**：

## 分卷因果演进总览
- **第一卷**：
- **第二卷**：
- **第三卷**：
""")
    write_file_if_not_exists(target_dir / "03-剧情" / "第一卷-启程.md", f"""# 第一卷剧情大纲

## 核心因果三问
1. **本卷发生了什么核心事件？**：
2. **主角/团队为什么做出这种选择？**：
3. **这些选择为下一卷造成了什么不可逆转的后果？**：

## 阵营博弈背景
- 为什么各势力无法在此维持现状：

## 核心冲突链条
- 起因 -> 激化 -> 危机临界点 -> 爆发与代价 -> 走向下一阶段
""")
    write_file_if_not_exists(target_dir / "03-剧情" / "伏笔与秘密.md", f"""# 《{title}》伏笔与秘密管理表

| 伏笔编号 | 伏笔/秘密描述 | 埋设章节 | 计划兑现分卷/章节 | 真实底层答案 | 兑现状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FB-001 | | 第1章 | | | 待埋设 |
""")
    write_file_if_not_exists(target_dir / "03-剧情" / "人物命运与结局.md", f"# 《{title}》人物命运与终局预设\n\n| 人物 | 终局归宿 | 核心意义与代价 |\n| :--- | :--- | :--- |\n| 主角 | | |\n")

    # 7. 生成 04-文风 模板文件
    write_file_if_not_exists(target_dir / "04-文风" / "文风总规范.md", f"""# 《{title}》文风总规范

## 1. 叙事视角与语态
- **主视角**：第三人称限制视角
- **叙述距离**：按作者选择设置近距离或疏离限制视角，不强制固定风格

## 2. 节奏与句式
- 动作场景：短句为主，紧凑有力
- 思考与环境：按当前小说题材、视角与作者要求定义，不默认军事冷峻文风

## 3. 对话风格
- 说话符合人物身份与背景，严禁现代网梗，多用潜台词
""")
    write_file_if_not_exists(target_dir / "04-文风" / "原创文风样例.md", f"# 《{title}》原创文风基准样例\n\n## 动作与紧迫段落样例\n\n（在此录入符合本书标杆的500-800字样例）\n\n## 场景与心理段落样例\n\n（在此录入符合本书标杆的500-800字样例）\n")
    write_file_if_not_exists(target_dir / "04-文风" / "禁用表达与常见问题.md", """# 禁用表达与去 AI 味清单 (融合 Humanizer-zh 与 说人话)

## 1. 严禁出现的滥调词汇与套话 (Humanizer-zh 模式)
- 璀璨、瑰丽、深邃的眼眸、嘴角勾起一抹、倒吸一口凉气、心潮澎湃、宛如天神下凡

## 2. 严禁出现的假对比与虚浮升华 (Humanizer-zh 核心禁令)
- 严禁“不仅是……更是……”、“看似……实则……”、“表面上……骨子里……”
- 严禁段尾/章尾假大空哲学升华（如“这不仅是一场战斗，更是对人性的拷问”，发现一律删除）
- 严禁三段式排比句连环轰炸与四字成语堆叠

## 3. 坚决消灭公文动词与翻译腔 (说人话 shuorenhua 核心规约)
- 清除“进行/予以/给予/作为”：例如“对敌人进行了追击” -> 改为“提刀狂追”；“给予了他重创” -> 改为“一枪挑翻其肩胛”
- 保持生活毛边感：对话接地气，带留白与口语呼吸，拒绝字正腔圆的播音腔

## 4. 绝对原则 (保事实)
- 润色改写时 100% 保留剧情既定事实、伤病状态、时间数字与伏笔线索，绝不为辞害意。
""")

    # 8. 生成 05-写作计划 模板文件
    write_file_if_not_exists(target_dir / "05-写作计划" / "章节规划总表.md", f"# 《{title}》章节规划总表\n\n| 卷号 | 章号 | 章节标题 | 核心冲突 | 承接关系 | 状态 |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n| 第一卷 | 第001章 | | | 开篇引入 | pending |\n")
    write_file_if_not_exists(target_dir / "05-写作计划" / "章节任务卡" / "第001章-任务卡.md", f"""# 第001章 写作任务卡

- **章节标题**：待定
- **所属分卷**：第一卷
- **出场人物**：
  - 主角：主角
  - 配角：（列出本章出场主要配角）
  - 辅助角色：（列出本章出场辅助角色）
- **写前小传核验**：
  - [ ] 检查本章全部出场人员，确认均已建立独立小传
  - [ ] 若有新增非一次性角色，已先行补充创建小传（按 主角/配角或辅助角色/初始势力/首次登场章或插章 规范归档）
- **主要场景**：
- **核心事件**：
- **前置因果（承接上章）**：无（开篇）
- **悬念钩子**：
- **登场人物实时状态要求**：
- **设定调用清单**：
""")

    # 9. 生成 07-创作记忆 模板文件
    write_file_if_not_exists(target_dir / "07-创作记忆" / "当前写作进度.md", f"""# 当前写作进度

- **当前分卷**：第一卷
- **当前撰写章节**：第001章
- **已完结章节数**：0
- **当前总字数**：0
- **最新全局时间节点**：故事起点
""")
    write_file_if_not_exists(target_dir / "07-创作记忆" / "人物实时状态.md", f"""# 核心人物实时状态跟踪表

| 人物 | 当前位置 | 身体伤病与精力 | 装备与物资配给 | 已知情报边界（他知道什么） | 未知警戒线（严禁剧透） | 心理与人际动态 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **主角** | 初始起点 | 状态正常 | 标配装备 | 仅限初始认知 | 外部大阴谋与伏笔未揭示 | 初始心态 |
""")
    # 时间轴总账（结构化基准底表）
    timeline_baseline = {
        "worldBaseline": {
            "epochName": "待作者确立",
            "currentYear": None,
            "currentMonth": None,
            "currentDay": None,
            "season": "",
            "worldMajorEvent": "待确认"
        },
        "charactersTimeline": {},
        "travelConstraintMatrix": {}
    }
    write_file_if_not_exists(target_dir / "07-创作记忆" / "时间轴总账.json", json.dumps(timeline_baseline, ensure_ascii=False, indent=2))

    write_file_if_not_exists(target_dir / "07-创作记忆" / "事件时间线.md", f"""# 正文事件真实时间线

| 发生时间（世界时间/主角实岁） | 章节 | 事件概要 | 产生不可逆后果 | 关联人物 |
| :--- | :--- | :--- | :--- | :--- |\n""")
    write_file_if_not_exists(target_dir / "07-创作记忆" / "伏笔兑现记录.md", f"""# 伏笔埋设与兑现日志

| 伏笔编号 | 埋设章号 | 伏笔细节 | 兑现章号 | 兑现方式说明 |
| :--- | :--- | :--- | :--- | :--- |\n""")
    write_file_if_not_exists(target_dir / "07-创作记忆" / "设定变更记录.md", f"""# 设定确权与变更记录

| 变更日期 | 涉及文档 | 变更内容概要 | 批准/原因 |
| :--- | :--- | :--- | :--- |\n""")
    write_file_if_not_exists(target_dir / "07-创作记忆" / "章节摘要.md", "# 章节摘要汇总\n\n每章完成后在此追加 300-500 字摘要，供跨卷连贯性参考。\n")

    # 10. 生成兼容层文件
    plan_json = {
        "version": 2,
        "novelName": title,
        "architectureMode": "deep",
        "projectPath": str(target_dir.as_posix()),
        "totalChapters": 20,
        "minWordsPerChapter": DEFAULT_WRITING["chapter_min_han"],
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "status": "planning",
        "writingMode": "serial",
        "chapters": [
            {
                "chapterNumber": 1,
                "title": "第001章",
                "volume": "第一卷",
                "filePath": "06-正文/第一卷/第001章.md",
                "status": "pending",
                "wordCount": None,
                "wordCountPass": None,
                "retryCount": 0
            }
        ]
    }
    write_file_if_not_exists(target_dir / "02-写作计划.json", json.dumps(plan_json, ensure_ascii=False, indent=2))

    # 编译生成 00-人物档案.md, 01-大纲.md, 03-文风基准.md, 99-章节摘要.md
    write_file_if_not_exists(target_dir / "00-人物档案.md", f"# 《{title}》人物速查（只读索引）\n\n> ⚠️ 本文件由系统自动从 `02-人物/` 提取生成，请勿在此直接修改。\n\n- 主角：见 [02-人物/主角/主角.md](02-人物/主角/主角.md)\n")
    write_file_if_not_exists(target_dir / "01-大纲.md", f"# 《{title}》总纲与分卷索引\n\n> 详细情节请参阅 `03-剧情/` 与 `05-写作计划/`。\n\n## 主线索引\n- 全书主线：[03-剧情/全书主线.md](03-剧情/全书主线.md)\n- 第一卷：[03-剧情/第一卷-启程.md](03-剧情/第一卷-启程.md)\n")
    write_file_if_not_exists(target_dir / "03-文风基准.md", f"# 文风基准\n\n> 权威源见 `04-文风/`。\n\n## 核心锚点\n- 参见 [04-文风/原创文风样例.md](04-文风/原创文风样例.md)\n")
    write_file_if_not_exists(target_dir / "99-章节摘要.md", "# 章节摘要\n\n> 镜像自 `07-创作记忆/章节摘要.md`。\n")

    # 11. 生成 10-人物插画 与 11-剧情音频 目录说明
    write_file_if_not_exists(target_dir / "10-人物插画" / "README.md", f"""# 《{title}》人物插画库说明

本目录由作者根据个人意愿**自由存放与管理**角色视觉素材（支持 AI 生成立绘、Midjourney/DALL-E/Flux 构图、私人约稿插画等）。

## 推荐分类与命名规范
1. **角色立绘/肖像**：
   - 命名建议：`[角色名]-立绘.png` 或 `[角色名]-肖像.jpg`（如：`主角-立绘.png`）
   - 引用方式：可在 `02-人物/` 对应人物小传中插入引用：
     ```markdown
     ## 1. 基础信息
     - **人物视觉立绘**：![立绘](../../10-人物插画/[角色名]-立绘.png)
     ```
2. **高光剧情场景插画**：
   - 命名建议：`第{{XX}}章-[高光情节名].png`（如：`第001章-雪夜追击.png`）
   - 可在对应正文章节中直接嵌入展示。
3. **支持格式**：`.png`, `.jpg`, `.jpeg`, `.webp`, `.svg`, `.gif` 等常见图片格式。

> 💡 **提示**：本目录为用户可选扩展，不强制要求提供；未存放插画不影响正文全自动创作流程。
""")

    write_file_if_not_exists(target_dir / "11-剧情音频" / "README.md", f"""# 《{title}》剧情音频库说明

本目录由作者根据个人意愿**自由存放与管理**剧情配乐、配音及原声广播剧素材。

## 推荐分类与命名规范
1. **章节配音/有声朗读**：
   - 命名建议：`第{{XX}}章-[章节名]-朗读.mp3` 或 `第{{XX}}章-[角色名]-高光台词.mp3`
   - 适合存放 TTS（ElevenLabs、CosyVoice、GPT-SoVITS 等）生成的演播音频。
2. **剧情氛围配乐/主题曲 (BGM)**：
   - 命名建议：`BGM-[场景名/阵营名].mp3`（如：`BGM-荒野伏击.mp3`）
3. **支持格式**：`.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.aac` 等常见音频格式。
4. **正文引用方式（可选）**：
   可在章节正文末尾或任务卡中添加音频链接：
   ```markdown
   > 🎵 **本章专属配乐/音频**：[点击播放/查看音频](../../11-剧情音频/第001章-高光音频.mp3)
   ```

> 💡 **提示**：本目录为用户可选扩展，不强制要求提供；未存放音频不影响正文全自动创作流程。
""")

    print(f"✅ 成功初始化深度小说工程: {target_dir} (书名: {title}, 模式: deep)")


def init_standard_workspace(target_dir: Path, title: str, genre: str = "通用"):
    """初始化标准轻量工程体系 (Standard Mode)"""
    target_dir.mkdir(parents=True, exist_ok=True)
    write_project_config(target_dir, title)

    # 创建人物插画与剧情音频目录（用户按需自由扩充）
    (target_dir / "人物插画").mkdir(parents=True, exist_ok=True)
    (target_dir / "剧情音频").mkdir(parents=True, exist_ok=True)

    write_file_if_not_exists(target_dir / "人物插画" / "README.md", f"""# 《{title}》人物插画库说明

本目录供作者按需**自由存放与管理**角色视觉素材（立绘、肖像与剧情插画）。
- 命名建议：`[角色名]-立绘.png`、`第{{XX}}章-[场景名].png`
- 支持格式：`.png`, `.jpg`, `.jpeg`, `.webp` 等常见格式
- 可在 `00-人物档案.md` 或章节正文中按需引用。未提供不影响写作。
""")

    write_file_if_not_exists(target_dir / "剧情音频" / "README.md", f"""# 《{title}》剧情音频库说明

本目录供作者按需**自由存放与管理**章节有声朗读、广播剧片段与剧情配乐（BGM）。
- 命名建议：`第{{XX}}章-配音.mp3`、`BGM-[场景名].mp3`
- 支持格式：`.mp3`, `.wav`, `.m4a`, `.flac` 等常见格式
- 可在章节正文中按需添加音频链接。未提供不影响写作。
""")

    # 保持原 Skill 经典 5 大文件结构，人物按主角/配角/辅助角色+章节分类
    write_file_if_not_exists(target_dir / "00-人物档案.md", f"""# 《{title}》人物档案

> ⚠️ **核心法则**：**主角和配角都要有人物小传，理论上只要多次出现的人物都要设立小传！**
> 💡 **小传定位**：小传没必要所有的情节都在正文中提及，只是为性格和人物建立基础，后续合规性教研质检时当做基准输入。
> 按照「主角、配角、辅助角色+章节」分类组织，方便快速检索。

## 一、主角

### [主角姓名]
- **首次登场**：第01章
- **年龄/职业**：
- **性格核心**：
- **禁止偏离清单**：

## 二、配角

### [配角姓名]
- **首次登场**：第01章
- **阵营/身份**：
- **与主角关系**：
- **禁止偏离清单**：

## 三、辅助角色（按章节归类）

### 第01章出场辅助角色
#### [角色姓名]
- **首次登场**：第01章
- **身份与功能**：
- **性格与底线**：
""")
    write_file_if_not_exists(target_dir / "01-大纲.md", f"# 《{title}》大纲\n\n## 基本信息\n- 题材：{genre}\n- 预计章节数：10-20 章\n\n## 章节规划\n| 章节 | 标题 | 核心事件 | 承接上章 | 悬念钩子 | 出场人物 | 场景列表 |\n")
    write_file_if_not_exists(target_dir / "03-文风基准.md", "# 文风基准\n\n## 文风指纹\n- 对话占比：35%-45%\n\n## 基准段落\n")
    write_file_if_not_exists(target_dir / "99-章节摘要.md", "# 章节摘要\n\n每章完成后追加 300-500 字摘要，供连贯性参考。\n")

    plan_json = {
        "version": 1,
        "novelName": title,
        "architectureMode": "standard",
        "projectPath": str(target_dir.as_posix()),
        "totalChapters": 10,
        "minWordsPerChapter": 3000,
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "status": "planning",
        "writingMode": "serial",
        "chapters": [
            {
                "chapterNumber": 1,
                "title": "第01章",
                "filePath": "第01章.md",
                "status": "pending",
                "wordCount": None,
                "wordCountPass": None,
                "retryCount": 0
            }
        ]
    }
    write_file_if_not_exists(target_dir / "02-写作计划.json", json.dumps(plan_json, ensure_ascii=False, indent=2))
    print(f"✅ 成功初始化标准小说工程: {target_dir} (书名: {title}, 模式: standard)")


def main():
    parser = argparse.ArgumentParser(description="中文小说工程工作区初始化工具")
    parser.add_argument("target_dir", type=str, help="目标工程根目录")
    parser.add_argument("--title", type=str, required=True, help="小说标题")
    parser.add_argument("--mode", type=str, choices=["deep", "standard"], default="deep", help="架构模式: deep (深度史诗) 或 standard (标准轻量)")
    parser.add_argument("--genre", type=str, default="通用", help="小说题材")

    args = parser.parse_args()
    target_path = Path(args.target_dir).resolve()

    if args.mode == "deep":
        init_deep_workspace(target_path, args.title, args.genre)
    else:
        init_standard_workspace(target_path, args.title, args.genre)


if __name__ == "__main__":
    main()
