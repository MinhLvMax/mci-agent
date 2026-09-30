from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_users_repository import PostgresUsersRepository

from src.app.usecases.signin_usecase import (
    SigninUseCase,
    SigninUserCommand
)


class SigninRequest(BaseModel):
    email: str
    password: str


class SigninResponse(BaseModel):
    id: int
    email: str


signin_router = APIRouter(
    prefix="/signin",
)


@signin_router.post(
    "/",
    response_model=SigninResponse
)
def signin(
        request: SigninRequest
):
    # mở database connection
    connection = create_postgres_connection()

    try:

        # tạo repository
        repository = PostgresUsersRepository(
            connection
        )

        # tạo usecase
        usecase = SigninUseCase(
            repository
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
            email=user.email
        )

    except Exception as e:

        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

    finally:

        # đóng connection
        connection.close()
