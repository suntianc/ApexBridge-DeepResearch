# app/modules/insight/prompts.py
from textwrap import dedent

class ResearchPrompts:
    """
    统一管理系统中的所有 Prompt 模板。
    使用 dedent 去除缩进，保持 Prompt 干净。
    """

    @staticmethod
    def planner_initial(topic: str) -> str:
        """[规划者] 第一轮：广度优先规划"""
        return dedent(f"""
            用户想研究 '{topic}'。
            请生成 1 个最适合入门或获取宏观数据的搜索引擎关键词。
            
            要求：
            1. 关键词要精准，利于搜索引擎理解。
            2. 只返回关键词本身，不要包含解释或引号。
        """).strip()

    @staticmethod
    def planner_gap_driven(topic: str, gap: str) -> str:
        """[规划者] 后续轮次：基于缺口的深度规划"""
        return dedent(f"""
            研究主题: {topic}
            目前已有的分析指出缺失信息(Gap): "{gap}"
            
            任务：
            请生成 1 个**非常具体**的搜索关键词，专门用来挖掘上述缺失的信息。
            
            示例策略：
            - 如果缺数据，搜索词应包含 "statistics", "data", "report", "2024" 等。
            - 如果缺技术细节，搜索词应包含 "architecture", "specs", "whitepaper" 等。
            
            要求：
            只返回关键词本身，不要包含引号。
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
            - 如果信息不足，请在 Gap 部分明确指出下一步需要搜什么（例如：“缺乏具体的2024年Q4成本数据”）。
            - 保持客观、中立，用数据说话。
        """).strip()

    @staticmethod
    def publisher_final_report(topic: str, context: str) -> str:
        """[出版者] 最终报告生成"""
        return dedent(f"""
            你是一个专业的行业分析师。请根据以下【已核实的信息片段】，撰写一份关于 '{topic}' 的深度研究报告。
            
            【信息片段】：
            {context}
            
            【报告要求】：
            1. 格式：Markdown。
            2. 结构：
               - 📑 **摘要** (Executive Summary)
               - 🧭 **目录**
               - 📖 **正文** (分章节，逻辑清晰)
               - 📊 **结论与展望**
            3. **引用标注** (关键)：在正文中引用具体数据或观点时，必须在句末标注来源，格式为 [Source: URL]。
            4. 语气：客观、专业、详实。
            5. 内容：重点回答用户最初的问题，并整合之前分析中发现的衍生观点。
        """).strip()
    
    @staticmethod
    def critic_evaluation(topic: str, draft: str) -> str:
        """[批评家] 评估草稿质量与幻觉"""
        return dedent(f"""
            你是一个严谨的学术审稿人。请评估关于 '{topic}' 的研究草稿。
            
            【待评草稿】：
            {draft}
            
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
                "adjustment": "<给规划者的具体建议，例如：'搜索X公司的财报'，'查找Y技术的原理图'>"
            }}
        """).strip()
    @staticmethod
    def planner_dag_generation(topic: str, existing_plan_json: str = "[]") -> str:
        """[规划者] 生成或更新 DAG 任务图"""
        return dedent(f"""
            你是一个拥有10年经验的**技术架构师**和项目经理。你的任务是将研究主题 '{topic}' 拆解为一份详细的执行计划。
            
            【核心原则 - 必须遵守】：
            1. **寻找源头**：如果研究涉及开源项目，**必须**包含搜索其 "GitHub", "HuggingFace", "Official Docs" 的任务。不要只搜新闻！
            2. **技术优先**：优先关注 API 接口、硬件需求（NPU/RAM）、部署架构等硬核信息。
            3. **依赖明确**：先搜概况，再搜技术细节，最后做竞品对比。
            
            【当前计划状态】：
            {existing_plan_json}
            
            【任务要求】：
            1. 如果计划为空，请从头生成一份完整的 DAG（有向无环图）计划。
            2. 任务必须具有依赖关系。例如：分析竞品（Task B）通常依赖于收集数据（Task A）。
            3. 任务描述必须具体，包含具体的搜索意图。
            
            【输出格式】：
            请严格只返回一个 JSON 列表，格式如下：
            [
                {{
                    "id": "task_1",
                    "description": "搜索 2024 年全球 GPU 市场规模及主要玩家",
                    "dependencies": [] 
                }},
                {{
                    "id": "task_2",
                    "description": "查找 NVIDIA 和 AMD 最新的财报数据",
                    "dependencies": ["task_1"]
                }}
            ]
            
            注意：
            - id 必须唯一。
            - dependencies 只能包含已定义的 id。
            - 不要使用 Markdown 代码块，直接返回 JSON 字符串。
        """).strip()
    # 事实提取 Prompt
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
            4. **忽略主观观点**：忽略“我认为”、“可能”、“预计”等模糊描述。
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

    # 事实核查 Prompt
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
    # 🟢 新增：MAD 辩论相关提示词
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
# 实例化（如果需要单例，或者直接用静态方法）
prompts = ResearchPrompts()