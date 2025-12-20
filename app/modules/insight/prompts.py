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

# 实例化（如果需要单例，或者直接用静态方法）
prompts = ResearchPrompts()