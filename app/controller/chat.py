from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.common import success_response, ResponseModel, error_response, ResponseCode
from app.core.logger import log_info, log_error
from app.agent.factory import AgentFactory
from app.core.setting import settings
import asyncio
import json

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色，如 'user' 或 'assistant'")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(
        default_factory=list, description="聊天历史消息"
    )
    prompt: str = Field(..., description="用户提问")
    system_prompt: Optional[str] = Field(None, description="系统提示")
    model: str = Field(default="gpt-4o-mini", description="使用的模型")
    stream: bool = Field(default=False, description="是否使用流式响应")
    max_retries: int = Field(default=3, description="最大重试次数")
    retry_delay: float = Field(default=1.0, description="重试间隔时间(秒)")


class ChatResponse(BaseModel):
    content: str = Field(..., description="助手回复内容")
    messages: List[ChatMessage] = Field(..., description="更新后的聊天历史")
    retry_info: Dict[str, Any] = Field(..., description="重试信息")


@router.post("/completions", response_model=ResponseModel[ChatResponse])
async def chat_completions(request: ChatRequest):
    """
    聊天完成接口
    """
    log_info(f"收到聊天请求: {request.prompt[:50]}...")

    # 创建聊天代理
    chat_agent = AgentFactory.create(
        "chat",
        api_key=settings.chat.SHAREAI_API_KEY,
        base_url=settings.chat.SHAREAI_BASE_URL,
        model=request.model,
        max_retries=settings.chat.MAX_RETRIES,
        retry_delay=settings.chat.RETRY_DELAY,
    )

    # 添加历史消息
    for message in request.messages:
        chat_agent.add_message(message.role, message.content)

    try:
        # 执行聊天请求
        if not request.stream:
            # 同步请求
            chat_agent.run(prompt=request.prompt, system_prompt=request.system_prompt)
        else:
            # 流式请求
            await chat_agent.stream_run(
                prompt=request.prompt, system_prompt=request.system_prompt
            )

        # 获取结果
        result = chat_agent.get_result()

        # 获取重试信息
        retry_info = chat_agent.get_retry_info()

        # 转换消息格式
        messages = [
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in chat_agent.messages
        ]

        # 获取助手回复
        assistant_message = (
            chat_agent.get_last_message()
            if chat_agent.messages and chat_agent.messages[-1]["role"] == "assistant"
            else ""
        )

        return success_response(
            data=ChatResponse(
                content=assistant_message, messages=messages, retry_info=retry_info
            )
        )
    except Exception:
        return error_response(
            code=ResponseCode.INTERNAL_ERROR, data=None, msg="服务器繁忙"
        )


class StreamRequest(ChatRequest):
    pass


@router.post("/stream")
async def chat_stream(request: StreamRequest):
    """
    流式聊天接口 - 使用 SSE (Server-Sent Events)
    """
    log_info(f"收到流式聊天请求: {request.prompt[:50]}...")

    # 创建响应生成器
    async def event_generator():
        # 创建聊天代理
        chat_agent = AgentFactory.create(
            "chat",
            api_key=settings.chat.SHAREAI_API_KEY,
            base_url=settings.chat.SHAREAI_BASE_URL,
            model=request.model,
            max_retries=settings.chat.MAX_RETRIES,
            retry_delay=settings.chat.RETRY_DELAY,
        )

        # 添加历史消息
        for message in request.messages:
            chat_agent.add_message(message.role, message.content)

        # 用于存储流式响应内容
        content_buffer = []

        # 回调函数，用于处理流式响应
        async def handle_chunk(chunk: str):
            content_buffer.append(chunk)
            yield f"data: {chunk}\n\n"

        try:
            # 执行流式请求
            task = asyncio.create_task(
                chat_agent.stream_run(
                    prompt=request.prompt,
                    system_prompt=request.system_prompt,
                    callback=lambda chunk: content_buffer.append(chunk),
                )
            )

            # 发送内容
            while not task.done() or content_buffer:
                if content_buffer:
                    chunk = content_buffer.pop(0)
                    yield f"data: {chunk}\n\n"
                else:
                    await asyncio.sleep(0.1)

            # 等待任务完成
            await task

            # 发送完成事件
            retry_info = chat_agent.get_retry_info()
            yield f"data: [DONE]\n\n"
            yield f"data: {json.dumps({'retry_info': retry_info})}\n\n"

        except Exception as e:
            log_error(f"流式聊天请求失败: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


class AsyncChatRequest(ChatRequest):
    callback_url: Optional[str] = Field(None, description="回调URL，用于异步通知结果")


@router.post("/async", response_model=ResponseModel[Dict[str, Any]])
async def async_chat(request: AsyncChatRequest, background_tasks: BackgroundTasks):
    """
    异步聊天接口 - 立即返回，后台处理
    """
    log_info(f"收到异步聊天请求: {request.prompt[:50]}...")

    # 创建任务ID
    task_id = f"task_{id(request)}"

    # 后台任务
    async def process_chat():
        try:
            # 创建聊天代理
            chat_agent = AgentFactory.create(
                "chat",
                api_key=settings.chat.SHAREAI_API_KEY,
                base_url=settings.chat.SHAREAI_BASE_URL,
                model=request.model,
                max_retries=settings.chat.MAX_RETRIES,
                retry_delay=settings.chat.RETRY_DELAY,
            )

            # 添加历史消息
            for message in request.messages:
                chat_agent.add_message(message.role, message.content)

            # 执行聊天请求
            if not request.stream:
                chat_agent.run(
                    prompt=request.prompt, system_prompt=request.system_prompt
                )
            else:
                await chat_agent.stream_run(
                    prompt=request.prompt, system_prompt=request.system_prompt
                )

            # 获取结果
            result = chat_agent.get_result()
            retry_info = chat_agent.get_retry_info()

            log_info(
                f"异步聊天请求完成，任务ID: {task_id}，重试次数: {retry_info['attempts']}"
            )

            # 如果提供了回调URL，发送结果
            if request.callback_url:
                # 这里可以实现回调逻辑
                pass

        except Exception:
            log_error(f"异步聊天请求失败，任务ID: {task_id}")
            # 如果提供了回调URL，发送错误信息
            if request.callback_url:
                # 这里可以实现回调错误逻辑
                pass

    background_tasks.add_task(process_chat)

    # 立即返回
    return success_response(data={"task_id": task_id, "status": "processing"})
