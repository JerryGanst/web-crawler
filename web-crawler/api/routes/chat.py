# coding=utf-8
"""
聊天 API 路由

提供数据洞察聊天功能的 RESTful API。
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/chat", tags=["聊天"])

logger = logging.getLogger(__name__)


# ==================== 请求/响应模型 ====================

class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="消息角色: user/assistant")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[str] = Field(None, description="时间戳")


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID，不传则自动生成")


class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool
    message: str = Field(..., description="AI回复")
    session_id: str = Field(..., description="会话ID")
    timestamp: str = Field(..., description="响应时间")
    error: Optional[str] = None


class HistoryResponse(BaseModel):
    """历史记录响应"""
    success: bool
    session_id: str
    messages: List[ChatMessage]
    summary: Optional[str] = None


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    created_at: str
    message_count: int
    last_message: Optional[str] = None


# ==================== 全局引擎实例 ====================

_chat_engine = None


def get_engine():
    """获取聊天引擎实例（延迟初始化）"""
    global _chat_engine
    if _chat_engine is None:
        try:
            from chat_engine import get_chat_engine
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            _chat_engine = get_chat_engine(project_root=project_root)
            logger.info("聊天引擎初始化成功")
        except Exception as e:
            logger.error(f"聊天引擎初始化失败: {e}")
            raise
    return _chat_engine


# ==================== API 端点 ====================

@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """
    发送聊天消息

    - **message**: 用户消息内容
    - **session_id**: 会话ID（可选，用于多轮对话）

    返回 AI 的回复内容。
    """
    try:
        engine = get_engine()

        # 生成或使用会话ID
        session_id = request.session_id or str(uuid.uuid4())[:8]

        logger.info(f"收到消息 [session={session_id}]: {request.message[:50]}...")

        # 调用聊天引擎
        response = await engine.chat(
            message=request.message,
            session_id=session_id
        )

        return ChatResponse(
            success=True,
            message=response,
            session_id=session_id,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        return ChatResponse(
            success=False,
            message="",
            session_id=request.session_id or "",
            timestamp=datetime.now().isoformat(),
            error=str(e)
        )


@router.post("/hybrid", response_model=ChatResponse)
async def hybrid_query(request: ChatRequest):
    """
    混合查询接口 (Text-to-SQL + RAG)
    
    优势:
    - 商品查询: 直接生成 SQL，跳过工具选择，速度快且准确
    - 新闻查询: 语义检索 + LLM 摘要
    
    返回结构化查询结果。
    """
    try:
        engine = get_engine()
        session_id = request.session_id or str(uuid.uuid4())[:8]
        
        logger.info(f"混合查询 [session={session_id}]: {request.message[:50]}...")
        
        # 使用混合查询
        result = engine.chat_hybrid(
            message=request.message,
            session_id=session_id
        )
        
        return ChatResponse(
            success=result.get("success", False),
            message=result.get("answer", ""),
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            error=None if result.get("success") else result.get("error")
        )

    except Exception as e:
        logger.error(f"聊天处理失败: {e}", exc_info=True)
        return ChatResponse(
            success=False,
            message="抱歉，处理您的请求时出现错误。",
            session_id=request.session_id or "error",
            timestamp=datetime.now().isoformat(),
            error=str(e)
        )


@router.get("/history/{session_id}", response_model=HistoryResponse)
async def get_history(session_id: str):
    """
    获取会话历史记录

    - **session_id**: 会话ID

    返回该会话的所有消息历史。
    """
    try:
        engine = get_engine()
        history = engine.get_history(session_id)

        return HistoryResponse(
            success=True,
            session_id=session_id,
            messages=[
                ChatMessage(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=msg.get("timestamp")
                )
                for msg in history
            ]
        )

    except Exception as e:
        logger.error(f"获取历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """
    清除会话历史

    - **session_id**: 会话ID

    清除指定会话的所有历史记录。
    """
    try:
        engine = get_engine()
        success = engine.clear_history(session_id)

        return {
            "success": success,
            "message": "历史记录已清除" if success else "清除失败"
        }

    except Exception as e:
        logger.error(f"清除历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    """
    获取聊天服务状态

    返回服务运行状态和配置信息。
    """
    try:
        engine = get_engine()
        return {
            "success": True,
            "status": "running",
            "model": engine.model_name,
            "max_context_messages": engine.max_messages_before_summary,
            "available_tools": [t.name for t in engine.tools],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.post("/new-session")
async def create_session():
    """
    创建新会话

    返回一个新的会话ID。
    """
    session_id = str(uuid.uuid4())[:8]
    return {
        "success": True,
        "session_id": session_id,
        "created_at": datetime.now().isoformat()
    }


@router.post("/trigger-crawl")
async def trigger_crawl(background_tasks: BackgroundTasks):
    """
    触发数据爬取

    在后台启动爬虫获取最新热搜数据。
    """
    import subprocess
    import os

    try:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        def run_crawler():
            try:
                subprocess.run(
                    ["python3", "-m", "scrapers.hotlist_scraper"],
                    cwd=project_root,
                    timeout=120
                )
            except Exception as e:
                logger.error(f"爬虫执行失败: {e}")

        background_tasks.add_task(run_crawler)

        return {
            "success": True,
            "message": "爬虫任务已启动，请稍等片刻后重试查询",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"触发爬虫失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ==================== 流式响应（可选） ====================

from fastapi.responses import StreamingResponse
import asyncio


@router.post("/stream")
async def stream_message(request: ChatRequest):
    """
    流式聊天响应（实验性）

    返回 Server-Sent Events 格式的流式响应。
    """
    session_id = request.session_id or str(uuid.uuid4())[:8]

    async def generate():
        try:
            engine = get_engine()
            response = await engine.chat(
                message=request.message,
                session_id=session_id
            )

            # 模拟流式输出（逐字符）
            for char in response:
                yield f"data: {char}\n\n"
                await asyncio.sleep(0.02)

            yield f"data: [DONE]\n\n"

        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
