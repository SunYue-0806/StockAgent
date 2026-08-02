import json
import logging
from typing import List, Any, Dict

import tiktoken

logger = logging.getLogger(__name__)


class TokenCounter:
    def __init__(self, model_name: str = "gpt-4o"):
        self.model_name = model_name
        self.encoder = self._get_encoder(model_name)

    def _get_encoder(self, model_name: str):
        """修复缺陷 1：根据模型名称动态选择编码器，回退到 cl100k_base"""
        try:
            return tiktoken.encoding_for_model(model_name)
        except KeyError:
            logger.info(f"未找到模型 {model_name} 的专属 Tokenizer，回退使用 cl100k_base")
            return tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(self.encoder.encode(str(text)))

    def count_message(self, message: Any) -> int:
        tokens = 0

        # 1. 基础消息结构开销: <|start|>{role}\n{content}<|end|> 约占 4 tokens
        tokens += 4

        # 2. 算 role 的开销
        role = getattr(message, "role", None) or getattr(message, "type", "user")
        tokens += self.count(role)

        # 3. 算 content 的开销
        content = getattr(message, "content", "") or ""
        if isinstance(content, str):
            tokens += self.count(content)
        elif isinstance(content, list):  # 兼容多模态/Block 结构
            for block in content:
                tokens += self.count(str(block))

        # 4. 算 name 字段开销（如果存在 name，如 ToolMessage，会多占用 1 token）
        name = getattr(message, "name", None) or getattr(message, "tool_name", None)
        if name:
            tokens += self.count(name)
            tokens += 1  # OpenAI 规范：如果有 name，结构多消耗 1 Token

        # 5. 精确计算 tool_calls
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                tokens += 3  # 每个 tool_call 协议头本身的固定开销

                # 提取 id, name, arguments
                tc_id = getattr(tc, "id", "")
                tc_name = getattr(tc, "name", "") or (
                    getattr(tc, "function", {}).name if hasattr(tc, "function") else "")
                tc_args = getattr(tc, "arguments", "") or (
                    getattr(tc, "function", {}).arguments if hasattr(tc, "function") else "")

                # 如果 arguments 是 dict，转成标准 JSON 字符串
                if isinstance(tc_args, dict):
                    tc_args = json.dumps(tc_args, ensure_ascii=False)

                tokens += self.count(tc_id)
                tokens += self.count(tc_name)
                tokens += self.count(tc_args)

        return tokens

    def count_tools_schema_tokens(self, tools_schema: List[Dict[str, Any]]) -> int:
        """补充：算传入的 Tools 定义本身占用的 Token"""
        if not tools_schema:
            return 0
        schema_str = json.dumps(tools_schema, ensure_ascii=False)
        return self.count(schema_str)
