from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.pre.api.container import ApiContainer, get_container

from src.app.usecases.signin_usecase import (
    SigninUseCase,
    SigninUserCommand,
    InactiveAccountError,
)


class SigninRequest(BaseModel):
    email: str
    password: str


class SigninResponse(BaseModel):
    id: int
    email: str
    access_token: str  # Token client dùng cho các request sau
    token_type: str = "bearer"  # Báo client gửi token theo dạng "Authorization: Bearer <token>"
    role: str = 'user'  # 'user' | 'admin'


signin_router = APIRouter(
    prefix="/signin",
)


@signin_router.post(
    "/",
    response_model=SigninResponse
)
def signin(
        request: SigninRequest,
        container: ApiContainer = Depends(get_container),
):
    try:
        # mở phiên CSDL, ra khỏi "with" là tự đóng
        with container.unit_of_work() as uow:

            # tạo usecase
            usecase = SigninUseCase(
                uow.users,
                password_hasher=container.password_hasher(),
                token_service=container.token_service()  # Truyền service tạo token vào usecase
            )

            # gọi nghiệp vụ login
            user = usecase.execute(
                SigninUserCommand(
                    email=request.email,
                    password=request.password
                )
            )

        # trả response
        return SigninResponse(
            id=user.user_id,
            email=user.email,
            access_token=user.access_token,  # Gửi token về cho client
            role=user.role
        )

    except InactiveAccountError as e:  # Đúng mật khẩu nhưng chưa được duyệt

        raise HTTPException(
            status_code=403,  # 403 = đã xác thực đúng nhưng không được phép vào
            detail=str(e)
        )

    except Exception as e:

        raise HTTPException(
            status_code=401,
            detail=str(e)
        )
