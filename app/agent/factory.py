from typing import Dict, Type, Optional
from .base import BaseAgent
from .chat_agent import ChatAgent


class AgentFactory:

    _agent_types: Dict[str, Type[BaseAgent]] = {}

    @classmethod
    def register(cls, agent_type: str, agent_class: Type[BaseAgent]) -> None:
        """
        注册代理类型

        Args:
            agent_type: 代理类型名称
            agent_class: 代理类
        """
        cls._agent_types[agent_type] = agent_class

    @classmethod
    def create(
        cls,
        agent_type: str,
        api_key: str,
        base_url: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs
    ) -> Optional[BaseAgent]:
        """
        创建代理实例

        Args:
            agent_type: 代理类型名称
            api_key: API密钥
            base_url: 基础URL
            max_retries: 最大重试次数
            retry_delay: 重试间隔时间(秒)
            **kwargs: 其他参数

        Returns:
            代理实例，如果类型不存在则返回None
        """
        agent_class = cls._agent_types.get(agent_type)
        if agent_class:
            return agent_class(
                api_key=api_key,
                base_url=base_url,
                max_retries=max_retries,
                retry_delay=retry_delay,
                **kwargs
            )
        return None


AgentFactory.register("chat", ChatAgent)
