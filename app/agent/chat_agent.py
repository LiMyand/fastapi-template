from typing import List, Dict, Any, Optional, Callable
from .base import BaseAgent
import httpx
import aiohttp
import json
from functools import partial
import asyncio


class ChatAgent(BaseAgent[Dict[str, Any]]):

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "gpt-4o-mini",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        初始化聊天代理
        Args:
            api_key: API密钥
            base_url: 基础URL
            model: 模型名称
            max_retries: 最大重试次数
            retry_delay: 重试间隔时间(秒)
        """
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        self.model = model
        self.messages: List[Dict[str, str]] = []
        self._is_running = False

    def add_message(self, role: str, content: str) -> None:
        """
        添加消息到对话历史
        """
        self.messages.append({"role": role, "content": content})

    def _execute_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行HTTP请求，可以被重试装饰器包装
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def run(self, prompt: str = None, system_prompt: str = None) -> None:
        """
        执行聊天请求
        """
        self._is_running = True

        if system_prompt and not any(msg["role"] == "system" for msg in self.messages):
            self.add_message("system", system_prompt)

        if prompt:
            self.add_message("user", prompt)

        try:
            payload = {
                "model": self.model,
                "messages": self.messages,
            }

            # 使用重试装饰器包装请求执行函数
            execute_with_retry = self.with_retry(self._execute_request)
            response_data = execute_with_retry(payload)

            self._result = response_data

            if "choices" in response_data and response_data["choices"]:
                assistant_message = response_data["choices"][0]["message"]
                self.add_message(
                    assistant_message["role"], assistant_message["content"]
                )

        except Exception as e:
            self._result = {"error": str(e)}
        finally:
            self._is_running = False

    def reset(self) -> None:
        """重置代理状态"""
        self.messages = []
        self._result = None
        self._is_running = False

    def step(self, prompt: str) -> None:
        """
        执行单步对话

        Args:
            prompt: 用户提示
        """
        self.run(prompt=prompt)

    def stop(self) -> None:
        """停止代理执行"""
        self._is_running = False

    # 函数式方法
    def get_last_message(self) -> Optional[str]:
        """
        获取最后一条消息内容

        Returns:
            最后一条消息的内容
        """
        if self.messages:
            return self.messages[-1]["content"]
        return None

    def filter_messages(self, role_filter: str) -> List[Dict[str, str]]:
        """
        按角色筛选消息

        Args:
            role_filter: 角色名称

        Returns:
            筛选后的消息列表
        """
        return list(filter(lambda msg: msg["role"] == role_filter, self.messages))

    def get_conversation_text(self) -> str:
        """
        获取格式化的对话文本

        Returns:
            格式化后的对话文本
        """
        return "\n".join(
            [f"{msg['role'].upper()}: {msg['content']}" for msg in self.messages]
        )

    async def _execute_stream_request(
        self, payload: Dict[str, Any], callback: Optional[Callable[[str], None]]
    ) -> Dict[str, Any]:
        """
        执行流式HTTP请求，可以被重试装饰器包装
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0,
            ) as response:
                response.raise_for_status()

                full_content = ""
                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data:") and line != "data: [DONE]":
                        chunk_data = line[5:].strip()
                        if chunk_data:
                            try:
                                chunk_obj = json.loads(chunk_data)
                                if "choices" in chunk_obj and chunk_obj["choices"]:
                                    delta = chunk_obj["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        content = delta["content"]
                                        full_content += content
                                        if callback:
                                            callback(content)
                            except Exception:
                                pass

                # 将完整响应添加到消息历史
                if full_content:
                    return {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": full_content,
                                }
                            }
                        ]
                    }
                return {"choices": []}

    async def stream_run(
        self,
        prompt: str = None,
        system_prompt: str = None,
        callback: Callable[[str], None] = None,
    ) -> None:
        """
        流式执行聊天请求，使用 aiohttp 替代 httpx

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            callback: 接收流式响应的回调函数
        """
        self._is_running = True

        # 添加系统提示和用户提示的代码保持不变
        if system_prompt and not any(msg["role"] == "system" for msg in self.messages):
            self.add_message("system", system_prompt)

        if prompt:
            self.add_message("user", prompt)

        try:
            # 准备请求数据
            payload = {"model": self.model, "messages": self.messages, "stream": True}

            # 这里我们需要一个异步版本的重试装饰器
            # 由于基础实现是同步的，我们需要在这里手动实现异步重试逻辑
            attempt = 0
            self.retry_info["attempts"] = 0
            self.retry_info["errors"] = []
            self.retry_info["success"] = False

            while attempt < self.max_retries:
                try:
                    self.retry_info["attempts"] += 1
                    attempt += 1

                    response_data = await self._execute_stream_request(
                        payload, callback
                    )
                    self._result = response_data

                    if "choices" in response_data and response_data["choices"]:
                        assistant_message = response_data["choices"][0]["message"]
                        self.add_message(
                            assistant_message["role"], assistant_message["content"]
                        )

                    self.retry_info["success"] = True
                    break

                except (
                    TimeoutError,
                    ConnectionError,
                    ConnectionRefusedError,
                    ConnectionResetError,
                ) as e:
                    self.retry_info["errors"].append(str(e))
                    if attempt < self.max_retries:
                        # 使用指数退避策略
                        delay = self.retry_delay * (2 ** (attempt - 1))
                        await asyncio.sleep(delay)
                    else:
                        # 最后一次尝试失败
                        raise

        except Exception as e:
            self._result = {"error": str(e)}
        finally:
            self._is_running = False
