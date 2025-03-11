from fastapi import APIRouter, Depends, HTTPException
from app.common import BusinessException, ResponseCode, success_response, ResponseModel
from pydantic import BaseModel
from app.core.logger import (
    log_request,
    log_info,
    log_error,
    log_warning,
)
import asyncio

router = APIRouter(prefix="", tags=["demo"])


class UserInfo(BaseModel):
    username: str
    age: int


@router.get("/demo", response_model=ResponseModel[UserInfo])
async def demo_success():
    # 返回成功响应
    log_info("成功请求 /demo")  # 使用新的日志函数

    return success_response(data=UserInfo(username="张三", age=18))


@router.get("/demo-async")
async def demo_async(delay: int = 5):  # 添加 delay 参数，默认值为 5
    # 返回成功响应
    log_info("成功请求 /demo-async")  # 使用新的日志函数

    # 模拟一个长时间运行的任务
    await asyncio.sleep(delay)  # 使用 delay 参数
    log_info("成功请求 /demo-async")  # 使用新的日志函数
    return success_response(data=UserInfo(username="张三", age=18))


@router.get("/demo-error")
async def demo_error():
    # 抛出业务异常
    log_error("请求 /demo-error 发生错误")  # 使用新的日志函数
    raise BusinessException(code=ResponseCode.FORBIDDEN, msg="自定义错误信息")


@router.post("/demo-validate")
async def demo_validate(user: UserInfo):
    # FastAPI 会自动进行参数验证
    log_info(f"请求 /demo-validate，用户信息: {user}")  # 使用新的日志函数
    return success_response(data=user)


@router.get("/demo-internal-error")
async def demo_internal_error():
    # 未捕获的异常会被 handle_general_exception 处理
    log_error("请求 /demo-internal-error 发生内部错误")  # 使用新的日志函数
    raise ValueError("发生了一个意外错误")


@router.get("/hello")
@log_request(url="/demo/hello")
async def hello(name: str = "world"):
    log_info(f"处理 hello 请求，参数: name={name}")  # 使用新的日志函数

    # 模拟业务逻辑
    if name.lower() == "error":
        log_warning("触发错误测试")  # 使用新的日志函数
        raise BusinessException(code=ResponseCode.FORBIDDEN, msg="错误测试")

    result = {"message": f"Hello, {name}!"}
    log_info(f"请求处理完成，返回: {result}")  # 使用新的日志函数
    return success_response(data=result)


@router.post("/data")
@log_request(url="/demo/data", level="DEBUG")
async def process_data(data: dict):
    log_info(f"处理数据请求，数据: {data}")  # 使用新的日志函数

    # 处理数据...
    processed = {k: v.upper() if isinstance(v, str) else v for k, v in data.items()}

    log_info("数据处理完成")  # 使用新的日志函数
    return {"processed": processed}
