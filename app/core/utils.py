# app/core/utils.py
"""公共工具函数"""
import json
import re
from typing import Optional


def parse_json_safe(text: str) -> Optional[dict | list]:
    """
    安全地解析 JSON 字符串，处理各种格式问题

    支持的格式:
    - 纯 JSON: {"key": "value"}
    - Markdown JSON: ```json {"key": "value"} ```
    - JSON Array: [{"id": 1}, {"id": 2}]
    - JSON in text: Some text {"key": "value"} more text

    Args:
        text: 可能包含 JSON 的文本

    Returns:
        解析后的 dict/list，失败返回 None
    """
    if not text:
        return None

    try:
        # 1. 尝试直接解析（清理 markdown 代码块）
        clean = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # 2. 尝试从文本中提取 JSON 对象或数组
    match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None
