#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单章「去 AI 味四关」机械合检工具

四关来源（外部 skill 的检测口径，已按长篇小说的文体做本地化适配）：
  G1 = op7418/Humanizer-zh        （31 条模式：假对比、拔高、翻译腔、公文腔、排版套式）
  G2 = Raymondhou0917/speak-human-tw（38 种 AI 痕迹：立场真空、公式化开场、罐头反应镜头、假推论）
  G3 = MrGeDiao/shuorenhua        （保事实、去翻译腔、去公文动词、责任主体与情态守恒）
  G4 = larashero3-dotcom/lieflat-less-ai-tone（白名单式硬规则：翻案腔、顿号罗列、相邻句同构、
       破折号/冒号、序数小标题、拟人喻体、概括盖数据、起手式、段首零主语）
  G0 = 本书自有铁律（AGENTS.md 去 AI 味十大铁律 ∩ scan_chapter.py 的全知剧透与顿悟句）

设计原则（重要）：
  1. 本脚本只报「可定位的触发标记」，不做 AI 作者鉴定，也不替代人工四关复核。
  2. 长篇小说的合法文体手段必须放行：对话里的口语起手式、叙事中的停顿镜头、文学性排比与
     比喻，只有在明确命中「无功能填充」标记时才计入，且多数降级为 WARN（待人工裁量）。
  3. 引号内台词默认豁免「起手式 / 破折号 / 顿号罗列 / 罐头反应镜头」四类；但「假对比、
     拔高、公文动词、翻译腔」在台词里照样查——AI 台词最常见的毛病正是这些。
  4. 命中 BLOCK 一律判定 BLOCKED（退出码 1），必须先改后复检；WARN 需人工逐条确认或放行。

用法:
  python scan_ai_tone.py <章节路径> [<章节路径2> ...] [--project-dir 项目根] [--json]
                         [--auto-report] [--report 指定报告路径] [--min-words 项目配置覆盖]
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path
from project_config import chapter_limits

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# --------------------------------------------------------------------------------------
# 规则表
#   id            规则编号（关卡前缀 + 序号）
#   gate          归属关卡
#   name          规则名（沿用原 skill 的说法，便于回溯）
#   pattern       正则；None 表示由统计逻辑处理
#   severity      BLOCK = 硬伤必须改；WARN = 待人工裁量
#   dialogue      是否豁免引号内台词
#   note / fix    判定说明与建议改法（写进报告，供 Agent 与作者直接照改）
# --------------------------------------------------------------------------------------
def R(rid, gate, name, pattern, severity, note, fix, scope="all"):
    return {
        "id": rid,
        "gate": gate,
        "name": name,
        "pattern": re.compile(pattern) if pattern else None,
        "severity": severity,
        "note": note,
        "fix": fix,
        # scope: all=整行（保护行内代码）；narration=只查叙述（豁免引号内台词）；
        #        dialogue=只查引号内台词
        "scope": scope,
    }


RULES = [
    # ---------------- G0 本书铁律（跨关共检：全知剧透 / 顿悟总结 / 机械断章） ----------------
    R("G0-01", "G0", "全知剧透模板句", r"他不知道的是|她不知道的是|殊不知|命运的齿轮|多年以后",
      "BLOCK", "第三人称有限视角禁用的全知旁白，提前宣布人物未知的结局。",
      "整句删除。该信息要么本章不写，要么改成角色此刻能观察到的具体物证或对话。"),
    R("G0-02", "G0", "顿悟总结句", r"这一刻[^。！？]{0,9}(?:终于|才)?(?:明白|懂|意识到|醒悟)|终于懂得了|他明白了[^。！？]{0,10}的道理",
      "BLOCK", "替角色总结成长与觉悟，属于说教式收束。",
      "删掉总结句，只保留触发顿悟的那个具体动作或画面，让读者自己得出结论。"),
    R("G0-03", "G0", "机械断章钩子", r"危险正在(?:悄然)?逼近|然而[^。！？]{0,20}意想不到|一场更大的风暴|故事才刚刚开始",
      "BLOCK", "章尾机械反转/预告式断章，属于模板钩子。",
      "换成具体的、可感知的现场变化（声音、光影、体温、通讯杂音）收尾。"),
    R("G0-04", "G0", "高频强化词堆积（聚合统计）", None,
      "WARN", "并非禁用词，但同一章密集复现会形成机械强化节奏（阈值：单词超过 3 次）。",
      "把超出部分换成具体动作或生理反应（手抖、耳鸣、指节发白），不要整词删除。"),

    # ---------------- G1 Humanizer-zh ----------------
    R("G1-01", "G1", "假对比（不是 X 而是 Y）", r"(?:不仅|不只)(?:仅)?是[^。！？]{1,24}(?:更|而且)(?:是)?",
      "BLOCK", "抬高语气的假对比，两部分常只有一处提供信息。",
      "直接写后半句的判断。「A 不只是战场，更是坟场」→「这是坟场」，除非否定部分纠正了真实误解。",
      scope="narration"),
    R("G1-04", "G1", "起跑式铺垫", r"(?:接下来|下面|且看|让我们)[^，。！？]{0,8}(?:看看|说说|聊聊|走进|了解|见识)",
      "BLOCK", "只预告下文、不承担信息的过渡句。",
      "整句删除，让后面的实质内容直接开始。"),
    R("G1-05", "G1", "与假想敌辩论", r"(?:别误会|不是要|我并不是在|先别急着)",
      "BLOCK", "自我辩护式铺垫，正文里没有真实对手。",
      "删掉辩护句，直接陈述事实或命令。"),
    R("G1-09", "G1", "限定词堆叠", r"(?:也许|或许|可能|大概|恐怕)(?:也)?(?:可能|或许|也许|大概)",
      "BLOCK", "同一层不确定性重复限定，语义空转。",
      "保留一个限定词。原文是「也许可能会」→「可能」。"),
    R("G1-12", "G1", "AI 高频词", r"赋能|至关重要|深入探讨|无缝衔接|形成闭环|抓手|颗粒度|底层逻辑|组合拳|护城河|势能|范式|生态位|降维打击",
      "BLOCK", "会议/营销语料词，进入小说叙事即成硬伤。",
      "换成人话：赋能→给…装上；深入探讨→讨论；闭环→把…接上；底层逻辑→他真正图的是什么。"),
    R("G1-13", "G1", "意义拔高", r"标志着|见证了|开启了[^，。！？]{0,8}新(?:时代|篇章|纪元)|奠定了[^，。]{0,8}基础|具有[^，。]{0,8}重要意义|浓墨重彩|里程碑",
      "BLOCK", "给普通事件贴历史标签，拔高叙事。",
      "删除拔高句，保留事件本身与其后果。"),
    R("G1-14", "G1", "模糊关联", r"有着[^，。！？]{0,10}(?:密切|千丝万缕)的?(?:联系|关联)",
      "BLOCK", "含糊交代关系，等于没交代。",
      "写出具体关系（谁给谁递过话、谁欠谁一条命）。"),
    R("G1-15", "G1", "句尾补充式拔高", r"彰显了|体现了|折射出|诠释了|昭示着|诉说着",
      "BLOCK", "句尾追加的赞美尾巴，无新信息。",
      "砍掉尾巴；若确有原因/目的，用具体因果句写出。"),
    R("G1-16", "G1", "宣传语", r"堪称|不愧为|叹为观止|天花板级|行业天花板|殿堂级|教科书级",
      "BLOCK", "无参数支撑的溢美之词。",
      "改成可核查的事实或直接给角色评价（「机械师骂了一句，说这枪比他年纪还大」）。"),
    R("G1-17", "G1", "无源借权威", r"(?:专家|研究者|学者|业内人士|权威人士|数据显示|研究表明|调查显示)(?:认为|表明|显示|指出|发现)",
      "BLOCK", "小说正文中的无出处权威背书，且多半是信息投喂。",
      "删除归因句，把信息改成角色亲眼所见、亲耳所闻或档案原文。"),
    R("G1-19", "G1", "粗体当装饰", r"\*\*[^*\n]{1,40}\*\*",
      "WARN", "正文中的 Markdown 粗体，长篇正文应为纯散文。",
      "去掉 ** 标记，用句子本身承担强调。"),
    R("G1-20", "G1", "装饰性符号/emoji", r"[\U0001F300-\U0001FAFF\u2600-\u27BF]",
      "BLOCK", "正文出现表情符号或装饰图形。",
      "删除符号，保留文字。"),
    R("G1-21", "G1", "半角标点串味", r"\.\.\.|(?<![A-Za-z0-9_])[\"'](?=[\u4e00-\u9fff])",
      "WARN", "中文正文混入半角省略号/引号。",
      "改为「……」与「“”」或「」」，与全书标点体例统一。"),
    R("G1-22", "G1", "客服腔/编辑腔残留", r"希望(?:这|以上|本文|本章)[^。！？]{0,10}(?:帮助|有用)|好问题|以下是(?:修改|改写|润色|正文)",
      "BLOCK", "把写作过程或服务话术写进了正文。",
      "整句删除。"),
    R("G1-23", "G1", "知识边界免责", r"由于篇幅|限于篇幅|恕不赘述|本文不再展开|不再赘述",
      "BLOCK", "说明文式的免责与省略提示。",
      "删除；该跳过的直接跳过。"),
    R("G1-25", "G1", "谈论上一稿", r"上一版|前一稿|本次修订|这段是刚|刚补充的|原稿中",
      "BLOCK", "把修改过程留在了正文里。",
      "删除，只保留定稿内容。"),
    R("G1-26", "G1", "层叠的「的」", r"的[^，。！？]{1,12}的[^，。！？]{1,12}的",
      "WARN", "长定语套叠，读起来要回头确认句意。",
      "拆成两个分句，把其中一层改成动词结构。"),
    R("G1-27", "G1", "进行/予以 + 动词", r"(?:进行|予以|加以|给予)(?:了)?(?:一次|一番|一个)?(?:全面|深入|细致|重点|紧急)?(?:的)?(?:检查|测试|调整|优化|处理|攻击|打击|分析|讨论|评估|部署|确认|审阅|视察|包扎|清点)",
      "BLOCK", "公文动词化，动作被抽象成流程。",
      "还原具体动作：「对伤口进行了处理」→「拿酒精棉按上去，受伤者嘶了一声」。"),
    R("G1-28", "G1", "被字句堆叠", r"被[^。！？]{0,12}被",
      "WARN", "一句里连续被动，施事者全部消失。",
      "至少一处改主动，把施事者写出来（谁动的手）。"),
    R("G1-29", "G1", "四字词排比轰炸", r"(?:[\u4e00-\u9fff]{4}、){2,}[\u4e00-\u9fff]{4}",
      "WARN", "连续三个以上四字词并列，形成僵硬律动。",
      "留一个最准的，其余展开成具体动作或细节。"),
    R("G1-30", "G1", "「随着…发展」式开场", r"(?:^|[。！？\n])\s*(?:随着|在)[^，。]{0,20}(?:的发展|进步|推进|普及|到来)[，,]",
      "BLOCK", "时代大帽子开场，第一句没有本章独有的信息。",
      "删掉背景帽，第一节直接写现场。"),
    R("G1-31", "G1", "套话收尾", r"总而言之|综上所述|总的来说|让我们(?:一起)?(?:拭目以待|期待)|未来(?:充满|可期)|值得期待|新征程",
      "BLOCK", "章末罐头总结或祝愿。",
      "删除；允许章节停在最后一个具体动作或一句没说完的话上。"),

    # ---------------- G2 speak-human-tw（简体/长篇适配，去台湾在地化层） ----------------
    R("G2-02", "G2", "公式化开场", r"(?:在当今|在这个)[^，。]{0,10}的?时代|随着(?:科技|AI|人工智能|社会|时代)的?(?:快速|不断|飞速)?(?:发展|进步|演进)",
      "BLOCK", "公式化时代开场。",
      "删除该句，从具体时间、地点、温度、气味写起。"),
    R("G2-03", "G2", "立场真空", r"各有(?:各的)?(?:优缺点|千秋|长短)|因人而异|见仁见智|取决于多方面|没有绝对的对错",
      "BLOCK", "回避判断的和稀泥表述。",
      "写出角色此刻的实际选择与理由；不写「各有各的道理」。"),
    R("G2-04", "G2", "首先其次最后三段式", r"首先[，,][^。！？]{0,80}其次[，,][^。！？]{0,80}(?:最后|第三)",
      "BLOCK", "对称凑数的三段式，结构服从对称而非逻辑。",
      "删掉过渡词，按真实的因果或时间顺序重排。"),
    R("G2-05", "G2", "假推论句", r"(?:这(?:意味着|表明了?|说明了?)|由此可见|不难看出)",
      "BLOCK", "把上一句换个说法再讲一遍的复述句。",
      "并入前一句，或直接删掉提示语只留结论。"),
    R("G2-06", "G2", "罐头反应镜头", r"(?:愣|怔)(?:了)?(?:一下|半晌|片刻)|沉默(?:了)?(?:几秒|片刻|半晌)|停了一下|看着[^。！？]{0,8}(?:屏幕|窗外|远方)[^。！？]{0,8}(?:没|不)说话",
      "WARN", "只负责表演情绪的通用镜头；若停顿本身承担叙事功能（打断对话、交代时间、关系变化）则合法。",
      "无功能就删；有功能就保留并补一句具体信息（谁先开口、外面什么声响）。", scope="narration"),
    R("G2-07", "G2", "空洞积极收束", r"未来充满(?:无限)?可能|充满希望|一切都会(?:好起来|过去)|明天会更好",
      "BLOCK", "通用积极结论，与本章具体处境无关。",
      "删除，或换成本章独有的具体下一步动作。"),
    R("G2-08", "G2", "待作者补充占位符", r"[（(]\s*需作者补充|【待补】|TODO|XX待定",
      "BLOCK", "交付物里残留占位符。",
      "补成正文；确实无法补则按任务卡处理，不得带占位符交稿。"),

    # ---------------- G3 shuorenhua ----------------
    R("G3-01", "G3", "公文动词化（进行/予以）", r"(?:对[^，。]{1,12}|向[^，。]{1,12})(?:进行|予以|加以)(?:了)?",
      "BLOCK", "说人话原则：动作被名词化成流程。",
      "还原动词与施受关系：「对阵地进行了火力压制」→「机枪压住坡口」。"),
    R("G3-02", "G3", "实现了…的提升", r"实现了[^，。]{0,10}的(?:提升|增长|优化|突破|改善|跨越)|取得了[^，。]{0,10}的(?:进展|成果|成效)",
      "BLOCK", "业绩汇报句式。",
      "给出可核查的具体变化（时间从多少到多少、距离从多少到多少）。"),
    R("G3-03", "G3", "完成了对…的", r"完成了对[^，。]{1,14}的|作出了[^，。]{0,8}的(?:决定|回应|处置|打击)",
      "BLOCK", "名词化套式。",
      "改回「谁 + 动词 + 什么」。"),
    R("G3-04", "G3", "「当…时」前置从句", r"当[^，。]{12,40}时[，,]",
      "WARN", "英语 When 从句直译式前置；小说里长从句放在句首会拖住主句，短句属正常汉语。",
      "删掉「当」和「时」，让从句直接作前一分句：「当风雪停时，哨所安静下来」→「风雪停了，哨所安静下来」。",
      scope="narration"),
    R("G3-05", "G3", "前置话题壳", r"(?:对于|对)[^，。]{1,10}(?:来说|而言)|就[^，。]{1,10}而言|在[^，。]{1,10}方面",
      "WARN", "For / As for / In terms of 直译壳子；小说叙述里可接受，密集出现才成问题。",
      "把对象直接放到主语位：「对于新兵来说，最难的是守夜」→「新兵最难的是守夜」。",
      scope="narration"),
    R("G3-06", "G3", "论文式句首路标", r"(?:^|[。！？\n])\s*(?:综上所述|换言之|总而言之|基于此|由此可见)[，,]",
      "BLOCK", "论文/公文式段落路标，小说里没有位置。",
      "删除该连接词，让事实自己承接。"),
    R("G3-09", "G3", "句首连接词（密度提示）", r"(?:^|[。！？\n])\s*(?:然而|因此|此外|与此同时)[，,]",
      "WARN", "单次合法；相邻段落连续这样开头才是英文式路标病。",
      "改成「不过」「也」「其实」并挪到主语后；「然而，他并没有动」→「他却没有动」。",
      scope="narration"),
    R("G3-07", "G3", "渲染夸饰词", r"完美地?融合|极致|前所未有|革命性|令人惊叹|无可挑剔|登峰造极|完美无缺",
      "WARN", "仅在「写平实」授权下才改；小说中若属人物视角的评价可保留。",
      "降调为平常说法（极致→很高），不加码、不换褒贬方向。"),
    R("G3-08", "G3", "情态被抹平（可能→一定）", r"(?:肯定|必然|一定)(?:会|是)[^，。！？]{0,10}(?:吧|的)?(?=[。，！？])",
      "WARN", "把原文的不确定写成确定，属于改动事实强度。核实是否与人物情报边界相符。",
      "情报不足以支撑确定性时，改回「大概」「兴许」「说不准」。"),

    # ---------------- TR 翻译腔候选：只报 WARN，需人工按 TR01—TR15 语境复核 ----------------
    # 注意：这些表达均可能是正确的文学句法/技术术语；不因单次出现判 AI 或自动阻断。
    # 同根因与既有 G1/G3 命中须人工合并，不能重复扣分。
    R("TR-02", "G3", "物事作主语 + 使人感到（候选）",
      r"(?:的(?:到来|离开|失踪|消失|死亡|发生|出现|决定|变化|失败)|这(?:件事|场|次))[^，。！？]{0,9}(?:让|使)[^，。！？]{0,12}(?:感到|觉得|产生)",
      "WARN", "TR02：物事/抽象事件充当主语，可能绕开真实感受者；有明确因果作用时合法。",
      "先确认事件是否是本句焦点；需要简化时写人如何反应，不捏造新情绪。", scope="narration"),
    R("TR-03", "G3", "有着/具有 + 抽象名词空壳（候选）",
      r"(?:有着|具有)[^，。！？]{1,16}的(?:重要性|知名度|影响力|意义|价值|作用|地位)",
      "WARN", "TR03：描述可能被绕成抽象名词；技术属性或正式措辞可保留。",
      "把抽象名词还原为清楚的状态或动作；保留比较和证据。", scope="narration"),
    R("TR-07", "G3", "被发现/被认为等施事隐去（候选）",
      r"被[^，。！？]{0,14}(?:发现|注意到|认为|认定|告知|给予|评价为)",
      "WARN", "TR07：被动不等于错误，连续出现或遮蔽责任主体才影响阅读。",
      "核查行动者是否应当明确；隐藏身份、受害者焦点或报告语境可保留。", scope="narration"),
    R("TR-08", "G3", "多重机械连词（候选）",
      r"(?:并且|与此同时|以及)[^。！？]{1,32}(?:并且|与此同时|以及)",
      "WARN", "TR08：连词连续黏接动作，可能形成英译长串句。",
      "核对并列和先后关系，必要时以逗号或动作承接，不改变同时/递进含义。", scope="narration"),
    R("TR-09", "G3", "时态词复叠（候选）",
      r"(?:已经[^，。！？]{0,8}曾经|曾经[^，。！？]{0,8}已经|已经[^，。！？]{0,8}已)",
      "WARN", "TR09：可能重复交代已明确的时间；状态变化的“已经”可能必需。",
      "不改变事件是否已完成的事实，只删多余时态词。", scope="narration"),
    R("TR-11", "G3", "由于…导致因果套壳（候选）",
      r"由于[^，。！？]{2,36}[，,][^。！？]{0,10}(?:导致|使得|造成)",
      "WARN", "TR11：介宾壳可能使句子缺少清楚主语；不排除合理的学术/报告用语。",
      "将原因和结果写成清楚两分句，保留归责与不确定性。", scope="narration"),
    R("TR-12", "G3", "量词列举机械化（候选）",
      r"(?:一(?:个|台|张|把|只|份|件)[^，、。！？]{1,12}[、，]){2,}一(?:个|台|张|把|只|份|件)",
      "WARN", "TR12：按英文 a/an 逐项列举可能多余；数量本身有用时不得删。",
      "只在列举种类而非数量的场合去量词。", scope="narration"),
    R("TR-13", "G3", "生硬直译词（仅语境候选）",
      r"门控|横切|一等公民|面包屑|心智模型|数据契约|接口契约|原语",
      "WARN", "TR13：这些词在专业领域可能完全正确，严禁直接替换既定技术术语。",
      "检查是否角色真在讨论算法/接口/导航等精确概念；非专业比喻才改自然表达。"),
    R("TR-14", "G3", "生造词/不必要拟人（仅语境候选）",
      r"(?:这个|这种|问题|方法)切法|系统长出(?:了)?|工具长出(?:了)?|接口长出(?:了)?",
      "WARN", "TR14：突兀造词和对物过度拟人；活体技术/角色独特用词可能成立。",
      "若无设定意义，改写成实际新增的动作或事实。", scope="narration"),

    # ---------------- G4 lieflat-less-ai-tone（白名单硬规则） ----------------
    R("G2-09", "G2", "台词内假对比/翻案腔", r"(?:不是|并非|不在于)[^。！？]{1,24}(?:而是|而在于)|与其说[^。]{1,20}不如说|看似[^。]{1,20}(?:实则|其实)",
      "WARN", "台词里的翻案腔若属人物辩白、且否定部分纠正了真实误解，可以保留；纯为抬高语气的要改。",
      "直接从正面说；人物真在辩白时保留，但一场戏里不要连续用两次同一句式。",
      scope="dialogue"),

    R("G4-01", "G4", "抽象翻案腔（硬伤）", r"(?:不是|并非|不在于)[^。！？]{1,24}(?:而是|而在于)[^。！？]{0,6}(?:一种|一次|一场|一门|一份)?(?:认知|心态|态度|格局|思维|本质|选择|修行|境界|智慧|眼光|考验|觉醒|成长|责任|信念|意志|尊严|人性|命运|能力问题|技术问题|作风)",
      "BLOCK", "把具体问题翻成抽象命题的抬高式翻案，是模板感最强的形态。",
      "直接从正面下判断：先给判断，再给依据。「不是装备问题，而是补给问题」→「问题在补给」。",
      scope="narration"),
    R("G4-01b", "G4", "事实辨识式「不是A而是B」", r"(?:不是|并非|不在于)[^。！？]{1,24}(?:而是|而在于)|与其说[^。]{1,24}不如说|表面(?:上)?[^。]{1,24}(?:实际|实则)|看似[^。]{1,24}(?:实则|其实)|你以为[^。]{1,30}其实|答案恰恰相反|回头才发现",
      "WARN", "侦察辨识、勘验推断中的「不是A而是B」是小说合法手段；只有修辞性拔高才需要改。",
      "保留事实辨识；把纯修辞的那处改成直述。一章内同一句式不要超过两次。",
      scope="narration"),
    R("G4-02", "G4", "顿号罗列过密", r"[^，。！？、\n]{1,10}、[^，。！？、\n]{1,10}、[^，。！？、\n]{1,10}",
      "WARN", "三项以上同构并列塞进一句；材料本身必须完整列出时（装备清单、条令）合法。",
      "概括成一项，或改变其中一项的句法，不让它们排成同一结构。", scope="narration"),
    R("G4-05", "G4", "冒号提示语", r"(?:一句话总结|核心是|关键在于|原因(?:如下|有两个|有三个)|结论|本质上|换句话说|简而言之)[：:]",
      "BLOCK", "提示语替内容说话。",
      "删掉提示语直接写内容，或把冒号改成句号。"),
    R("G4-06", "G4", "序数词小标题", r"(?:^|\n)\s*(?:#{1,6}\s*|\*\*)[一二三四五六七八九十]+、",
      "BLOCK", "「一、二、三」通篇编号的小标题是最强的模板感。",
      "删掉编号保留标题文字；正文里的「首先…其次」不在此列。"),
    R("G4-07", "G4", "拟人化喻体", r"像(?:一位|一个|一名)?(?:智慧的|贴心的|不知疲倦的|永不疲倦的|全能的)?(?:导师|秘书|助手|顾问|管家|审查员|实习生|教练|保姆)",
      "WARN", "把系统/流程比作理想化职业人格，替作者抒情。",
      "换成它实际做了什么；文学性比喻（像老师傅、像守夜人）不在此列。", scope="narration"),
    R("G4-09", "G4", "禁用起手式", r"(?:^|[。！？\n])\s*(?:说白了|说穿了|先说结论|不吹不黑|往白了说)",
      "BLOCK", "叙述者跳出故事跟读者交底。",
      "删掉起手式，直接给判断。", scope="narration"),
    R("G4-11", "G4", "段首零主语评论", r"(?:^|\n)\s*(?:听起来|看起来|值得注意的是|更重要的是|关键在于|问题在于|意味着|不难看出|有意思的是)[^。！？\n]{0,40}",
      "WARN", "非首段以评论语开头却缺回指成分，读者得回上一段找对象。",
      "补一个「这」或点明评论对象；首段与引语内部不适用。"),
]


# --------- 统计型指标（无法用单条正则判定，按整章密度评估） ---------
STAT_RULES = {
    "dash": {
        "id": "G4-04",
        "gate": "G4",
        "name": "破折号滥用",
        "note": "揭晓式破折号；人类写作约 0.8 次/千字，小说允许略高，超出阈值需逐处判断是否在制造停顿揭晓。",
        "fix": "直接写完整句子，或改用逗号、句号；确属对话被打断的破折号可保留。",
    },
    "same_structure": {
        "id": "G4-03",
        "gate": "G4",
        "name": "相邻句结构同款",
        "note": "连续三句以上同一句法骨架（逗号数相同、成分顺序相同、长度接近），像在填表。",
        "fix": "打散其中一句的句法：合并、拆分、换语序；只改句内，不动段落顺序。",
    },
    "summarize_over_data": {
        "id": "G4-08",
        "gate": "G4",
        "name": "概括盖掉已有具体数据",
        "note": "同段已写出具体数字/时间，却仍用「显著提升」「大幅增长」盖住它。",
        "fix": "把已有具体值提到概括词的位置；原文没有数据时只恢复动词，绝不编数字。",
    },
    "pause_list": {
        "id": "LF-W",
        "gate": "G4",
        "name": "破折号/顿号密度",
        "note": "密度类提示。",
        "fix": "按上述单条规则处理。",
    },
}

QUOTE_PATTERNS = [
    re.compile(r"「[^」]*」"),
    re.compile(r"“[^”]*”"),
    re.compile(r"『[^』]*』"),
    re.compile(r"`[^`\n]*`"),  # 行内代码/型号/编号：按保护内容处理，不参与套路检测
]


def is_han(ch):
    cp = ord(ch)
    return 0x3400 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF or 0x20000 <= cp <= 0x3134F


def prose_lines(text):
    """提取纯正文行，保留原始行号；跳过标题、代码围栏、分隔线与转储标记。"""
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
        if stripped in ("---", "***", "___", "***"):
            continue
        yield line_no, line


def mask_dialogue(line):
    """把引号内台词替换为等长占位符，保持索引对齐，用于豁免类规则。"""
    masked = line
    for pat in QUOTE_PATTERNS:
        def repl(m):
            return "□" * len(m.group())
        masked = pat.sub(repl, masked)
    return masked


def mask_code(line):
    """只遮行内代码/型号编号（保护内容），用于非豁免规则。"""
    return QUOTE_PATTERNS[3].sub(lambda m: "□" * len(m.group()), line)


def mask_all_dialogue(line):
    """把整段引号（含引号本身）遮掉，用于统计叙述部分的密度。"""
    return mask_dialogue(line)


def mask_narration(line):
    """只留引号内台词，其余替换为等长占位符（用于「仅台词」规则）。"""
    keep = [False] * len(line)
    for pat in QUOTE_PATTERNS[:3]:
        for m in pat.finditer(line):
            for i in range(m.start(), m.end()):
                keep[i] = True
    out = []
    for i, ch in enumerate(line):
        out.append(ch if (keep[i] or ch.isspace()) else "□")
    return "".join(out)


def split_sentences(text):
    parts = re.split(r"(?<=[。！？…])", text)
    return [p.strip() for p in parts if p.strip()]


def check_dash(prose_han, dash_count):
    per_k = dash_count / (prose_han / 1000.0) if prose_han else 0
    return {
        "value": dash_count,
        "per_1000": round(per_k, 2),
        "verdict": "BLOCK" if per_k > 3.0 else ("WARN" if per_k > 1.5 else "PASS"),
    }


def check_same_structure(prose):
    """相邻三句同款：逗号数相同、长度接近、句末同为句号。"""
    sents = split_sentences(prose)
    groups = []
    run = []
    for i, s in enumerate(sents):
        core = s.rstrip("。！？…")
        commas = core.count("，")
        if not (12 <= len(core) <= 60) or commas == 0:
            if len(run) >= 3:
                groups.append(run)
            run = []
            continue
        if run:
            prev = run[-1]
            if prev[1] == commas and abs(prev[2] - len(core)) <= 6:
                run.append((i, commas, len(core), s))
                continue
            if len(run) >= 3:
                groups.append(run)
            run = []
        run.append((i, commas, len(core), s))
    if len(run) >= 3:
        groups.append(run)
    return groups


REPEAT_WORDS = ["瞬间", "死死", "狂暴", "狠狠", "狠狠地", "猛地", "骤然"]


def check_repeat_words(prose):
    """高频强化词聚合统计：单词超过 3 次才提示，避免逐处刷屏。"""
    counts = []
    for w in REPEAT_WORDS:
        n = prose.count(w)
        if n > 3:
            counts.append((w, n))
    return counts


def check_summarize_over_data(lines):
    """同段既有具体数字，又用概括词盖住它。"""
    hits = []
    summary_re = re.compile(r"(?:显著|大幅|明显|极大|巨大)(?:提升|增长|改善|提高|降低|缩短|减少)")
    num_re = re.compile(r"[0-9０-９]+|[一二三四五六七八九十百千两]{1,3}(?:个|名|人|米|公里|小时|分钟|天|年|发|枚|度|斤|次)")
    for line_no, line in lines:
        if summary_re.search(line) and num_re.search(line):
            for m in summary_re.finditer(line):
                hits.append({"line": line_no, "match": m.group(), "context": line.strip()[:80]})
    return hits


CHAPTER_RE = re.compile(r"第\s*(\d{1,4})\s*章")


def detect_project_dir(chapter_path):
    cur = chapter_path.resolve().parent
    for _ in range(6):
        if (cur / "02-写作计划.json").exists() or (cur / "08-审稿").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def scan_file(path: Path, min_words: int = None, auto_report: bool = False,
              report_path: str = None, project_dir: str = None):
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    if min_words is None:
        min_words = chapter_limits(path, project_dir)[0]
    raw = path.read_text(encoding="utf-8-sig")
    lines = list(prose_lines(raw))
    prose = "".join(line for _, line in lines)
    han_count = sum(is_han(ch) for ch in prose)

    chapter_number = None
    m = CHAPTER_RE.search(path.stem)
    if m:
        chapter_number = int(m.group(1))

    issues = []
    gate_stats = {g: {"block": 0, "warn": 0} for g in ("G0", "G1", "G2", "G3", "G4")}

    for line_no, line in lines:
        masked_full = mask_dialogue(line)
        masked_code = mask_code(line)
        masked_dlg = mask_narration(line)
        for rule in RULES:
            if rule["pattern"] is None:
                continue
            scope = rule["scope"]
            if scope == "narration":
                target = masked_full
            elif scope == "dialogue":
                target = masked_dlg
            else:
                target = masked_code
            for mt in rule["pattern"].finditer(target):
                start, end = mt.start(), mt.end()
                snippet = line[max(0, start - 20):min(len(line), end + 20)].strip()
                issues.append({
                    "gate": rule["gate"],
                    "rule_id": rule["id"],
                    "rule": rule["name"],
                    "severity": rule["severity"],
                    "line": line_no,
                    "match": line[start:end],
                    "context": snippet,
                    "note": rule["note"],
                    "fix": rule["fix"],
                })
                gate_stats[rule["gate"]][
                    "block" if rule["severity"] == "BLOCK" else "warn"
                ] += 1

    # ---- 统计型检查：破折号 ----
    narration = "".join(mask_dialogue(l) for _, l in lines)
    dash_narr = narration.count("——")
    dash_all = prose.count("——")
    dash_result = check_dash(han_count, dash_all)
    if dash_result["verdict"] != "PASS":
        sev = dash_result["verdict"]
        issues.append({
            "gate": "G4",
            "rule_id": "G4-04",
            "rule": "破折号滥用（密度）",
            "severity": sev,
            "line": 0,
            "match": f"全章 {dash_all} 处（叙述 {dash_narr} 处，{dash_result['per_1000']}/千字）",
            "context": "密度指标；台词内被打断的破折号已单独计数",
            "note": STAT_RULES["dash"]["note"],
            "fix": STAT_RULES["dash"]["fix"],
        })
        gate_stats["G4"]["block" if sev == "BLOCK" else "warn"] += 1

    # ---- 统计型检查：相邻句结构同款 ----
    structure_groups = check_same_structure(narration)
    if structure_groups:
        issues.append({
            "gate": "G4",
            "rule_id": "G4-03",
            "rule": "相邻句结构同款",
            "severity": "WARN",
            "line": 0,
            "match": f"共 {len(structure_groups)} 组连续三句以上同构（逗号数相同、长度接近）",
            "context": " / ".join(g[0][3][:24] + "…" for g in structure_groups[:3]),
            "note": STAT_RULES["same_structure"]["note"],
            "fix": STAT_RULES["same_structure"]["fix"],
        })
        gate_stats["G4"]["warn"] += 1

    # ---- 统计型检查：高频强化词聚合 ----
    repeat_hits = check_repeat_words(prose)
    if repeat_hits:
        desc = "、".join(f"{w}×{n}" for w, n in repeat_hits)
        issues.append({
            "gate": "G0",
            "rule_id": "G0-04",
            "rule": "高频强化词堆积",
            "severity": "WARN",
            "line": 0,
            "match": desc,
            "context": "全章统计，单次出现不算问题",
            "note": "并非禁用词，但同一章密集复现会形成机械强化节奏。",
            "fix": "把超出部分换成具体动作或生理反应（手抖、耳鸣、指节发白），不要整词删除。",
        })
        gate_stats["G0"]["warn"] += 1

    # ---- 统计型检查：概括盖掉具体数据 ----
    for hit in check_summarize_over_data(lines):
        issues.append({
            "gate": "G4",
            "rule_id": "G4-08",
            "rule": "概括盖掉已有具体数据",
            "severity": "WARN",
            "line": hit["line"],
            "match": hit["match"],
            "context": hit["context"],
            "note": STAT_RULES["summarize_over_data"]["note"],
            "fix": STAT_RULES["summarize_over_data"]["fix"],
        })
        gate_stats["G4"]["warn"] += 1

    issues.sort(key=lambda x: (x["line"], x["gate"], x["rule_id"]))

    block_issues = [i for i in issues if i["severity"] == "BLOCK"]
    warn_issues = [i for i in issues if i["severity"] == "WARN"]

    length_issues = []
    length_status = "PASS"
    if han_count < min_words:
        length_status = "BLOCKED"
        length_issues.append(f"正文汉字 {han_count} 字，低于下限 {min_words} 字（缺口 {min_words - han_count}）")

    overall = "BLOCKED" if (block_issues or length_status == "BLOCKED") else (
        "PASS_WITH_WARNINGS" if warn_issues else "PASS"
    )

    result = {
        "file": str(path.resolve()),
        "chapter_number": chapter_number,
        "han_characters": han_count,
        "min_words_required": min_words,
        "length_status": length_status,
        "length_issues": length_issues,
        "gates": gate_stats,
        "block_count": len(block_issues),
        "warn_count": len(warn_issues),
        "overall_status": overall,
        "issues": issues,
        "metrics": {
            "dash_total": dash_all,
            "dash_narration": dash_narr,
            "dash_per_1000": dash_result["per_1000"],
            "same_structure_groups": len(structure_groups),
            "dunhao_count": prose.count("、"),
            "colon_count": prose.count("："),
        },
        "disclaimer": "机械合检只报可定位标记，不构成 AI 作者鉴定；四关人工复核仍需逐条执行，见 references/ai-tone/chapter-gate-runbook.md",
    }

    # ---- 报告落盘 ----
    if report_path or auto_report:
        target = Path(report_path) if report_path else None
        if target is None:
            base = Path(project_dir) if project_dir else detect_project_dir(path)
            if base is None:
                base = path.parent
            review_dir = base / "08-审稿"
            review_dir.mkdir(parents=True, exist_ok=True)
            num = chapter_number if chapter_number is not None else 0
            target = review_dir / f"第{num:03d}章-去AI味四关报告.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_markdown(result, path), encoding="utf-8")
        result["report_path"] = str(target.resolve())

    return result


MANUAL_CHECKLIST = {
    "G1": [
        "每个新增的具体信息都能在原文或素材里找到出处？找不到就撤回。",
        "独立信息、否定、限定、时间、范围、归因是否完整？有没有把「可能」写成「确定」？",
        "被删的句子是否确属纯套话，而不是承担转场或节奏？",
        "有没有把作品本身的文学手段（有意排比、比喻、短句强调）当成 AI 味删掉？",
    ],
    "G2": [
        "删掉空话后有没有补上同族的另一句空话（换汤不换药）？",
        "立场是否明确？「各有优缺点」「因人而异」是否改成了角色的实际选择？",
        "罐头反应镜头是删掉了还是补上了具体信息（谁先开口、外面什么声响）？",
        "有没有替角色编造原文没有的经历、情绪或往事来「增加人味」？",
    ],
    "G3": [
        "每个动作是否还原成了可拍的具体动作，而不是流程名词？",
        "施事者、责任主体是否清楚（谁下的令、谁动的手）？",
        "情态与情报边界是否守恒（可能/据说/大概没有被升级成确定）？",
        "翻译腔五类之外的表达有没有被顺手改掉（越界修改）？",
    ],
    "G4": [
        "每处改动都能对应到某一条编号规则？指不出规则的一律撤回。",
        "有没有为了「制造节奏」调整句长或拆段落（这项实测无差异，不作为理由）？",
        "段首评论是否已补回指成分；比喻独立成段是否被误删？",
        "改动是否限制在解决命中问题的最小范围，没有顺便润色相邻文字？",
    ],
}


def render_markdown(result, path):
    num = result["chapter_number"]
    title = f"第 {num:03d} 章" if num is not None else path.stem
    g = result["gates"]
    out = []
    out.append(f"# {title} 去 AI 味四关报告（机械合检 + 人工复核）")
    out.append("")
    out.append(f"- **章节文件**：`{path.name}`")
    out.append(f"- **正文汉字**：{result['han_characters']} 字（下限 {result['min_words_required']}）")
    out.append(f"- **篇幅判定**：{result['length_status']}")
    out.append(f"- **四关判定**：**{result['overall_status']}**"
               f"（BLOCK {result['block_count']} 处 / WARN {result['warn_count']} 处）")
    out.append("")
    out.append("> 关卡来源：G0 本书铁律；G1 `op7418/Humanizer-zh`；G2 `Raymondhou0917/speak-human-tw`；"
               "G3 `MrGeDiao/shuorenhua`；G4 `larashero3-dotcom/lieflat-less-ai-tone`。")
    out.append("> 机械命中只是线索，最终判定以 `references/ai-tone/chapter-gate-runbook.md` 的人工复核为准。")
    out.append("")
    out.append("## 一、四关汇总")
    out.append("")
    out.append("| 关卡 | 来源 | BLOCK | WARN | 结论 |")
    out.append("|---|---|---:|---:|---|")
    for key, label in (("G0", "本书铁律"), ("G1", "Humanizer-zh"), ("G2", "speak-human-tw"),
                       ("G3", "shuorenhua"), ("G4", "lieflat-less-ai-tone")):
        s = g.get(key, {"block": 0, "warn": 0})
        verdict = "BLOCKED" if s["block"] else ("待裁量" if s["warn"] else "PASS")
        out.append(f"| {key} | {label} | {s['block']} | {s['warn']} | {verdict} |")
    out.append("")
    if result["length_issues"]:
        out.append("**篇幅问题**：")
        for item in result["length_issues"]:
            out.append(f"- {item}")
        out.append("")

    blocks = [i for i in result["issues"] if i["severity"] == "BLOCK"]
    warns = [i for i in result["issues"] if i["severity"] == "WARN"]

    out.append("## 二、阻断项（必须逐条改完再复检）")
    out.append("")
    if blocks:
        out.append("| 行号 | 规则 | 命中 | 为什么改 | 建议改法 |")
        out.append("|---:|---|---|---|---|")
        for i in blocks:
            ctx = i["context"].replace("|", "／")
            out.append(f"| {i['line']} | {i['rule_id']} {i['rule']} | {ctx} | {i['note']} | {i['fix']} |")
    else:
        out.append("无。")
    out.append("")

    out.append("## 三、待裁量项（逐条确认保留或修改，不得默认放过）")
    out.append("")
    if warns:
        out.append("| 行号 | 规则 | 命中 | 为什么改 | 建议改法 |")
        out.append("|---:|---|---|---|---|")
        for i in warns:
            ctx = i["context"].replace("|", "／")
            out.append(f"| {i['line']} | {i['rule_id']} {i['rule']} | {ctx} | {i['note']} | {i['fix']} |")
    else:
        out.append("无。")
    out.append("")

    m = result["metrics"]
    out.append("## 四、机械指标")
    out.append("")
    out.append(f"- 破折号：全章 {m['dash_total']} 处（叙述 {m['dash_narration']} 处，{m['dash_per_1000']}/千字）")
    out.append(f"- 顿号总数：{m['dunhao_count']}；冒号总数：{m['colon_count']}")
    out.append(f"- 相邻三句同构组数：{m['same_structure_groups']}")
    out.append("")
    out.append("## 五、四关人工复核清单（脚本无法覆盖的部分）")
    out.append("")
    for key in ("G1", "G2", "G3", "G4"):
        out.append(f"**{key}**")
        for item in MANUAL_CHECKLIST[key]:
            out.append(f"- [ ] {item}")
        out.append("")
    out.append("## 六、结论")
    out.append("")
    if result["overall_status"] == "BLOCKED":
        out.append("**BLOCKED**：存在阻断项或篇幅越界，严禁进入事实回写与归档。改完必须重跑本脚本至 PASS。")
    elif result["overall_status"] == "PASS_WITH_WARNINGS":
        out.append("**PASS_WITH_WARNINGS**：无阻断项，待裁量项已逐条确认后可放行。")
    else:
        out.append("**PASS**：机械合检与证据口径无阻断项；仍须完成第五部分人工复核。")
    out.append("")
    return "\n".join(out)


def print_human(result):
    print("=" * 68)
    print(f"📄 {result['file']}")
    print(f"📊 正文汉字 {result['han_characters']} | 篇幅 {result['length_status']} | "
          f"四关判定 {result['overall_status']}")
    print(f"   BLOCK {result['block_count']} 处 | WARN {result['warn_count']} 处")
    for key in ("G0", "G1", "G2", "G3", "G4"):
        s = result["gates"][key]
        print(f"   {key}: block={s['block']} warn={s['warn']}")
    for i in result["issues"][:30]:
        mark = "❌" if i["severity"] == "BLOCK" else "⚠️"
        print(f"  {mark} L{i['line']} [{i['rule_id']} {i['rule']}] {i['context'][:60]}")
    if len(result["issues"]) > 30:
        print(f"  ... 另有 {len(result['issues']) - 30} 处，用 --json 查看全部")
    if result.get("report_path"):
        print(f"📝 四关报告已写入: {result['report_path']}")
    print("=" * 68)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", type=Path, nargs="+", help="章节 Markdown 文件路径")
    parser.add_argument("--project-dir", type=str, default=None, help="小说工程根目录（用于定位 08-审稿）")
    parser.add_argument("--min-words", type=int, default=None, help="覆盖小说项目的最低字数")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--auto-report", action="store_true", help="自动写入 08-审稿/第{XX}章-去AI味四关报告.md")
    parser.add_argument("--report", type=str, default=None, help="指定报告输出路径")
    parser.add_argument("--baseline", action="append", default=[], help="同类已定稿正文（建议至少3章，可重复）")
    parser.add_argument("--zhuque", action="store_true", help="显式上传正文至朱雀官方接口，需MAKERS_MODELS_KEY")
    parser.add_argument("--no-style-stats", action="store_true", help="关闭本地统计证据层；默认启用")

    args = parser.parse_args()
    try:
        results = [
            scan_file(p, chapter_limits(p, args.project_dir, min_words=args.min_words)[0], args.auto_report, args.report, args.project_dir)
            for p in args.files
        ]
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(2)

    # 统计证据层仅为候选，绝不改变原四关的退出码或 BLOCKED 判定。
    if not args.no_style_stats:
        try:
            import novel_style_statistics as style
            for chapter, result in zip(args.files, results):
                parts = style.paragraphs(chapter)
                local_metrics = style.metrics(parts)
                candidates, counts = style.scan(parts)
                baseline = style.baseline_compare(local_metrics, args.baseline) if args.baseline else {
                    "status": "NOT_REQUESTED", "used": 0, "message": "未提供已定稿基线"}
                analysis = {
                    "file": str(chapter), "mode": "prose", "metrics": local_metrics,
                    "candidates": candidates, "candidate_counts": counts, "baseline": baseline,
                    "zhuque": style.zhuque_check(parts) if args.zhuque else {"status": "NOT_REQUESTED"},
                    "quality_gate": "REFERENCE_ONLY",
                }
                result["style_analysis"] = analysis
                if result.get("report_path"):
                    with open(result["report_path"], "a", encoding="utf-8") as f:
                        f.write("\n---\n\n" + style.md_report(analysis))
        except (OSError, UnicodeError, ImportError) as exc:
            for result in results:
                result["style_analysis_error"] = str(exc)
            print("统计证据层不可用；四关结果仍有效（统计未执行）", file=sys.stderr)
    elif args.zhuque:
        parser.error("--zhuque 与 --no-style-stats 不能同时使用")

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print_human(item)

    sys.exit(1 if any(r["overall_status"] == "BLOCKED" for r in results) else 0)


if __name__ == "__main__":
    main()
