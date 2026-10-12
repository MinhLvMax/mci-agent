from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.pre.api.container import ApiContainer, get_container

from src.app.usecases.signup_usecase import (
    SignupUseCase,
    SignupUserCommand,
    SignupValidationError,
    EmailAlreadyExistsError,
)


class SignupRequest(BaseModel):
    email: str
    password: str


class SignupResponse(BaseModel):
    id: int
    email: str
    is_active: bool  # False: client cần báo user chờ quản trị viên duyệt


signup_router = APIRouter(
    prefix="/signup",
)


@signup_router.post(
    "/",
    response_model=SignupResponse,
    status_code=201,  # 201 = đã tạo tài nguyên mới
)
def signup(
        request: SignupRequest,
        container: ApiContainer = Depends(get_container),
) -> SignupResponse:
    # Router công khai: chưa có tài khoản thì chưa có token, nên không gắn get_current_user_id

    with container.unit_of_work() as uow:
        usecase = SignupUseCase(
            uow.users,
            password_hasher=container.password_hasher(),
        )

        try:
            result = usecase.execute(
                SignupUserCommand(
                    email=request.email,
                    password=request.password,
                )
            )

        except SignupValidationError as e:  # Email sai dạng hoặc mật khẩu không đạt yêu cầu
            raise HTTPException(
                status_code=400,
                detail=str(e),
            )

        except EmailAlreadyExistsError as e:  # Email đã có tài khoản
            raise HTTPException(
                status_code=409,  # 409 = xung đột với dữ liệu đang có
                detail=str(e),
            )

        return SignupResponse(
            id=result.user_id,
            email=result.email,
            is_active=result.is_active,
        )

