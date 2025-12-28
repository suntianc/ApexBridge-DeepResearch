# app/modules/insight/prompts.py
from textwrap import dedent
from typing import List, Dict

class ResearchPrompts:
    """
    统一管理系统中的所有 Prompt 模板。
    使用 dedent 去除缩进，保持 Prompt 干净。
    """

    # ==================== Clarifier (澄清者) ====================

    @staticmethod
    def clarification_check(topic: str) -> str:
        """[澄清者] 检查研究主题是否存在歧义"""
        return dedent(f"""
            你是一个严谨的研究员。用户提出了研究主题："{topic}"。
            请判断该主题是否存在重大歧义（例如时间范围不明、对象不明确、背景缺失）。

            如果存在歧义，请生成 1-3 个澄清问题，并给出你认为最合理的【默认假设】。
            如果非常清晰，请直接返回 "CLEAR"。

            输出格式（JSON）:
            {{
                "is_clear": boolean,
                "reason": "解释为什么不清",
                "questions": ["问题1", "问题2"],
                "assumptions": "如果用户不回答，我将默认研究..."
            }}
        """).strip()

    # ==================== Planner (规划者) ====================

    @staticmethod
    def outline_generation(topic: str, intent: str) -> str:
        """[规划者] 生成研究报告大纲结构"""
        return dedent(f"""
            研究主题：{topic}
            详细意图：{intent}

            请生成一份深度研究报告的【大纲结构】。这将作为后续研究的骨架。

            要求：
            1. 包含 4-6 个核心章节（不含摘要和结论）。
            2. 每个章节必须是一个具体的调研方向，逻辑递进。
            3. 避免空泛的标题，要具体。

            输出格式（JSON List）:
            ["1. 全球市场规模与增长驱动力分析", "2. NexaAI 的核心技术架构拆解", "3. ..."]
        """).strip()

    @staticmethod
    def planner_tasks_from_outline(topic: str, outline: list, existing_plan_json: str) -> str:
        """[规划者] 基于大纲拆解搜索任务"""
        return dedent(f"""
            你是一个项目经理。基于以下研究大纲，拆解具体的搜索任务。

            【研究主题】：{topic}
            【研究大纲】：
            {outline}

            【当前已有的计划】：
            {existing_plan_json}

            【任务】：
            请为大纲中【尚未充分研究】的章节生成搜索任务。

            【要求】：
            1. 每个任务必须明确服务于某个大纲章节。
            2. 任务必须具体（例如 "搜索 X 的白皮书" 而不是 "搜索 X"）。
            3. 建立合理的依赖关系。

            【输出格式】：
            严格返回 JSON 列表：
            [
                {{
                    "id": "task_market_1",
                    "description": "针对章节1，搜索2024年相关市场报告数据",
                    "dependencies": [],
                    "related_section": "1. 全球市场规模..."
                }}
            ]
        """).strip()

    @staticmethod
    def planner_dag_replanning(topic: str, existing_plan_json: str, feedback: str) -> str:
        """[规划者] 根据 Critic 反馈追加新任务"""
        return dedent(f"""
            你是一个敏捷的项目经理。我们对 '{topic}' 的初步研究收到了批评反馈，需要补充调查。

            【当前已完成的计划】：
            {existing_plan_json}

            【批评与建议】：
            {feedback}

            【任务】：
            请根据建议，生成 **1-3 个新的补救任务**，添加到现有的 DAG 中。

            【要求】：
            1. 新任务的 ID 必须不与现有 ID 冲突（建议使用 "fix_task_1", "fix_task_2" 等）。
            2. 新任务可以依赖现有的已完成任务。
            3. 只返回新增任务的 JSON 列表。

            【输出格式示例】：
            [
                {{
                    "id": "fix_data_2024",
                    "description": "搜索最新的2024年Q4营收数据以修正过时信息",
                    "dependencies": ["task_1"]
                }}
            ]
        """).strip()

    @staticmethod
    def planner_section_retry(focus_section: str, feedback: str) -> str:
        """[规划者] 针对特定章节补充搜索任务"""
        return dedent(f"""
            你是一个敏捷的项目经理。我们对某章节的初步研究收到了批评反馈，需要补充调研。

            【问题章节】：{focus_section}

            【批评与建议】：
            {feedback}

            【任务】：
            请生成 **1-3 个精准的搜索任务**，专门补充该章节缺失的信息。

            【要求】：
            1. 任务必须直接解决 Critic 指出的问题
            2. 任务描述要具体，包含具体的搜索意图
            3. 新任务的 ID 必须全局唯一，建议使用 "fix_section_{{序号}}" 格式
               例如：fix_section_1, fix_section_2（不要重复使用已存在的 ID）

            【输出格式】：
            严格返回 JSON 列表：
            [
                {{
                    "id": "fix_section_1",
                    "description": "搜索 2024 年 {focus_section} 相关数据报告",
                    "dependencies": [],
                    "related_section": "{focus_section}"
                }}
            ]
        """).strip()

    # ==================== Searcher (搜索者) ====================

    @staticmethod
    def search_result_selection(task_description: str, snippets_text: str, num_select: int = 3) -> str:
        """[搜索者] 从搜索结果中筛选高价值链接"""
        return dedent(f"""
            任务目标：{task_description}

            以下是搜索引擎返回的结果片段：
            {snippets_text}

            【任务】：
            请从中筛选出 {num_select} 个最有价值、信息量最大、最可能包含干货（如PDF、官方文档、技术博客）的链接。

            【输出格式】：
            严格返回 JSON 列表，只包含选中的 url：
            ["https://example.com/report.pdf", "https://github.com/xx/xx"]
        """).strip()

    # ==================== Analyst (分析师) ====================

    @staticmethod
    def analyst_section_writing(section_title: str, existing_draft: str, new_document: str) -> str:
        """[分析师] 分章节增量写作"""
        return dedent(f"""
            你正在撰写一份深度研究报告的**特定章节**。

            【当前章节标题】：{section_title}

            【目前该章节的草稿】：
            ---------------------
            {existing_draft if existing_draft else "(暂无草稿)"}
            ---------------------

            【新读入的参考文档】：
            ---------------------
            {new_document}
            ---------------------

            【任务】：
            请根据新文档的内容，**扩充、修正或完善**当前章节的草稿。

            【要求】：
            1. **聚焦**：只提取与"{section_title}"直接相关的信息。
            2. **细节保留**：保留数据、案例、技术参数等细节。
            3. **引用**：必须在引用处保留 `[Source: url]` 标记。
            4. **增量更新**：不要删除草稿中已有的有价值信息，除非新证据证明其错误。
            5. **输出完整草稿**：返回完整的、可以直接使用的章节内容。

            请直接输出更新后的完整章节草稿：
        """).strip()

    @staticmethod
    def analyst_incremental_reading(topic: str, existing_notes: str, new_document: str) -> str:
        """[分析师] 增量阅读文档并整合笔记"""
        return dedent(f"""
            你是一个正在进行深度调研的研究员。
            研究主题："{topic}"

            这是你【目前的调研笔记】：
            (如果没有笔记，显示为 "暂无")
            =========================================
            {existing_notes}
            =========================================

            这是你刚拿到的【一份新资料】(Markdown格式，包含元数据)：
            =========================================
            {new_document}
            =========================================

            【任务】：
            请阅读这份新资料，将其中的**关键信息、数据、技术细节**整合进你的【调研笔记】中。

            【严格要求】：
            1. **增量更新**：保留笔记中已有的有价值信息，不要删除，除非新资料证明旧信息是错的。
            2. **引用溯源 (CRITICAL)**：从新资料中提取信息时，**必须**在句尾加上来源标记。
               - 格式：`[Source: <url_from_new_document_header>]`
               - 新资料的 URL 在文件开头的 `url: ...` 字段中。
            3. **结构化**：笔记应保持清晰的层级结构（如：技术架构、市场数据、竞品分析）。
            4. **去重**：如果新资料讲的内容笔记里已经有了，且没有更多细节，则忽略，不要重复。

            请输出【更新后的调研笔记】：
        """).strip()

    @staticmethod
    def analyst_merge_sections(topic: str, outline: List[str], section_drafts: Dict[str, str]) -> str:
        """[分析师] 拼装各章节成完整报告"""
        drafts_text = ""
        for title in outline:
            content = section_drafts.get(title, "（暂无内容）")
            drafts_text += f"## {title}\n\n{content}\n\n"

        return dedent(f"""
            你是一位专业的技术报告编辑。请将各章节草稿拼装成一份完整、流畅的研究报告。

            【研究主题】：{topic}

            【研究大纲】：
            {outline}

            【各章节草稿】：
            =========================================
            {drafts_text}
            =========================================

            【任务】：
            1. **结构检查**：确保所有大纲章节都有对应内容
            2. **连贯性**：在各章节之间增加过渡句，使报告整体流畅
            3. **一致性**：统一术语、格式、引用风格
            4. **补充前言**：添加执行摘要和研究背景

            【输出要求】：
            - 直接输出完整的 Markdown 报告
            - 不要添加额外的解释或说明
            - 保持所有原始引用标记
        """).strip()

    @staticmethod
    def analyst_reasoning(topic: str, context: str) -> str:
        """[分析师] RAG 分析与 Gap 识别 (适用于 DeepSeek R1)"""
        return dedent(f"""
            你是一个严谨的深度研究员。基于以下【已核实的知识库片段】进行分析。

            【已核实信息】：
            {context}

            【任务】：
            1. 综合目前关于 '{topic}' 的所有信息，写一段深度分析（Draft）。
            2. 批判性地指出：我们还**缺少**什么关键数据或视角？(Gap Analysis)。

            【输出要求】：
            - 如果信息已经非常充分，能够回答 '{topic}' 的核心问题，Gap 请回复 "无"。
            - 如果信息不足，请在 Gap 部分明确指出下一步需要搜什么（例如："缺乏具体的2024年Q4成本数据"）。
            - 保持客观、中立，用数据说话。
        """).strip()

    # ==================== Critic (批评家) ====================

    @staticmethod
    def critic_evaluation(topic: str, draft: str, section_drafts: dict = None) -> str:
        """[批评家] 评估草稿质量与幻觉 - 支持按章节反馈"""
        # 构建章节摘要（如果提供了）
        sections_info = ""
        if section_drafts:
            sections_info = "\n【各章节草稿预览】：\n"
            for title, content in section_drafts.items():
                content_preview = content[:500] + "..." if len(content) > 500 else content
                sections_info += f"\n## {title}\n{content_preview}\n"

        return dedent(f"""
            你是一个严谨的学术审稿人。请评估关于 '{topic}' 的研究草稿。

            【待评草稿】：
            {draft}
            {sections_info}

            【评估标准】：
            1. **数据支撑 (30分)**: 是否有具体的数字、日期、实体？(空泛的描述扣分)
            2. **逻辑闭环 (30分)**: 结论是否由论据推导得出？
            3. **回答切题 (20分)**: 是否解决了用户最初的研究意图？
            4. **信息深度 (20分)**: 是否提供了超越常识的洞察？

            【输出要求】：
            请严格按照以下 JSON 格式输出（不要输出 Markdown 代码块，直接输出 JSON）：
 {{
                "score": <0-10分，总分/10>,
                "critique": "<具体的批评意见，指出哪里缺数据，哪里逻辑不通>",
                "adjustment": "<给规划者的具体建议，例如：'搜索X公司的财报'，'查找Y技术的原理图'>",
                "focus_section": "<如果问题在特定章节，写章节标题；否则写 null>",
                "reason": "<问题归类：insufficient_data | writing_quality | logic_issue | unknown>"
            }}
        """).strip()

    # ==================== Publisher (出版者) ====================

    @staticmethod
    def publisher_final_report(topic: str, draft_context: str) -> str:
        """[出版者] 生成最终研究报告 (增强版)"""
        return dedent(f"""
            你是一个专业的出版编辑和科技报告作家。
            主题：'{topic}'
            【输入材料】：
            这是一份由资深分析师撰写并经过事实核查的**深度研究草稿**：
            =========================================
            {draft_context}
            =========================================

            【任务】：
            请将这份草稿整理为一份完美的**最终研究报告**。

            【要求】：

            1. **执行摘要 (Executive Summary)**：
               - 放在报告最开头
               - 150-300 字
               - 包含：研究背景、核心发现、关键结论
               - 读者应能通过摘要了解报告精髓

            2. **结构优化**：
               - 确保有清晰的 摘要、目录、正文章节、结论、参考资料
               - 章节标题使用 "##" 二级标题
               - 保持逻辑递进

            3. **数据可视化**：
               - 对于关键数据（增长率、市场份额、营收等），优先使用表格呈现
               - 表格格式示例：
                 | 指标 | 2023年 | 2024年 | 同比变化 |
                 |------|--------|--------|----------|
                 | xxx  | xxx    | xxx    | +xx%     |
               - 不要使用 ASCII art 图表

            4. **引用保留**：
               - 绝对不要删除草稿中的 `[Source: ...]` 引用标记
               - 在正文中引用具体数据时，必须在句末标注来源

            5. **参考资料列表**：
               - 在报告末尾生成参考资料列表
               - 格式：- [标题](URL)

            6. **语言风格**：
               - 客观、专业、详实
               - 避免口语化表达
               - 只做语文润色和格式调整，不删减信息

            【输出格式】：
            直接输出 Markdown 格式的完整报告，不要有前言或解释。
        """).strip()

    # ==================== Verification (验证者) ====================

    @staticmethod
    def verification_claims_extraction(text: str) -> str:
        """[验证者] 提取事实断言"""
        return dedent(f"""
            你是一个专业的事实核查员。请从下面的文本中提取 3-5 个最关键的、包含具体数据或确定性陈述的事实断言。

            【待提取文本】：
            {text}

            【提取要求】：
            1. **只提取客观事实**：如金额、增长率、具体日期、实体关系、并购事件。
            2. **宁缺毋滥**：只提取包含**具体数字、日期、特定实体行为、明确因果关系**的句子。
            3. **忽略空泛内容**：如果该片段只是介绍背景、过渡语句或主观评论，不包含硬核事实，请返回空列表。
            4. **忽略主观观点**：忽略"我认为"、"可能"、"预计"等模糊描述。
            5. **原子化**：每个断言应该是一个独立的句子。

            【输出格式】：
            请严格仅返回 JSON 列表，格式如下：
            [
                {{
                    "original_text": "原文片段...",
                    "claim": "重写后的独立事实陈述"
                }}
            ]
        """).strip()

    @staticmethod
    def verification_claim_check(claim: str, context: str) -> str:
        """[验证者] 基于搜索结果核查断言"""
        return dedent(f"""
            请根据提供的搜索证据，验证以下断言的真实性。

            【待验证断言】：
            {claim}

            【搜索到的证据】：
            {context}

            【判定逻辑】：
            - **Verified (已验证)**: 证据中有明确数据支持该断言。
            - **Disputed (有争议)**: 证据中的数据/事实与断言直接冲突（例如：断言说增长50%，证据说下降10%）。
            - **Unconfirmed (未确认)**: 证据不足，或证据与断言无关。

            【输出格式】：
            请严格仅返回 JSON 对象：
            {{
                "status": "Verified" | "Disputed" | "Unconfirmed",
                "explanation": "一句话解释理由，引用证据中的来源（如果有）"
            }}
        """).strip()

    # ==================== MAD Debate (辩论框架) ====================

    @staticmethod
    def debate_argument(topic: str, stance: str, context: str) -> str:
        """[辩手] 生成辩论陈述"""
        return dedent(f"""
            你正在参与一场关于 '{topic}' 的严肃辩论。

            【你的立场】：{stance} (请极力寻找证据支持此立场，或反驳对方)

            【可用证据】：
            {context}

            【要求】：
            1. 逻辑严密，针锋相对。
            2. 必须显式引用证据（如 "根据[Source 1]..."）。
            3. 保持简短有力（200字以内）。

            请输出你的辩论陈述：
        """).strip()

    @staticmethod
    def debate_judgment(topic: str, affirmative_arg: str, negative_arg: str) -> str:
        """[法官] 最终裁决"""
        return dedent(f"""
            作为中立的大法官，请根据双方辩词对 '{topic}' 做出真理裁决。

            【正方观点】：
            {affirmative_arg}

            【反方观点】：
            {negative_arg}

            【判决标准】：
            1. 谁的证据更权威、更新？
            2. 谁的逻辑链条更完整？
            3. 忽略修辞技巧，只看事实密度。

            【输出格式】：
            请返回 JSON：
            {{
                "winner": "Affirmative" | "Negative" | "Uncertain",
                "conclusion": "最终认定的事实结论",
                "reasoning": "判决理由"
            }}
        """).strip()
    @staticmethod
    def search_query_optimization(task_description: str) -> str:
        """[搜索者] 将自然语言任务转换为各平台的专用搜索词"""
        return dedent(f"""
            你是一个搜索专家。请根据用户的研究任务，为不同的搜索平台生成**最优化的搜索关键词**。
            
            【原始任务】："{task_description}"
            
            【转换规则】：
            1. **ArXiv** (学术论文): 必须翻译成**英文**，使用学术术语。去掉"2024"等时间限制（论文库可能搜不到最新的），只搜核心概念。
            2. **GitHub** (开源代码): 必须翻译成**英文**，关注框架、工具、Dataset、Awesome列表。
            3. **Wikipedia** (百科全书): 提取核心**实体名词**（Entity），尽量短，不要句子。
            4. **Web** (通用搜索): 可以保留中文，或者是经过优化的组合关键词（如 "Market size filetype:pdf"）。
            
            【输出格式】：
            严格返回 JSON 对象：
            {{
                "arxiv": "Mobile AI Agent optimization",
                "github": "mobile-agent-framework",
                "wiki": "Intelligent agent",
                "web": "2024 全球移动端AI Agent 市场规模 报告 filetype:pdf"
            }}
        """).strip()


# 实例化（如果需要单例，或者直接用静态方法）
prompts = ResearchPrompts()
