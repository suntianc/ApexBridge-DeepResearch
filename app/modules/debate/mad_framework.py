from typing import Dict, Literal
import asyncio

from app.core.config import settings
from app.core.utils import parse_json_safe
from app.core.llm import simple_llm_call
from app.modules.insight.prompts import ResearchPrompts

class DebateResult(Dict):
    winner: Literal["Affirmative", "Negative", "Uncertain"]
    conclusion: str
    reasoning: str

class MADFramework:
    """
    Multi-Agent Debate (MAD) 框架
    用于解决事实冲突或高歧义问题
    """
    
    @staticmethod
    async def conduct_debate(topic: str, context: str) -> DebateResult:
        """
        执行一轮标准的辩论：正方 vs 反方 -> 法官裁决
        """
        print(f"⚖️ [MAD] Starting debate on: {topic}")
        
        # 1. 并行生成双方辩词 (Parallel Generation)
        # 使用 Reasoning 模型以保证逻辑性
        task_affirmative = simple_llm_call(
            ResearchPrompts.debate_argument(topic, "正方 (支持/肯定)", context),
            model=settings.MODEL_REASONING
        )

        task_negative = simple_llm_call(
            ResearchPrompts.debate_argument(topic, "反方 (反对/怀疑)", context),
            model=settings.MODEL_REASONING
        )
        
        # 并发执行
        arg_aff, arg_neg = await asyncio.gather(task_affirmative, task_negative)
        
        print(f"🗣️ [MAD] Affirmative: {arg_aff[:50]}...")
        print(f"🗣️ [MAD] Negative: {arg_neg[:50]}...")
        
        # 2. 法官裁决 (Judge)
        judge_prompt = ResearchPrompts.debate_judgment(topic, arg_aff, arg_neg)
        judge_response = await simple_llm_call(judge_prompt, model=settings.MODEL_REASONING)

        result = parse_json_safe(judge_response)
        if result:
            print(f"⚖️ [MAD] Judgment: {result.get('winner')} - {result.get('conclusion')[:50]}...")
            return result
        else:
            print(f"⚠️ MAD Judgment parsing failed")
            return {
                "winner": "Uncertain",
                "conclusion": "Debate failed to reach consensus.",
                "reasoning": "Failed to parse judge response"
            }