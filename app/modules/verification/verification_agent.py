# app/modules/verification/verification_agent.py

from typing import List, Dict, Literal
from pydantic import BaseModel
import json
import asyncio

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.core.utils import parse_json_safe
from app.core.llm import simple_llm_call
from app.modules.perception.search import search_generic as search_tool
from app.modules.insight.prompts import ResearchPrompts
# 🟢 引入辩论框架
from app.modules.debate.mad_framework import MADFramework

class FactClaim(BaseModel):
    original_text: str
    claim: str
    verification_status: Literal["Verified", "Disputed", "Unconfirmed"] = "Unconfirmed"
    explanation: str = ""
    source_url: str = ""

class VerificationAgent:
    """
    [验证智能体 V3]
    集成 MAD (多智能体辩论) 的终极验证系统
    能力：分块提取 -> 独立验证 -> 争议自动辩论
    """
    
    @staticmethod
    async def extract_claims(text: str) -> List[FactClaim]:
        """第一步：提取关键事实断言 (Map-Reduce 模式)"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,
            chunk_overlap=500,
            separators=["\n\n", "\n", "。", "！", "？", ".", " ", ""]
        )
        chunks = splitter.split_text(text)
        
        print(f"🛡️ [Verification] Split text into {len(chunks)} chunks for extraction.")
        
        async def process_chunk(chunk_text: str) -> List[dict]:
            prompt = ResearchPrompts.verification_claims_extraction(chunk_text)
            response = await simple_llm_call(prompt, model=settings.MODEL_CHAT)
            result = parse_json_safe(response)
            return result if isinstance(result, list) else []

        results_list = await asyncio.gather(*[process_chunk(chunk) for chunk in chunks])
        
        unique_claims = {}
        for batch in results_list:
            if not isinstance(batch, list): continue
            for item in batch:
                claim_text = item.get("claim", "").strip()
                if not claim_text: continue
                if claim_text not in unique_claims:
                    try:
                        unique_claims[claim_text] = FactClaim(**item)
                    except: pass
        
        final_claims = list(unique_claims.values())
        print(f"🛡️ [Verification] Extracted {len(final_claims)} unique claims.")
        return final_claims

    @staticmethod
    async def verify_claim(claim: FactClaim) -> FactClaim:
        """
        第二步：独立搜索验证 + 🟢 自动辩论升级
        """
        print(f"🔍 [Verification] Checking: {claim.claim}")
        
        # 1. 获取上下文
        try:
            results = await search_tool(f"verify {claim.claim}")
            context = "\n".join([r["snippet"] for r in results]) if results else "No search results found."
        except Exception as e:
            print(f"⚠️ Search failed: {e}")
            context = "Search failed."
        
        # 2. 初始 LLM 判定
        prompt = ResearchPrompts.verification_claim_check(claim.claim, context)
        response = await simple_llm_call(prompt, model=settings.MODEL_REASONING)

        data = parse_json_safe(response)
        if data:
            initial_status = data.get("status", "Unconfirmed")
            claim.explanation = data.get("explanation", "No explanation.")
            if results:
                claim.source_url = results[0]["url"]

            # 🟢 3. MAD 自动升级机制 (Auto-Escalation)
            # 如果初始判定有争议，启动辩论框架进行深究
            if initial_status == "Disputed":
                print(f"🚨 [Verification] Dispute detected! Escalating to MAD protocol for: {claim.claim}")

                # 启动辩论
                debate_result = await MADFramework.conduct_debate(claim.claim, context)

                # 根据辩论结果更新状态
                # 如果正方(Affirmative)赢了，说明原断言其实是成立的，之前可能误判
                if debate_result["winner"] == "Affirmative":
                    claim.verification_status = "Verified"
                    claim.explanation = f"[MAD Overrule] {debate_result['conclusion']}"
                    print(f"✅ [MAD] Overruled dispute -> Verified")

                # 如果反方(Negative)赢了，确认是错误的
                elif debate_result["winner"] == "Negative":
                    claim.verification_status = "Disputed"
                    claim.explanation = f"[MAD Confirmed Dispute] {debate_result['conclusion']}"
                    print(f"❌ [MAD] Confirmed dispute.")

                else:
                    claim.verification_status = "Unconfirmed"
                    claim.explanation = f"[MAD Uncertain] {debate_result['conclusion']}"

            else:
                # 没有争议，直接采纳初始结果
                claim.verification_status = initial_status
        else:
            print(f"⚠️ Verification logic failed: Failed to parse response")
            claim.verification_status = "Unconfirmed"
            claim.explanation = "解析验证响应失败"

        return claim

    @classmethod
    async def verify_report(cls, draft: str) -> str:
        """主入口"""
        # 1. 提取
        claims = await cls.extract_claims(draft)
        if not claims:
            # 添加未验证警告说明，而非静默跳过
            warning = "\n\n---\n> ⚠️ **注意**：系统未能从文本中提取出可验证的独立事实断言，本报告未经自动化事实核查。"
            return draft + warning

        # 2. 验证 (并发控制)
        sem = asyncio.Semaphore(5)
        async def sem_task(c):
            async with sem:
                return await cls.verify_claim(c)

        verified_claims = await asyncio.gather(*[sem_task(c) for c in claims])
        
        # 3. 报告生成
        report_suffix = "\n\n---\n### 🛡️ 事实核查报告 (Automated Verification)\n"
        has_dispute = False
        
        for c in verified_claims:
            icon = "✅"
            if c.verification_status == "Disputed":
                icon = "❌"
                has_dispute = True
            elif c.verification_status == "Unconfirmed":
                icon = "⚠️"
            
            # 如果经过了 MAD，加上标记
            mad_tag = "⚖️" if "[MAD" in c.explanation else ""
            source_link = f"([Source]({c.source_url}))" if c.source_url else ""
            
            report_suffix += f"- {icon} {mad_tag} **{c.verification_status}**: {c.claim}\n  *说明: {c.explanation}* {source_link}\n"
            
        final_draft = draft
        if has_dispute:
            warning = "> ⚠️ **警告：本报告包含部分存在争议的事实，系统已介入多智能体辩论(MAD)进行裁决，详情见文末。**\n\n"
            final_draft = warning + final_draft + report_suffix
        else:
            final_draft = final_draft + report_suffix
            
        return final_draft