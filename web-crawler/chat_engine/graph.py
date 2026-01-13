# coding=utf-8
"""
LangGraph 聊天引擎

实现带记忆压缩的智能对话系统。
架构：滑动窗口 + 摘要压缩策略
"""

import os
import json
import logging
from typing import Literal, Optional, List, Dict, Any, Annotated
from datetime import datetime
from pathlib import Path

import yaml
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    RemoveMessage,
    BaseMessage
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from typing_extensions import TypedDict

from .tools import DataInsightTools, get_tools_instance
from .mongo_checkpointer import get_mongo_checkpointer
from .hybrid_query import get_hybrid_router, HybridQueryRouter

logger = logging.getLogger(__name__)


# ==================== 配置加载 ====================

def _load_google_api_key() -> str:
    """从环境变量或配置文件加载 Google API Key"""
    # 优先从环境变量读取
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        return api_key

    # 从配置文件读取
    config_path = Path(__file__).parent.parent / "config" / "database.yaml"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        google_config = config.get('google_ai', {})
        api_key = google_config.get('api_key', '')
        if api_key:
            return api_key

    logger.warning("GOOGLE_API_KEY 未配置，请设置环境变量或在 config/database.yaml 中配置")
    return ""


# ==================== State 定义 ====================

class AgentState(TypedDict):
    """Agent 状态结构"""
    # messages: 对话消息列表，使用 add_messages 自动处理追加
    messages: Annotated[list, add_messages]
    # summary: 历史对话摘要
    summary: str
    # session_id: 会话ID
    session_id: str


# ==================== 系统提示词 ====================

SYSTEM_PROMPT = """你是一个专业的数据洞察助手，帮助用户分析新闻热搜数据和大宗商品行情。

你的能力：

【新闻热搜】
1. 获取最新热搜新闻（来自知乎、微博、百度、抖音、B站、头条等平台）
2. 搜索历史新闻数据
3. 分析话题热度趋势
4. 对比不同时期的热点变化

【大宗商品】
5. 查询实时商品价格（黄金、白银、原油、铜、铝等）
6. 查看商品历史价格走势
7. 按分类查询：贵金属、能源、工业金属、农产品

回答风格：
- 简洁明了，突出关键信息
- 使用数据支撑观点
- 主动提供洞察和建议
- 商品价格回答时注明单位和涨跌幅

重要规则 - 当新闻数据为空时：
- 调用 trigger_crawl 工具启动爬虫
- 告诉用户：「📭 数据库暂无数据，已为您启动爬虫！请等待 30-60 秒后再次提问。」

重要规则 - 当商品数据为空时：
- 告诉用户：「📭 暂无该商品数据，请确认商品名称或稍后再试。」

当前时间：{current_time}

{summary_context}
"""


# ==================== 核心节点 ====================

class ChatEngine:
    """聊天引擎主类"""

    def __init__(
        self,
        model_name: str = "gemini-3-flash-preview",
        max_messages_before_summary: int = 10,
        messages_to_keep: int = 4,
        project_root: str = None
    ):
        """
        初始化聊天引擎

        Args:
            model_name: 模型名称，支持:
                - gemini-2.5-pro-preview-06-05 (最新预览版)
                - gemini-2.0-flash (快速版)
                - gemini-1.5-pro (稳定版)
                - gemini-1.5-flash (轻量版)
            max_messages_before_summary: 触发摘要的消息数阈值
            messages_to_keep: 摘要后保留的最近消息数
            project_root: 项目根目录
        """
        self.model_name = model_name
        self.max_messages_before_summary = max_messages_before_summary
        self.messages_to_keep = messages_to_keep

        # 初始化模型 (使用 Google AI Studio API)
        api_key = _load_google_api_key()
        if not api_key:
            raise ValueError("GOOGLE_API_KEY 未配置，请设置环境变量或在 config/database.yaml 中配置")

        logger.info(f"初始化模型: {model_name}")

        self.model = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.7,
            max_output_tokens=8192,
            convert_system_message_to_human=True,  # Gemini 不原生支持 system message
            timeout=120,  # 增加超时时间（秒）
        )

        # 初始化工具
        self.tools_manager = get_tools_instance(project_root)
        self.tools = self.tools_manager.get_langchain_tools()

        # 绑定工具到模型
        self.model_with_tools = self.model.bind_tools(self.tools)

        # 构建图
        self.graph = self._build_graph()

        # 尝试使用 MongoDB 存储，失败则回退到内存存储
        try:
            self.checkpointer = get_mongo_checkpointer(required=False)
            if self.checkpointer:
                self.using_mongodb = True
                logger.info("使用 MongoDB 存储聊天历史")
            else:
                self.checkpointer = MemorySaver()
                self.using_mongodb = False
                logger.info("MongoDB 不可用，使用内存存储聊天历史")
        except Exception as e:
            logger.warning(f"MongoDB 连接失败: {e}，使用内存存储")
            self.checkpointer = MemorySaver()
            self.using_mongodb = False

        self.app = self.graph.compile(checkpointer=self.checkpointer)

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 工作流"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("conversation", self._call_model)
        workflow.add_node("tools", ToolNode(self.tools))
        workflow.add_node("summarize", self._summarize_conversation)

        # 定义边
        workflow.add_edge(START, "conversation")

        # 对话节点 -> 判断是否需要调用工具
        workflow.add_conditional_edges(
            "conversation",
            self._route_after_conversation,
            {
                "tools": "tools",
                "summarize": "summarize",
                "end": END
            }
        )

        # 工具节点 -> 回到对话
        workflow.add_edge("tools", "conversation")

        # 摘要节点 -> 结束
        workflow.add_edge("summarize", END)

        return workflow

    def _call_model(self, state: AgentState) -> Dict:
        """对话节点：调用模型生成回复"""
        summary = state.get("summary", "")
        messages = state["messages"]

        # 构建系统提示
        summary_context = f"之前的对话摘要：{summary}" if summary else ""
        system_prompt = SYSTEM_PROMPT.format(
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary_context=summary_context
        )

        # 过滤消息，确保 Gemini 消息顺序正确
        # Gemini 要求: tool_call 后必须紧跟 tool_response
        filtered_messages = self._filter_messages_for_gemini(messages)

        # 组装消息
        full_messages = [SystemMessage(content=system_prompt)] + filtered_messages

        # 调用模型
        response = self.model_with_tools.invoke(full_messages)

        return {"messages": [response]}

    def _filter_messages_for_gemini(self, messages: list) -> list:
        """
        过滤消息以符合 Gemini 的消息顺序要求

        Gemini 要求:
        - function call 必须紧跟在 user turn 或 function response 之后
        - 不能有孤立的 tool_call 没有对应的 tool_response
        """
        from langchain_core.messages import ToolMessage

        filtered = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            # 检查是否是带工具调用的 AI 消息
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                # 需要确保后面有对应的 ToolMessage
                tool_call_ids = {tc.get('id') or tc.get('tool_call_id') for tc in msg.tool_calls if isinstance(tc, dict)}

                # 收集后续的 ToolMessage
                j = i + 1
                tool_responses = []
                while j < len(messages):
                    next_msg = messages[j]
                    if isinstance(next_msg, ToolMessage) or (hasattr(next_msg, 'type') and next_msg.type == 'tool'):
                        tool_responses.append(next_msg)
                        j += 1
                    else:
                        break

                # 只有当有完整的工具调用链时才保留
                if tool_responses:
                    filtered.append(msg)
                    filtered.extend(tool_responses)
                    i = j
                    continue
                else:
                    # 跳过没有响应的工具调用
                    i += 1
                    continue

            # 跳过孤立的 ToolMessage
            if isinstance(msg, ToolMessage) or (hasattr(msg, 'type') and msg.type == 'tool'):
                i += 1
                continue

            # 保留普通的 Human/AI 消息
            if isinstance(msg, (HumanMessage, AIMessage)):
                # 对于 AIMessage，只保留有内容的
                if isinstance(msg, AIMessage):
                    if msg.content:
                        filtered.append(msg)
                else:
                    filtered.append(msg)

            i += 1

        return filtered

    def _route_after_conversation(self, state: AgentState) -> str:
        """路由：判断下一步动作"""
        messages = state["messages"]

        if not messages:
            return "end"

        last_message = messages[-1]

        # 如果最后一条消息有工具调用，转到工具节点
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"

        # 如果消息数超过阈值，触发摘要
        if len(messages) > self.max_messages_before_summary:
            return "summarize"

        return "end"

    def _summarize_conversation(self, state: AgentState) -> Dict:
        """摘要节点：压缩对话历史"""
        summary = state.get("summary", "")
        messages = state["messages"]

        # 构建摘要提示
        if summary:
            summary_prompt = f"""当前摘要：{summary}

请基于上述摘要和下面的新对话，生成一个更新后的简洁摘要。
摘要应该保留关键信息点，包括：
- 用户查询过的话题
- 重要的数据发现
- 用户的偏好或关注点

新对话：
"""
        else:
            summary_prompt = """请将下面的对话总结成一段简洁的摘要。
摘要应该保留关键信息点，包括：
- 用户查询过的话题
- 重要的数据发现
- 用户的偏好或关注点

对话：
"""

        # 提取对话文本
        conversation_text = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                conversation_text.append(f"用户: {msg.content}")
            elif isinstance(msg, AIMessage):
                # 只保留文本内容，跳过工具调用
                if msg.content:
                    conversation_text.append(f"助手: {msg.content[:500]}...")  # 截断长回复

        full_prompt = summary_prompt + "\n".join(conversation_text)

        # 调用模型生成摘要（使用 HumanMessage 格式避免 Gemini API 消息顺序错误）
        response = self.model.invoke([HumanMessage(content=full_prompt)])
        new_summary = response.content

        # 删除旧消息，保留最近几条
        delete_messages = [
            RemoveMessage(id=m.id)
            for m in messages[:-self.messages_to_keep]
            if hasattr(m, 'id') and m.id
        ]

        logger.info(f"对话摘要完成，删除 {len(delete_messages)} 条旧消息")

        return {
            "summary": new_summary,
            "messages": delete_messages
        }

    async def chat(
        self,
        message: str,
        session_id: str = "default"
    ) -> str:
        """
        发送消息并获取回复

        Args:
            message: 用户消息
            session_id: 会话ID

        Returns:
            AI 回复内容
        """
        # 使用同步方法，因为 MongoDB Checkpointer 不支持异步
        return self.chat_sync(message, session_id)

    def chat_sync(
        self,
        message: str,
        session_id: str = "default"
    ) -> str:
        """
        同步版本的聊天方法

        Args:
            message: 用户消息
            session_id: 会话ID

        Returns:
            AI 回复内容
        """
        config = {"configurable": {"thread_id": session_id}}

        # 调用图
        result = self.app.invoke(
            {
                "messages": [HumanMessage(content=message)],
                "session_id": session_id
            },
            config=config
        )

        # 提取最后的 AI 回复
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                content = msg.content
                # 处理 Gemini 3 返回的列表格式
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            return item.get('text', '')
                    return str(content)
                return content

        return "抱歉，我无法生成回复。"

    def chat_hybrid(
        self,
        message: str,
        session_id: str = "default"
    ) -> Dict:
        """
        使用混合查询架构处理消息

        优势:
        - 商品查询: Text-to-SQL，跳过工具选择，速度快且准确
        - 新闻查询: RAG 语义检索 + LLM 摘要

        Args:
            message: 用户消息
            session_id: 会话ID

        Returns:
            {
                "query_type": "commodity" | "news" | "mixed" | "general",
                "success": bool,
                "answer": str,
                "data": any,
                "execution_time_ms": float
            }
        """
        try:
            router = get_hybrid_router()
            result = router.route_and_query(message)

            logger.info(f"混合查询 [{result['query_type']}]: {result.get('total_time_ms', 0):.0f}ms")

            # 保存到会话历史
            self._save_hybrid_to_history(message, result, session_id)

            return result
        except Exception as e:
            logger.error(f"混合查询失败: {e}")
            return {
                "query_type": "error",
                "success": False,
                "answer": f"查询失败: {e}",
                "data": None,
                "execution_time_ms": 0
            }

    def _save_hybrid_to_history(
        self,
        user_message: str,
        result: Dict,
        session_id: str
    ) -> None:
        """
        将混合查询结果保存到会话历史

        Args:
            user_message: 用户消息
            result: 查询结果
            session_id: 会话ID
        """
        try:
            config = {"configurable": {"thread_id": session_id}}

            # 获取当前状态
            current_state = self.app.get_state(config)
            current_messages = []
            current_summary = ""

            if current_state and current_state.values:
                current_messages = list(current_state.values.get("messages", []))
                current_summary = current_state.values.get("summary", "")

            # 过滤掉带有工具调用的消息（避免 Gemini 消息顺序错误）
            # Gemini 要求: tool_call 后必须紧跟 tool_response
            filtered_messages = []
            for msg in current_messages:
                # 跳过带工具调用的 AI 消息
                if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                    continue
                # 跳过工具响应消息
                if hasattr(msg, 'type') and msg.type == 'tool':
                    continue
                # 只保留纯文本的 Human/AI 消息
                if isinstance(msg, (HumanMessage, AIMessage)) and msg.content:
                    filtered_messages.append(msg)

            # 创建新消息
            import uuid
            human_msg = HumanMessage(
                content=user_message,
                id=str(uuid.uuid4())
            )
            ai_msg = AIMessage(
                content=result.get("answer", ""),
                id=str(uuid.uuid4())
            )

            # 追加消息
            new_messages = filtered_messages + [human_msg, ai_msg]

            # 更新状态
            self.app.update_state(
                config,
                {
                    "messages": new_messages,
                    "summary": current_summary,
                    "session_id": session_id
                }
            )

            logger.debug(f"混合查询历史已保存 [session={session_id}]")

        except Exception as e:
            logger.warning(f"保存混合查询历史失败: {e}")

    def get_history(self, session_id: str = "default") -> List[Dict]:
        """
        获取会话历史

        Args:
            session_id: 会话ID

        Returns:
            消息历史列表
        """
        config = {"configurable": {"thread_id": session_id}}

        try:
            state = self.app.get_state(config)
            if state and state.values:
                messages = state.values.get("messages", [])
                history = []
                for msg in messages:
                    if isinstance(msg, HumanMessage):
                        history.append({
                            "role": "user",
                            "content": msg.content,
                            "timestamp": datetime.now().isoformat()
                        })
                    elif isinstance(msg, AIMessage) and msg.content:
                        history.append({
                            "role": "assistant",
                            "content": msg.content,
                            "timestamp": datetime.now().isoformat()
                        })
                return history
        except Exception as e:
            logger.error(f"获取历史失败: {e}")

        return []

    def clear_history(self, session_id: str = "default") -> bool:
        """
        清除会话历史

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        try:
            if self.using_mongodb and hasattr(self.checkpointer, 'delete_thread'):
                # 使用 MongoDB 直接删除会话
                self.checkpointer.delete_thread(session_id)
                logger.info(f"已清除会话 {session_id} 的 MongoDB 历史")
            else:
                # 内存存储：重新创建 checkpointer
                self.checkpointer = MemorySaver()
                self.app = self.graph.compile(checkpointer=self.checkpointer)
                logger.info("已重置内存存储")
            return True
        except Exception as e:
            logger.error(f"清除历史失败: {e}")
            return False


# ==================== 全局实例管理 ====================

_engine_instance: Optional[ChatEngine] = None


def get_chat_engine(
    project_root: str = None,
    force_new: bool = False
) -> ChatEngine:
    """
    获取聊天引擎单例

    Args:
        project_root: 项目根目录
        force_new: 是否强制创建新实例

    Returns:
        ChatEngine 实例
    """
    global _engine_instance

    if _engine_instance is None or force_new:
        _engine_instance = ChatEngine(
            project_root=project_root
        )

    return _engine_instance


# ==================== 测试代码 ====================

if __name__ == "__main__":
    import asyncio

    async def test():
        engine = get_chat_engine()

        # 测试对话
        response = await engine.chat("最近有什么热门新闻？")
        print(f"AI: {response}")

        response = await engine.chat("分析一下AI话题的趋势")
        print(f"AI: {response}")

    asyncio.run(test())
