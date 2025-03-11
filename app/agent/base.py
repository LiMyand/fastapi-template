from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, TypeVar, Generic, Union, List
import time
from functools import wraps

T = TypeVar("T")


class BaseAgent(ABC, Generic[T]):
    """
    基础代理类 - 使用工厂模式和策略模式
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        初始化代理

        Args:
            api_key: API密钥
            base_url: 基础URL
            max_retries: 最大重试次数
            retry_delay: 重试间隔时间(秒)
        """
        self.api_key = api_key
        self.base_url = base_url
        self._result: Optional[T] = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        # 记录重试信息
        self.retry_info: Dict[str, Any] = {
            "attempts": 0,
            "errors": [],
            "success": False,
        }

    @abstractmethod
    def run(self, *args, **kwargs) -> None:
        """执行代理的主要功能"""
        pass

    def get_result(self) -> Optional[T]:
        """
        获取代理执行的结果

        Returns:
            执行结果，如果尚未执行则为None
        """
        return self._result

    @abstractmethod
    def reset(self) -> None:
        """重置代理状态"""
        self._result = None
        self.retry_info = {"attempts": 0, "errors": [], "success": False}

    @abstractmethod
    def step(self, *args, **kwargs) -> None:
        """执行单步操作"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """停止代理执行"""
        pass

    # 函数式方法，用于转换结果
    def map_result(self, transform_fn: Callable[[T], Any]) -> Any:
        """
        使用提供的函数转换结果

        Args:
            transform_fn: 转换函数

        Returns:
            转换后的结果
        """
        if self._result is not None:
            return transform_fn(self._result)
        return None

    def with_retry(self, func: Callable) -> Callable:
        """
        装饰器：为函数添加重试功能

        Args:
            func: 需要添加重试功能的函数

        Returns:
            添加了重试功能的函数
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            self.retry_info["attempts"] = 0
            self.retry_info["errors"] = []
            self.retry_info["success"] = False

            retryable_errors = (
                TimeoutError,
                ConnectionError,
                ConnectionRefusedError,
                ConnectionResetError,
            )

            for attempt in range(self.max_retries):
                try:
                    self.retry_info["attempts"] += 1
                    result = func(*args, **kwargs)
                    self.retry_info["success"] = True
                    return result
                except retryable_errors as e:
                    self.retry_info["errors"].append(str(e))
                    if attempt < self.max_retries - 1:
                        # 使用指数退避策略
                        delay = self.retry_delay * (2**attempt)
                        time.sleep(delay)
                    else:
                        # 最后一次尝试失败，重新抛出异常
                        raise

            return None

        return wrapper

    def get_retry_info(self) -> Dict[str, Union[int, List[str], bool]]:
        """
        获取重试信息

        Returns:
            包含重试次数、错误信息和成功状态的字典
        """
        return self.retry_info
