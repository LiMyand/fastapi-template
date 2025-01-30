from fastapi import APIRouter, Depends
from app.common import (
    BusinessException,
    ResponseCode,
    success_response,
    ResponseModel
)
from pydantic import BaseModel

router = APIRouter()

class UserInfo(BaseModel):
    username: str
    age: int

@router.get("/demo", response_model=ResponseModel[UserInfo])
async def demo_success():
    # 返回成功响应
    return success_response(
        data=UserInfo(username="张三", age=18)
    )

@router.get("/demo-error")
async def demo_error():
    # 抛出业务异常
    raise BusinessException(
        code=ResponseCode.FORBIDDEN,
        message="自定义错误信息" 
    )

@router.post("/demo-validate")
async def demo_validate(user: UserInfo):
    # FastAPI 会自动进行参数验证
    # 如果验证失败，会被 handle_validation_exception 处理
    return success_response(data=user)

@router.get("/demo-internal-error")
async def demo_internal_error():
    # 未捕获的异常会被 handle_general_exception 处理
    raise ValueError("发生了一个意外错误")